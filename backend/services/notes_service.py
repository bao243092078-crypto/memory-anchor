"""
Notes Service - Notes API 的业务层（async wrapper）

FastAPI 层是 async，而 MemoryKernel/SearchService 为同步实现。
这里统一使用 asyncio.to_thread 做异步包装，确保数据源统一为 Qdrant。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from backend.core.memory_kernel import MemoryKernel, MemorySource, get_memory_kernel
from backend.models.note import MemoryLayer, NoteCategory

_UNSET = object()


class NotesService:
    """便利贴 CRUD 服务（基于 MemoryKernel/SearchService）。"""

    def __init__(self, kernel: MemoryKernel | None = None):
        self._kernel = kernel or get_memory_kernel()

    @property
    def kernel(self) -> MemoryKernel:
        return self._kernel

    @staticmethod
    def _ensure_payload_defaults(payload: dict) -> dict:
        """为历史数据补齐字段（用于更新/写回）。"""
        now_iso = datetime.now().isoformat()
        data = dict(payload)

        data.setdefault("layer", MemoryLayer.FACT.value)
        if data.get("priority") is None:
            data["priority"] = 100
        if data.get("confidence") is None:
            data["confidence"] = 0.5

        source = data.get("source") or data.get("created_by") or MemorySource.CAREGIVER.value
        data.setdefault("source", source)
        data.setdefault("created_by", data.get("created_by") or source)

        if data.get("created_at") is None:
            data["created_at"] = now_iso

        if data.get("is_active") is None:
            data["is_active"] = True

        return data

    async def create(
        self,
        *,
        content: str,
        layer: MemoryLayer,
        category: NoteCategory | None = None,
        priority: int = 100,
        expires_at: datetime | None = None,
        created_by: str = MemorySource.CAREGIVER.value,
    ) -> dict:
        content = content.strip()

        # 宪法层：绕过 Kernel 的红线保护，仅用于兼容/测试场景（写入 Qdrant）
        if layer == MemoryLayer.CONSTITUTION:
            note_id = uuid4()
            created_at = datetime.now().isoformat()
            await asyncio.to_thread(
                self.kernel.search.index_note,
                note_id=note_id,
                content=content,
                layer=layer.value,
                category=category.value if category else None,
                is_active=True,
                confidence=1.0,
                source=created_by,
                created_by=created_by,
                priority=priority,
                created_at=created_at,
                expires_at=expires_at.isoformat() if expires_at else None,
            )
            return {
                "id": note_id,
                "content": content,
                "layer": layer.value,
                "category": category.value if category else None,
                "priority": priority,
                "confidence": 1.0,
                "source": created_by,
                "created_by": created_by,
                "created_at": created_at,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "is_active": True,
            }

        result = await asyncio.to_thread(
            self.kernel.add_memory,
            content=content,
            layer=layer.value,
            category=category.value if category else None,
            source=MemorySource.CAREGIVER.value,
            confidence=1.0,
            priority=priority,
            created_by=created_by,
            expires_at=expires_at,
        )

        if result.get("status") != "saved":
            raise ValueError(result.get("reason") or "创建失败")

        return {
            "id": result["id"],
            "content": content,
            "layer": layer.value,
            "category": category.value if category else None,
            "priority": priority,
            "confidence": float(result["confidence"]) if result.get("confidence") is not None else 1.0,
            "source": MemorySource.CAREGIVER.value,
            "created_by": str(result.get("created_by") or created_by),
            "created_at": result.get("created_at"),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "is_active": True,
        }

    async def list(
        self,
        *,
        layer: MemoryLayer | None = None,
        category: NoteCategory | None = None,
        active_only: bool = True,
        limit: int = 50,
    ) -> list[dict]:
        return await asyncio.to_thread(
            self.kernel.search.list_notes,
            layer=layer.value if layer else None,
            category=category.value if category else None,
            only_active=active_only,
            limit=limit,
        )

    async def get(self, note_id: UUID) -> Optional[dict]:
        return await asyncio.to_thread(self.kernel.search.get_note, note_id)

    async def update(
        self,
        note_id: UUID,
        *,
        content: str | None | object = _UNSET,
        category: NoteCategory | None | object = _UNSET,
        priority: int | None | object = _UNSET,
        expires_at: datetime | None | object = _UNSET,
        is_active: bool | None | object = _UNSET,
    ) -> dict:
        raw = await self.get(note_id)
        if not raw:
            raise KeyError("note not found")

        payload = self._ensure_payload_defaults(raw)

        if content is not _UNSET:
            if content is None or not str(content).strip():
                raise ValueError("content 不能为空")
            payload["content"] = str(content).strip()

        if category is not _UNSET:
            if category is None:
                payload["category"] = None
            else:
                payload["category"] = category.value if isinstance(category, NoteCategory) else str(category)

        if priority is not _UNSET and priority is not None:
            payload["priority"] = int(priority) if isinstance(priority, (int, float, str)) else priority

        if expires_at is not _UNSET:
            if expires_at is None:
                payload.pop("expires_at", None)
            else:
                payload["expires_at"] = (
                    expires_at.isoformat() if isinstance(expires_at, datetime) else str(expires_at)
                )

        if is_active is not _UNSET and is_active is not None:
            payload["is_active"] = bool(is_active)

        await asyncio.to_thread(self.kernel.search.update_note, note_id, payload)
        return payload

    async def delete(self, note_id: UUID) -> bool:
        raw = await self.get(note_id)
        if not raw:
            raise KeyError("note not found")
        return await asyncio.to_thread(self.kernel.search.update_note_status, note_id, False)


_notes_service: Optional[NotesService] = None


def get_notes_service() -> NotesService:
    """获取 NotesService 单例"""
    global _notes_service
    if _notes_service is None:
        _notes_service = NotesService()
    return _notes_service

