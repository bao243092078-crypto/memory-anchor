"""Notes API - 便利贴 CRUD 接口（Qdrant 持久化）"""

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query

from backend.models.note import (
    MemoryLayer,
    NoteCategory,
    NoteCreate,
    NoteResponse,
    NoteUpdate,
    NoteVerify,
)
from backend.services.notes_service import get_notes_service

router = APIRouter(prefix="/notes", tags=["notes"])

_MAX_SCAN_NOTES = 5000


def _to_response(data: dict) -> NoteResponse:
    """Qdrant payload -> NoteResponse（source → created_by，兼容老数据缺失字段）。"""
    payload = dict(data or {})

    raw_id = payload.get("id")
    try:
        note_id = raw_id if isinstance(raw_id, UUID) else UUID(str(raw_id))
    except Exception:
        note_id = uuid4()

    raw_layer = payload.get("layer") or MemoryLayer.FACT.value
    try:
        layer = raw_layer if isinstance(raw_layer, MemoryLayer) else MemoryLayer(str(raw_layer))
    except ValueError:
        layer = MemoryLayer.FACT

    raw_category = payload.get("category")
    if raw_category is None:
        category = None
    else:
        try:
            category = raw_category if isinstance(raw_category, NoteCategory) else NoteCategory(str(raw_category))
        except ValueError:
            category = None

    raw_priority = payload.get("priority")
    priority = int(raw_priority) if raw_priority is not None else 100

    raw_confidence = payload.get("confidence")
    confidence = float(raw_confidence) if raw_confidence is not None else 0.5

    created_by = payload.get("source") or payload.get("created_by") or "caregiver"

    raw_created_at = payload.get("created_at")
    if raw_created_at is None:
        created_at = datetime.now()
    elif isinstance(raw_created_at, datetime):
        created_at = raw_created_at
    else:
        created_at = datetime.fromisoformat(str(raw_created_at).replace("Z", "+00:00"))

    raw_is_active = payload.get("is_active")
    is_active = bool(raw_is_active) if raw_is_active is not None else True

    return NoteResponse(
        id=note_id,
        content=str(payload.get("content", "")),
        layer=layer,
        category=category,
        priority=priority,
        confidence=confidence,
        created_by=str(created_by),
        created_at=created_at,
        expires_at=payload.get("expires_at"),
        last_verified=payload.get("last_verified"),
        is_active=is_active,
        # v2.1 可追溯性字段
        session_id=payload.get("session_id"),
        related_files=payload.get("related_files"),
    )


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
    service = get_notes_service()
    try:
        created = await service.create(
            content=content,
            layer=note.layer,
            category=note.category,
            priority=note.priority,
            expires_at=note.expires_at,
            created_by="caregiver",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _to_response(created)


@router.get("", response_model=list[NoteResponse])
async def list_notes(
    layer: str | None = Query(default=None, description="按记忆层级过滤（支持 v1.x: constitution/fact/session）"),
    category: NoteCategory | None = Query(default=None, description="按分类过滤"),
    active_only: bool = Query(default=True, description="仅显示激活的便利贴"),
    limit: int = Query(default=50, ge=1, le=100, description="返回数量限制"),
) -> list[NoteResponse]:
    """获取便利贴列表"""
    # 转换层级（支持 v1.x 旧术语）
    layer_enum = MemoryLayer.from_string(layer) if layer else None

    service = get_notes_service()
    raw_notes = await service.list(
        layer=layer_enum,
        category=category,
        active_only=active_only,
        limit=_MAX_SCAN_NOTES,
    )

    notes: list[NoteResponse] = []
    for r in raw_notes:
        try:
            notes.append(_to_response(r))
        except Exception:
            continue

    # 按优先级排序（0=最高）
    notes.sort(key=lambda n: n.priority)
    return notes[:limit]


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(note_id: UUID) -> NoteResponse:
    """获取单个便利贴"""
    service = get_notes_service()
    raw = await service.get(note_id)
    if not raw:
        raise HTTPException(status_code=404, detail="便利贴不存在")
    return _to_response(raw)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(note_id: UUID, note: NoteUpdate) -> NoteResponse:
    """更新便利贴"""
    service = get_notes_service()
    update_data = note.model_dump(exclude_unset=True)
    kwargs: dict = {}
    if "content" in update_data:
        kwargs["content"] = update_data["content"]
    if "category" in update_data:
        kwargs["category"] = update_data["category"]
    if "priority" in update_data:
        kwargs["priority"] = update_data["priority"]
    if "expires_at" in update_data:
        kwargs["expires_at"] = update_data["expires_at"]
    if "is_active" in update_data:
        kwargs["is_active"] = update_data["is_active"]
    # v2.1 可追溯性字段
    if "session_id" in update_data:
        kwargs["session_id"] = update_data["session_id"]
    if "related_files" in update_data:
        kwargs["related_files"] = update_data["related_files"]

    try:
        updated = await service.update(note_id, **kwargs)
    except KeyError:
        raise HTTPException(status_code=404, detail="便利贴不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _to_response(updated)


@router.post("/{note_id}/verify", response_model=NoteResponse)
async def verify_note(note_id: UUID, body: NoteVerify) -> NoteResponse:
    """
    确认记忆（将 confidence 设为 1.0）

    用于人工确认 AI 提取的记忆，消除 ⚠️ 警告标记。
    """
    service = get_notes_service()

    try:
        # 更新 confidence 为 1.0，并记录确认时间
        updated = await service.update(
            note_id,
            confidence=1.0,
            last_verified=datetime.now(),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="记忆不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _to_response(updated)


@router.delete("/{note_id}", status_code=204)
async def delete_note(note_id: UUID) -> None:
    """删除便利贴（软删除）"""
    service = get_notes_service()
    try:
        await service.delete(note_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="便利贴不存在")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
