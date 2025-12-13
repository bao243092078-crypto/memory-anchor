"""
Search service for Memory Anchor.
使用 Qdrant 向量数据库实现语义搜索。

支持两种模式：
1. Server 模式（推荐）：通过 HTTP 访问独立的 Qdrant Server，支持并发
2. 本地模式：使用本地文件存储，单进程独占

配置来源（优先级从高到低）：
1. 环境变量（QDRANT_URL, MCP_MEMORY_PROJECT_ID）
2. ~/.memory-anchor/projects/{project}/config.yaml
3. ~/.memory-anchor/config.yaml
4. 代码默认值

启动 Qdrant Server：
    docker run -d -p 6333:6333 -v $(pwd)/.qdrant_data:/qdrant/storage:z --name qdrant qdrant/qdrant
"""
from typing import List, Optional
from uuid import UUID

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
)

from backend.config import get_config
from backend.services.embedding import embed_text, embed_batch


def _get_collection_name() -> str:
    """
    获取当前项目的 collection 名称（通过配置）。

    物理隔离策略：
    - project_name=alzheimer → collection = memory_anchor_notes_alzheimer
    - project_name=dev_test → collection = memory_anchor_notes_dev_test
    - project_name=default → collection = memory_anchor_notes（向后兼容）

    Returns:
        collection 名称，只包含 [a-zA-Z0-9_-]
    """
    config = get_config()
    return config.collection_name


# 向后兼容：保留 COLLECTION_NAME 变量（运行时计算）
# 注意：这个变量可能在 SearchService 创建前就被访问，所以保留
def _lazy_collection_name() -> str:
    """延迟获取 collection 名称"""
    return _get_collection_name()


# 为了向后兼容，COLLECTION_NAME 作为模块级别的动态属性
# 实际使用时应通过 _get_collection_name() 或 SearchService.collection_name
COLLECTION_NAME = _get_collection_name()

# 向后兼容：测试/外部代码可能使用 VECTOR_SIZE 常量
VECTOR_SIZE = get_config().vector_size


def _get_qdrant_client(
    local_path: Optional[str] = None,
    server_url: Optional[str] = None,
    prefer_server: bool = True,
) -> tuple[QdrantClient, str]:
    """
    获取 Qdrant 客户端，优先尝试 Server 模式。

    Args:
        local_path: 本地存储路径（None 则使用配置）
        server_url: Qdrant Server URL（None 则使用配置）
        prefer_server: 是否优先尝试 Server 模式

    Returns:
        (client, mode) - client 实例和模式字符串 ("server" 或 "local")
    """
    config = get_config()

    # 使用配置中的值作为默认
    actual_local_path = local_path or str(config.qdrant_path)
    actual_server_url = server_url or config.qdrant_url or "http://localhost:6333"

    if prefer_server:
        try:
            # 快速探测 Qdrant Server 是否可用
            with httpx.Client(timeout=0.5) as http_client:
                resp = http_client.get(f"{actual_server_url}/readyz")
                if resp.status_code == 200:
                    return QdrantClient(url=actual_server_url), "server"
        except Exception:
            pass

    # 降级到本地模式
    return QdrantClient(path=actual_local_path), "local"


