"""Notes API - 便利贴 CRUD 接口

MVP 阶段使用 Qdrant 的 payload 作为便利贴主存储，保证重启后数据仍可用。
"""

from asyncio import to_thread
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from backend.models.note import (
    MemoryLayer,
    NoteCategory,
    NoteCreate,
    NoteResponse,
    NoteUpdate,
)
from backend.core.memory_kernel import get_memory_kernel
from backend.services.search import get_search_service

router = APIRouter(prefix="/notes", tags=["notes"])

_MAX_SCAN_NOTES = 5000


def _ensure_payload_defaults(payload: dict) -> dict:
    """为历史数据补齐必需字段（仅用于响应构造，不强制回写）。"""
    now_iso = datetime.now().isoformat()

    if payload.get("layer") is None:
        payload["layer"] = MemoryLayer.FACT.value

    if payload.get("priority") is None:
        payload["priority"] = 100

    if payload.get("confidence") is None:
        payload["confidence"] = 0.5

    created_by = payload.get("created_by") or payload.get("source") or "caregiver"
    payload.setdefault("created_by", created_by)
    payload.setdefault("source", created_by)

    if payload.get("created_at") is None:
        payload["created_at"] = now_iso

    if payload.get("is_active") is None:
        payload["is_active"] = True

    return payload


def _payload_to_note_response(note_id: UUID, payload: dict) -> NoteResponse:
    payload = _ensure_payload_defaults(payload)

    data: dict = {
        "id": note_id,
        "content": payload.get("content", ""),
        "layer": payload.get("layer", MemoryLayer.FACT.value),
        "category": payload.get("category"),
        "priority": int(payload.get("priority", 100) or 100),
        "confidence": float(payload.get("confidence", 1.0) or 1.0),
        "created_by": payload.get("created_by") or payload.get("source") or "caregiver",
        "expires_at": payload.get("expires_at"),
        "last_verified": payload.get("last_verified"),
        "is_active": bool(payload.get("is_active", True)),
    }

    # created_at 是必填字段；缺失时使用默认补齐（_ensure_payload_defaults）
    if payload.get("created_at") is not None:
        data["created_at"] = payload["created_at"]

    return NoteResponse(**data)


@router.post("", response_model=NoteResponse, status_code=201)
async def create_note(note: NoteCreate) -> NoteResponse:
    """
    创建便利贴

    - **content**: 便利贴内容（必填）
    - **layer**: 记忆层级（默认：fact）
    - **category**: 分类（可选）
    - **priority**: 优先级，0=最高（默认：100）
    """
    content = note.content.strip()

    # 宪法层：MVP 阶段仍允许创建（用于测试/兼容），但推荐走专用审批流程
    if note.layer == MemoryLayer.CONSTITUTION:
        response = NoteResponse(
            content=content,
            layer=note.layer,
            category=note.category,
            priority=note.priority,
            expires_at=note.expires_at,
            confidence=1.0,
            created_by="caregiver",
        )
        service = get_search_service()
        await to_thread(
            service.index_note,
            note_id=response.id,
            content=response.content,
            layer=response.layer.value,
            category=response.category.value if response.category else None,
            is_active=True,
            confidence=response.confidence,
            source=response.created_by,
            created_by=response.created_by,
            priority=response.priority,
            created_at=response.created_at.isoformat(),
            expires_at=response.expires_at.isoformat() if response.expires_at else None,
        )
        return response

    # 事实层/会话层：复用 Kernel 的写入策略（同步实现，需要 to_thread）
    kernel = get_memory_kernel()
    result = await to_thread(
        kernel.add_memory,
        content=content,
        layer=note.layer.value,
        category=note.category.value if note.category else None,
        source="caregiver",
        confidence=1.0,
        priority=note.priority,
        created_by="caregiver",
        expires_at=note.expires_at,
    )

    if result.get("status") != "saved":
        raise HTTPException(status_code=400, detail=result.get("reason") or "创建失败")

    return NoteResponse(
        id=result["id"],
        content=content,
        layer=note.layer,
        category=note.category,
        priority=note.priority,
        confidence=float(result.get("confidence") or 1.0),
        created_by=str(result.get("created_by") or "caregiver"),
        created_at=result.get("created_at"),
        expires_at=note.expires_at,
        is_active=True,
    )


