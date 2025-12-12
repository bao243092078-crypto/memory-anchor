"""
Memory API - 统一记忆管理接口

基于 docs/MEMORY_STRATEGY.md 策略：
- POST /memory/add: 添加记忆（遵循置信度分级）
- GET /memory/search: 搜索记忆（宪法层始终可见）
- GET /memory/constitution: 获取全部宪法层
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.models.note import MemoryLayer, NoteCategory
from backend.services.memory import (
    MemoryService,
    MemoryAddRequest,
    MemorySearchRequest,
    MemoryResult,
    MemorySource,
    get_memory_service,
)

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


# === Request/Response Schemas ===


class AddMemoryRequest(BaseModel):
    """添加记忆请求（API层）"""
    content: str = Field(..., min_length=1, max_length=2000, description="记忆内容")
    layer: MemoryLayer = Field(default=MemoryLayer.FACT, description="记忆层级")
    category: Optional[NoteCategory] = Field(default=None, description="分类")
    source: MemorySource = Field(default=MemorySource.CAREGIVER, description="来源")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="置信度")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "content": "患者今天去了公园散步",
                    "layer": "fact",
                    "category": "event",
                    "source": "caregiver",
                    "confidence": 1.0,
                }
            ]
        }
    }


class AddMemoryResponse(BaseModel):
    """添加记忆响应"""
    id: Optional[UUID] = Field(description="记忆ID（低置信度时为None）")
    status: str = Field(description="状态：saved/pending_approval/rejected_low_confidence")
    layer: str = Field(description="记忆层级")
    confidence: float = Field(description="置信度")
    requires_approval: bool = Field(default=False, description="是否需要审批")
    reason: Optional[str] = Field(default=None, description="拒绝原因（如有）")


class SearchMemoryResponse(BaseModel):
    """搜索记忆响应"""
    results: list[MemoryResult]
    count: int
    query: str
    include_constitution: bool


class ConstitutionResponse(BaseModel):
    """宪法层响应"""
    memories: list[MemoryResult]
    count: int


# === API Endpoints ===


@router.post("/add", response_model=AddMemoryResponse, status_code=201)
async def add_memory(request: AddMemoryRequest) -> AddMemoryResponse:
    """
    添加记忆到系统

    **置信度分级处理**（仅AI提取）：
    - ≥0.9: 直接存入事实层
    - 0.7-0.9: 存入待确认区
    - <0.7: 拒绝存储

    **层级限制**：
    - 宪法层：不允许通过此API创建，请使用专用API
    - 事实层：默认层级
    - 会话层：自动记录

    **示例**：
    ```json
    {
        "content": "患者今天去了公园散步",
        "layer": "fact",
        "category": "event",
        "source": "caregiver",
        "confidence": 1.0
    }
    ```
    """
    service = get_memory_service()

    try:
        # 转换为内部请求
        internal_request = MemoryAddRequest(
            content=request.content,
            layer=request.layer,
            category=request.category,
            source=request.source,
            confidence=request.confidence,
        )

        result = await service.add_memory(internal_request)

        return AddMemoryResponse(
            id=result.get("id"),
            status=result["status"],
            layer=result["layer"],
            confidence=result["confidence"],
            requires_approval=result.get("requires_approval", False),
            reason=result.get("reason"),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/search", response_model=SearchMemoryResponse)
async def search_memory(
    q: str = Query(..., min_length=1, description="搜索查询"),
    layer: Optional[MemoryLayer] = Query(default=None, description="过滤记忆层级"),
    category: Optional[NoteCategory] = Query(default=None, description="过滤分类"),
    include_constitution: bool = Query(default=True, description="是否始终包含宪法层"),
    limit: int = Query(default=5, ge=1, le=20, description="返回数量限制"),
    min_score: float = Query(default=0.3, ge=0.0, le=1.0, description="最低分数阈值"),
) -> SearchMemoryResponse:
    """
    搜索记忆

    **检索策略**（基于 MEMORY_STRATEGY.md）：
    - 宪法层：始终预加载（不依赖检索分数）
    - 事实层+会话层：语义检索 + 关键词混合

    **响应格式**：
    - 宪法层结果始终在前
    - 其他结果按分数降序排列

    **示例**：
    - `/memory/search?q=女儿电话` → 返回宪法层联系人信息
    - `/memory/search?q=今天&layer=session` → 搜索今日会话
    """
    service = get_memory_service()

    internal_request = MemorySearchRequest(
        query=q,
        layer=layer,
        category=category,
        include_constitution=include_constitution,
        limit=limit,
        min_score=min_score,
    )

    results = await service.search_memory(internal_request)

    return SearchMemoryResponse(
        results=results,
        count=len(results),
        query=q,
        include_constitution=include_constitution,
    )


@router.get("/constitution", response_model=ConstitutionResponse)
async def get_constitution() -> ConstitutionResponse:
    """
    获取全部宪法层记忆

    宪法层是患者的核心身份信息，包括：
    - 姓名、年龄、住址
    - 关键家庭成员和联系方式
    - 必要的医疗信息（用药、过敏）

    **特点**：
    - 始终全量返回（不依赖检索）
    - 最多20条
    - 置信度始终为1.0
    """
    service = get_memory_service()
    results = await service.get_constitution()

    return ConstitutionResponse(
        memories=results,
        count=len(results),
    )


@router.get("/pending")
async def get_pending_memories():
    """
    获取待审批的记忆列表

    AI提取的中置信度（0.7-0.9）记忆会进入待审批区，
    需要照护者确认后才能存入事实层。

    TODO: 实现待审批队列
    """
    return {
        "pending": [],
        "count": 0,
        "message": "待审批功能将在后续版本实现",
    }


@router.patch("/{memory_id}/approve")
async def approve_memory(memory_id: UUID):
    """
    审批通过记忆

    将待审批区的记忆移入事实层。

    TODO: 实现审批逻辑
    """
    return {
        "id": memory_id,
        "status": "approved",
        "message": "审批功能将在后续版本实现",
    }


@router.patch("/{memory_id}/reject")
async def reject_memory(memory_id: UUID, reason: str = Query(default="")):
    """
    拒绝记忆

    从待审批区删除记忆。

    TODO: 实现拒绝逻辑
    """
    return {
        "id": memory_id,
        "status": "rejected",
        "reason": reason,
        "message": "拒绝功能将在后续版本实现",
    }
