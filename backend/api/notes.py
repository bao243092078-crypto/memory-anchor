"""Notes API - 便利贴 CRUD 接口"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from backend.models.note import (
    MemoryLayer,
    NoteCategory,
    NoteCreate,
    NoteResponse,
    NoteUpdate,
)

router = APIRouter(prefix="/notes", tags=["notes"])

# 临时内存存储（MVP 阶段，后续替换为 SQLite + Qdrant）
_notes_db: dict[UUID, NoteResponse] = {}


@router.post("", response_model=NoteResponse, status_code=201)
async def create_note(note: NoteCreate) -> NoteResponse:
    """
    创建便利贴

    - **content**: 便利贴内容（必填）
    - **layer**: 记忆层级（默认：fact）
    - **category**: 分类（可选）
    - **priority**: 优先级，0=最高（默认：100）
    """
    response = NoteResponse(
        content=note.content,
        layer=note.layer,
        category=note.category,
        priority=note.priority,
        expires_at=note.expires_at,
    )
    _notes_db[response.id] = response
    return response


@router.get("", response_model=list[NoteResponse])
async def list_notes(
    layer: MemoryLayer | None = Query(default=None, description="按记忆层级过滤"),
    category: NoteCategory | None = Query(default=None, description="按分类过滤"),
    active_only: bool = Query(default=True, description="仅显示激活的便利贴"),
    limit: int = Query(default=50, ge=1, le=100, description="返回数量限制"),
) -> list[NoteResponse]:
    """获取便利贴列表"""
    notes = list(_notes_db.values())

    # 过滤
    if layer:
        notes = [n for n in notes if n.layer == layer]
    if category:
        notes = [n for n in notes if n.category == category]
    if active_only:
        notes = [n for n in notes if n.is_active]

    # 按优先级排序（0=最高）
    notes.sort(key=lambda n: n.priority)

    return notes[:limit]


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(note_id: UUID) -> NoteResponse:
    """获取单个便利贴"""
    if note_id not in _notes_db:
        raise HTTPException(status_code=404, detail="便利贴不存在")
    return _notes_db[note_id]


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(note_id: UUID, note: NoteUpdate) -> NoteResponse:
    """更新便利贴"""
    if note_id not in _notes_db:
        raise HTTPException(status_code=404, detail="便利贴不存在")

    existing = _notes_db[note_id]
    update_data = note.model_dump(exclude_unset=True)

    # 宪法层需要二次确认（TODO: 实现确认机制）
    if existing.layer == MemoryLayer.CONSTITUTION and update_data:
        pass  # MVP 阶段暂不实现

    updated = existing.model_copy(update=update_data)
    _notes_db[note_id] = updated
    return updated


@router.delete("/{note_id}", status_code=204)
async def delete_note(note_id: UUID) -> None:
    """删除便利贴（软删除）"""
    if note_id not in _notes_db:
        raise HTTPException(status_code=404, detail="便利贴不存在")

    # 软删除：标记为不激活
    _notes_db[note_id] = _notes_db[note_id].model_copy(update={"is_active": False})
