"""
Pending Memory API - 待审批记忆管理 API

提供以下端点：
- GET /api/v1/pending/list - 列出待审批记忆
- GET /api/v1/pending/{note_id} - 获取单个待审批记忆
- POST /api/v1/pending/{note_id}/approve - 批准记忆
- POST /api/v1/pending/{note_id}/reject - 拒绝记忆
- GET /api/v1/pending/stats - 获取统计信息
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.core.memory_kernel import get_memory_kernel
from backend.services.pending_memory import PendingMemoryService

router = APIRouter(prefix="/api/v1/pending", tags=["pending"])

# 初始化服务
pending_service = PendingMemoryService()


class ApproveRequest(BaseModel):
    """批准请求"""
    approved_by: str = "caregiver"


class RejectRequest(BaseModel):
    """拒绝请求"""
    rejected_by: str = "caregiver"


@router.get("/list", response_model=List[Dict[str, Any]])
async def list_pending_memories(
    layer: Optional[str] = Query(None, description="按层级过滤"),
    min_confidence: Optional[float] = Query(None, description="最低置信度"),
    limit: int = Query(50, description="返回数量限制", ge=1, le=200),
):
    """
    列出待审批记忆

    按置信度和创建时间降序排列。
    """
    return pending_service.list_pending(
        layer=layer,
        min_confidence=min_confidence,
        limit=limit,
    )


@router.get("/{note_id}", response_model=Dict[str, Any])
async def get_pending_memory(note_id: str):
    """
    获取单个待审批记忆

    Args:
        note_id: 记忆 ID

    Returns:
        待审批记忆详情

    Raises:
        HTTPException: 如果记忆不存在或已处理
    """
    memory = pending_service.get_pending(note_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Pending memory not found or already processed")
    return memory


@router.post("/{note_id}/approve", response_model=Dict[str, Any])
async def approve_pending_memory(note_id: str, request: ApproveRequest):
    """
    批准待审批记忆（带乐观锁 + 补偿机制）

    并发安全保证：
    1. 使用乐观锁（UPDATE WHERE status='pending'）防止并发批准同一记录
    2. 先索引 Qdrant，成功后再更新 SQLite
    3. 如果 SQLite 更新失败，回滚 Qdrant（设置 is_active=False）

    Args:
        note_id: 记忆 ID
        request: 批准请求（包含批准人信息）

    Returns:
        批准结果

    Raises:
        HTTPException:
            - 404: 记忆不存在
            - 409: 记忆正在被其他请求处理或已处理
            - 500: 索引或更新失败
    """
    # 1. 获取待审批记忆并原子性地标记为 processing（乐观锁）
    memory = pending_service.try_lock_for_processing(note_id)
    if not memory:
        raise HTTPException(
            status_code=409,
            detail="Memory is being processed by another request or already processed"
        )

    qdrant_indexed = False
    try:
        # 2. 索引到 Qdrant（原子性：先索引）
        kernel = get_memory_kernel()
        kernel.search.index_note(
            note_id=memory["id"],
            content=memory["content"],
            layer=memory["layer"],
            category=memory["category"],
            is_active=True,
            confidence=memory["confidence"],
            source=memory["source"],
            agent_id=memory.get("agent_id"),
            created_at=memory["created_at"],
            expires_at=memory.get("expires_at"),
            priority=memory.get("priority", 0),
            created_by=memory.get("created_by"),
        )
        qdrant_indexed = True

        # 3. 索引成功后，更新 SQLite 状态并删除（原子性：后更新）
        approved = pending_service.approve_pending(note_id, approved_by=request.approved_by)
        if not approved:
            # 状态已变更（可能被 reject 或其他操作），需要补偿
            raise ValueError("Memory status changed during processing")

        pending_service.delete_pending(note_id)

        return {
            "success": True,
            "message": "Memory approved and indexed successfully",
            "note_id": note_id,
            "memory": memory,
        }

    except Exception as e:
        # 4. 失败时补偿：如果 Qdrant 已索引，则设置为 inactive（软删除）
        if qdrant_indexed:
            try:
                from uuid import UUID
                kernel.search.update_note_status(UUID(memory["id"]), is_active=False)
            except Exception as rollback_error:
                # 补偿失败，记录错误，需要人工清理
                import logging
                logger = logging.getLogger(__name__)
                logger.error(
                    f"Failed to rollback Qdrant for {note_id}: {rollback_error}. "
                    f"Manual cleanup required."
                )

        # 5. 释放锁，恢复为 pending 状态
        pending_service.unlock_from_processing(note_id)

        # 6. 向用户报告错误
        raise HTTPException(
            status_code=500,
            detail=f"Failed to approve memory: {str(e)}. Memory has been unlocked and can be retried."
        )


@router.post("/{note_id}/reject", response_model=Dict[str, Any])
async def reject_pending_memory(note_id: str, request: RejectRequest):
    """
    拒绝待审批记忆

    拒绝后记忆会被标记为 rejected，不会索引到 Qdrant。

    Args:
        note_id: 记忆 ID
        request: 拒绝请求（包含拒绝人信息）

    Returns:
        拒绝结果

    Raises:
        HTTPException: 如果记忆不存在或已处理
    """
    memory = pending_service.reject_pending(note_id, rejected_by=request.rejected_by)
    if not memory:
        raise HTTPException(status_code=404, detail="Pending memory not found or already processed")

    return {
        "success": True,
        "message": "Memory rejected successfully",
        "note_id": note_id,
        "memory": memory,
    }


@router.get("/stats", response_model=Dict[str, Any])
async def get_pending_statistics():
    """
    获取待审批记忆统计信息

    Returns:
        统计信息（总数、按层级分布、平均置信度）
    """
    return pending_service.get_statistics()