@router.get("", response_model=list[NoteResponse])
async def list_notes(
    layer: MemoryLayer | None = Query(default=None, description="按记忆层级过滤"),
    category: NoteCategory | None = Query(default=None, description="按分类过滤"),
    active_only: bool = Query(default=True, description="仅显示激活的便利贴"),
    limit: int = Query(default=50, ge=1, le=100, description="返回数量限制"),
) -> list[NoteResponse]:
    """获取便利贴列表"""
    service = get_search_service()
    raw_notes = await to_thread(
        service.list_notes,
        layer=layer.value if layer else None,
        category=category.value if category else None,
        only_active=active_only,
        limit=_MAX_SCAN_NOTES,
    )

    notes: list[NoteResponse] = []
    for r in raw_notes:
        try:
            note_id = UUID(str(r.get("id")))
        except Exception:
            continue
        notes.append(_payload_to_note_response(note_id, r))

    # 按优先级排序（0=最高）
    notes.sort(key=lambda n: n.priority)
    return notes[:limit]


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(note_id: UUID) -> NoteResponse:
    """获取单个便利贴"""
    service = get_search_service()
    raw = await to_thread(service.get_note, note_id)
    if not raw:
        raise HTTPException(status_code=404, detail="便利贴不存在")
    return _payload_to_note_response(note_id, raw)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(note_id: UUID, note: NoteUpdate) -> NoteResponse:
    """更新便利贴"""
    service = get_search_service()
    raw = await to_thread(service.get_note, note_id)
    if not raw:
        raise HTTPException(status_code=404, detail="便利贴不存在")

    existing_payload = _ensure_payload_defaults(dict(raw))

    update_data = note.model_dump(exclude_unset=True)

    # 宪法层需要二次确认（TODO: 实现确认机制）
    if existing_payload.get("layer") == MemoryLayer.CONSTITUTION.value and update_data:
        pass  # MVP 阶段暂不实现

    if "content" in update_data:
        if update_data["content"] is None or not str(update_data["content"]).strip():
            raise HTTPException(status_code=400, detail="content 不能为空")
        existing_payload["content"] = str(update_data["content"]).strip()

    if "category" in update_data:
        if update_data["category"] is None:
            existing_payload["category"] = None
        else:
            existing_payload["category"] = update_data["category"].value

    if "priority" in update_data and update_data["priority"] is not None:
        existing_payload["priority"] = int(update_data["priority"])

    if "expires_at" in update_data:
        if update_data["expires_at"] is None:
            existing_payload.pop("expires_at", None)
        else:
            existing_payload["expires_at"] = update_data["expires_at"].isoformat()

    if "is_active" in update_data and update_data["is_active"] is not None:
        existing_payload["is_active"] = bool(update_data["is_active"])

    await to_thread(
        service.index_note,
        note_id=note_id,
        content=str(existing_payload.get("content", "")),
        layer=str(existing_payload.get("layer", MemoryLayer.FACT.value)),
        category=existing_payload.get("category"),
        is_active=bool(existing_payload.get("is_active", True)),
        confidence=existing_payload.get("confidence"),
        source=existing_payload.get("source"),
        agent_id=existing_payload.get("agent_id"),
        created_at=existing_payload.get("created_at"),
        expires_at=existing_payload.get("expires_at"),
        priority=existing_payload.get("priority"),
        created_by=existing_payload.get("created_by"),
        last_verified=existing_payload.get("last_verified"),
    )

    return _payload_to_note_response(note_id, existing_payload)


@router.delete("/{note_id}", status_code=204)
async def delete_note(note_id: UUID) -> None:
    """删除便利贴（软删除）"""
    service = get_search_service()
    raw = await to_thread(service.get_note, note_id)
    if not raw:
        raise HTTPException(status_code=404, detail="便利贴不存在")
    await to_thread(service.update_note_status, note_id, False)
