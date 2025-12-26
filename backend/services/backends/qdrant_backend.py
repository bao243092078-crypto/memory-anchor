"""
Qdrant Memory Backend - 基于 Qdrant 向量数据库的记忆后端实现

这是 MemoryBackend 接口的 Qdrant 实现。
复用现有的 SearchService，但遵循新的抽象接口。
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from backend.services.memory_backend import (
    AbstractMemoryBackend,
    MemoryCategory,
    MemoryItem,
    MemoryLayer,
)
from backend.services.search import SearchService, get_search_service


class QdrantMemoryBackend(AbstractMemoryBackend):
    """
    基于 Qdrant 的记忆后端

    特点：
    - 语义搜索（向量相似度）
    - 支持 Server 和 Local 两种模式
    - 自动降级
    """

    def __init__(self, search_service: Optional[SearchService] = None):
        """
        初始化 Qdrant 后端

        Args:
            search_service: 可选的 SearchService 实例，不传则使用全局单例
        """
        self._search_service = search_service

    @property
    def search_service(self) -> SearchService:
        """延迟获取 SearchService"""
        if self._search_service is None:
            self._search_service = get_search_service()
        return self._search_service

    async def _do_search(
        self,
        query: str,
        layer: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10
    ) -> list[dict]:
        """执行 Qdrant 搜索"""
        # 空查询时使用通用关键词
        search_query = query if query else "记忆"

        return self.search_service.search(
            query=search_query,
            layer=layer,
            category=category,
            limit=limit,
            only_active=True
        )

    async def _do_index(
        self,
        memory_id: UUID,
        content: str,
        layer: str,
        category: Optional[str],
        metadata: dict
    ) -> bool:
        """执行 Qdrant 索引"""
        return self.search_service.index_note(
            note_id=memory_id,
            content=content,
            layer=layer,
            category=category,
            is_active=True
        )

    async def _do_delete(self, memory_id: UUID) -> bool:
        """执行 Qdrant 删除"""
        return self.search_service.delete_note(memory_id)

    async def get_by_id(self, memory_id: UUID) -> Optional[MemoryItem]:
        """
        根据 ID 获取记忆

        注意：Qdrant 的 ID 查询需要直接访问 client
        """
        try:
            # 使用 Qdrant client 直接获取
            points = self.search_service.client.retrieve(
                collection_name=self.search_service.collection_name,
                ids=[str(memory_id)],
                with_payload=True
            )

            if not points:
                return None

            point = points[0]
            # Handle point.id which can be int | str | UUID
            if isinstance(point.id, UUID):
                point_id = point.id
            else:
                point_id = UUID(str(point.id))

            # Handle payload which might be None
            payload = point.payload or {}

            return MemoryItem(
                id=point_id,
                content=payload.get("content", ""),
                layer=MemoryLayer(payload.get("layer", "fact")),
                category=MemoryCategory(payload["category"]) if payload.get("category") else None,
                confidence=payload.get("confidence", 1.0),
                score=1.0,
                source=payload.get("source"),
                metadata=payload
            )
        except Exception:
            return None

    async def delete(self, memory_id: UUID) -> bool:
        """删除记忆"""
        return await self._do_delete(memory_id)

    async def get_timeline(
        self,
        since: Optional[datetime] = None,
        limit: int = 20
    ) -> list[MemoryItem]:
        """
        获取最近记忆

        注意：当前实现不支持按时间过滤（需要在 payload 中存储 created_at）
        暂时返回全部记忆
        """
        # 使用通用关键词搜索获取最近记忆
        results = self.search_service.search(
            query="记忆",
            limit=limit,
            only_active=True
        )

        return [
            self._dict_to_memory_item(r)
            for r in results
        ]

    def get_stats(self) -> dict:
        """获取后端统计信息"""
        stats = self.search_service.get_stats()
        stats["backend"] = "qdrant"
        stats["mode"] = self.search_service.mode
        return stats


# 全局单例
_qdrant_backend: Optional[QdrantMemoryBackend] = None


def get_qdrant_backend() -> QdrantMemoryBackend:
    """获取 Qdrant 后端单例"""
    global _qdrant_backend
    if _qdrant_backend is None:
        _qdrant_backend = QdrantMemoryBackend()
    return _qdrant_backend


__all__ = ["QdrantMemoryBackend", "get_qdrant_backend"]