class SearchService:
    """语义搜索服务"""

    def __init__(
        self,
        path: Optional[str] = None,
        url: Optional[str] = None,
        prefer_server: bool = True,
    ):
        """
        初始化搜索服务。

        配置优先级：
        1. 构造函数参数（显式传入）
        2. 配置文件（~/.memory-anchor/）
        3. 环境变量
        4. 代码默认值

        Args:
            path: Qdrant 本地数据存储路径（None 则使用配置）
            url: Qdrant Server URL（显式指定则只用 Server 模式）
            prefer_server: 是否优先尝试 Server 模式
        """
        self._config = get_config()
        self.collection_name = self._config.collection_name
        self.vector_size = self._config.vector_size

        if url:
            # 显式指定 URL，直接使用 Server 模式
            self.client = QdrantClient(url=url)
            self.mode = "server"
        else:
            # 自动检测（使用配置或参数）
            self.client, self.mode = _get_qdrant_client(
                local_path=path,
                server_url=self._config.qdrant_url,
                prefer_server=prefer_server,
            )
        self._ensure_collection()

    def _ensure_collection(self):
        """确保 collection 存在"""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )

    def index_note(
        self,
        note_id: UUID,
        content: str,
        layer: str,
        category: Optional[str] = None,
        is_active: bool = True,
        confidence: Optional[float] = None,
        source: Optional[str] = None,
        agent_id: Optional[str] = None,
        created_at: Optional[str] = None,
        expires_at: Optional[str] = None,
        priority: Optional[int] = None,
        created_by: Optional[str] = None,
        last_verified: Optional[str] = None,
    ) -> bool:
        """
        索引一条便利贴到向量数据库。

        Args:
            note_id: 便利贴 ID
            content: 便利贴内容
            layer: 记忆层级 (constitution/fact/session)
            category: 类别 (person/place/event/item/routine)
            is_active: 是否激活
            confidence: 置信度（可选，0-1）
            source: 来源标记（可选）
            agent_id: 会话层隔离用 agent_id（可选）
            created_at: ISO 时间字符串（可选）
            expires_at: ISO 时间字符串（可选）

        Returns:
            是否成功
        """
        vector = embed_text(content)

        payload: dict = {
            "content": content,
            "layer": layer,
            "category": category,
            "is_active": is_active,
        }
        if confidence is not None:
            payload["confidence"] = confidence
        if source is not None:
            payload["source"] = source
        if agent_id is not None:
            payload["agent_id"] = agent_id
        if created_at is not None:
            payload["created_at"] = created_at
        if expires_at is not None:
            payload["expires_at"] = expires_at
        if priority is not None:
            payload["priority"] = priority
        if created_by is not None:
            payload["created_by"] = created_by
        if last_verified is not None:
            payload["last_verified"] = last_verified

        point = PointStruct(
            id=str(note_id),
            vector=vector,
            payload=payload,
        )

        self.client.upsert(
            collection_name=self.collection_name,
            points=[point],
        )

        return True

    def index_notes_batch(
        self,
        notes: List[dict],
    ) -> int:
        """
        批量索引便利贴。

        Args:
            notes: 便利贴列表，每个包含 id, content, layer, category, is_active

        Returns:
            成功索引的数量
        """
        if not notes:
            return 0

        contents = [n["content"] for n in notes]
        vectors = embed_batch(contents)

        points = [
            PointStruct(
                id=str(n["id"]),
                vector=vec,
                payload={
                    "content": n["content"],
                    "layer": n["layer"],
                    "category": n.get("category"),
                    "is_active": n.get("is_active", True),
                    **({"confidence": n["confidence"]} if n.get("confidence") is not None else {}),
                    **({"source": n["source"]} if n.get("source") is not None else {}),
                    **({"agent_id": n["agent_id"]} if n.get("agent_id") is not None else {}),
                    **({"created_at": n["created_at"]} if n.get("created_at") is not None else {}),
                    **({"expires_at": n["expires_at"]} if n.get("expires_at") is not None else {}),
                },
            )
            for n, vec in zip(notes, vectors)
        ]

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

        return len(points)

    def search(
        self,
        query: str,
        limit: int = 5,
        layer: Optional[str] = None,
        category: Optional[str] = None,
        only_active: bool = True,
        agent_id: Optional[str] = None,
    ) -> List[dict]:
        """
        语义搜索便利贴。

        Args:
            query: 搜索查询
            limit: 返回数量限制
            layer: 过滤记忆层级
            category: 过滤类别
            only_active: 是否只返回激活的
            agent_id: 会话层隔离用 agent_id（仅当 layer=session 时生效）

        Returns:
            搜索结果列表，包含 id, content, score, layer, category
        """
        query_vector = embed_text(query)

        # 构建过滤条件
        must_conditions = []

        if only_active:
            must_conditions.append(
                FieldCondition(key="is_active", match=MatchValue(value=True))
            )

        if layer:
            must_conditions.append(
                FieldCondition(key="layer", match=MatchValue(value=layer))
            )

        if category:
            must_conditions.append(
                FieldCondition(key="category", match=MatchValue(value=category))
            )

        # 会话层隔离：仅在显式查询 session 层时启用
        if agent_id and layer == "session":
            must_conditions.append(
                FieldCondition(key="agent_id", match=MatchValue(value=agent_id))
            )

        query_filter = Filter(must=must_conditions) if must_conditions else None

        # 使用新版 Qdrant API: query_points
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
        )

        return [
            {
                "id": r.id,
                "content": r.payload.get("content", ""),
                "score": min(1.0, max(0.0, r.score)),  # clamp to [0, 1]
                "layer": r.payload.get("layer"),
                "category": r.payload.get("category"),
                "is_active": r.payload.get("is_active", True),
                "confidence": r.payload.get("confidence"),
                "source": r.payload.get("source"),
                "created_by": r.payload.get("created_by"),
                "priority": r.payload.get("priority"),
                "agent_id": r.payload.get("agent_id"),
                "created_at": r.payload.get("created_at"),
                "expires_at": r.payload.get("expires_at"),
                "last_verified": r.payload.get("last_verified"),
            }
            for r in results.points
        ]

    def list_notes(
        self,
        *,
        layer: Optional[str] = None,
        category: Optional[str] = None,
        only_active: bool = True,
        limit: int = 50,
    ) -> List[dict]:
        """
        列出便利贴（不做向量检索）。

        用于：
        - 宪法层全量预加载（不依赖 top-k 检索）
        - 后续 CRUD / 分页等

        Args:
            layer: 过滤记忆层级
            category: 过滤类别
            only_active: 是否只返回激活的
            limit: 返回数量限制

        Returns:
            列表结果，包含 id, content, layer, category 等 payload 字段
        """
        must_conditions = []

        if only_active:
            must_conditions.append(
                FieldCondition(key="is_active", match=MatchValue(value=True))
            )
        if layer:
            must_conditions.append(
                FieldCondition(key="layer", match=MatchValue(value=layer))
            )
        if category:
            must_conditions.append(
                FieldCondition(key="category", match=MatchValue(value=category))
            )

        scroll_filter = Filter(must=must_conditions) if must_conditions else None
        records, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=scroll_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return [
            {
                "id": r.id,
                "content": (r.payload or {}).get("content", ""),
                "layer": (r.payload or {}).get("layer"),
                "category": (r.payload or {}).get("category"),
                "is_active": (r.payload or {}).get("is_active", True),
                "confidence": (r.payload or {}).get("confidence"),
                "source": (r.payload or {}).get("source"),
                "created_by": (r.payload or {}).get("created_by"),
                "priority": (r.payload or {}).get("priority"),
                "agent_id": (r.payload or {}).get("agent_id"),
                "created_at": (r.payload or {}).get("created_at"),
                "expires_at": (r.payload or {}).get("expires_at"),
                "last_verified": (r.payload or {}).get("last_verified"),
            }
            for r in records
        ]

    def get_note(self, note_id: UUID) -> Optional[dict]:
        """
        获取单条便利贴（payload 读取）。

        Args:
            note_id: 便利贴 ID

        Returns:
            dict 或 None
        """
        points = self.client.retrieve(
            collection_name=self.collection_name,
            ids=[str(note_id)],
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            return None

        point = points[0]
        payload = point.payload or {}
        return {
            "id": point.id,
            "content": payload.get("content", ""),
            "layer": payload.get("layer"),
            "category": payload.get("category"),
            "is_active": payload.get("is_active", True),
            "confidence": payload.get("confidence"),
            "source": payload.get("source"),
            "created_by": payload.get("created_by"),
            "priority": payload.get("priority"),
            "agent_id": payload.get("agent_id"),
            "created_at": payload.get("created_at"),
            "expires_at": payload.get("expires_at"),
            "last_verified": payload.get("last_verified"),
        }

    def update_note(self, note_id: UUID, payload: dict) -> bool:
        """
        更新便利贴（重建向量 + 覆盖 payload）。

        Args:
            note_id: 便利贴 ID
            payload: 要写入的字段（允许部分字段；缺失字段会从现有记录补齐）

        Returns:
            是否成功
        """
        existing = self.get_note(note_id)
        merged: dict = dict(existing or {})
        merged.update(payload or {})
        merged.pop("id", None)

        created_at = merged.get("created_at")
        if hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()

        expires_at = merged.get("expires_at")
        if hasattr(expires_at, "isoformat"):
            expires_at = expires_at.isoformat()

        last_verified = merged.get("last_verified")
        if hasattr(last_verified, "isoformat"):
            last_verified = last_verified.isoformat()

        confidence = merged.get("confidence")
        confidence_value = float(confidence) if confidence is not None else None

        priority = merged.get("priority")
        priority_value = int(priority) if priority is not None else None

        return self.index_note(
            note_id=note_id,
            content=str(merged.get("content", "")),
            layer=str(merged.get("layer") or "fact"),
            category=merged.get("category"),
            is_active=bool(merged.get("is_active", True)),
            confidence=confidence_value,
            source=merged.get("source"),
            agent_id=merged.get("agent_id"),
            created_at=created_at,
            expires_at=expires_at,
            priority=priority_value,
            created_by=merged.get("created_by"),
            last_verified=last_verified,
        )

    def delete_note(self, note_id: UUID) -> bool:
        """
        从索引中删除便利贴。

        Args:
            note_id: 便利贴 ID

        Returns:
            是否成功
        """
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=[str(note_id)],
        )
        return True

    def update_note_status(self, note_id: UUID, is_active: bool) -> bool:
        """
        更新便利贴的激活状态。

        Args:
            note_id: 便利贴 ID
            is_active: 是否激活

        Returns:
            是否成功
        """
        self.client.set_payload(
            collection_name=self.collection_name,
            payload={"is_active": is_active},
            points=[str(note_id)],
        )
        return True

    def get_stats(self) -> dict:
        """
        获取索引统计信息。

        Returns:
            统计信息，包含 total_count, vector_size, collection_name, mode 等
        """
        info = self.client.get_collection(self.collection_name)
        return {
            "total_count": info.points_count,
            "vector_size": info.config.params.vectors.size,
            "distance": info.config.params.vectors.distance.value,
            "collection_name": self.collection_name,
            "mode": self.mode,
            "project_name": self._config.project_name,
        }


# 全局单例
_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """获取搜索服务单例"""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service


# 导出
__all__ = ["SearchService", "get_search_service"]
