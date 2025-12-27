"""
MCP Memory Service Backend - 基于 mcp-memory-service 的记忆后端实现

这是 MemoryBackend 接口的 mcp-memory-service 实现。
通过 HTTP 调用运行中的 mcp-memory-service FastMCP 服务。

优点：
- 支持多客户端并发访问（无锁问题）
- 与其他 Claude Code 实例共享记忆
- 自带持久化

参考 API：
- store_memory: 存储记忆
- retrieve_memory: 语义搜索
- search_by_tag: 按标签搜索
- delete_memory: 删除记忆
"""

import os
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import httpx

from backend.services.memory_backend import (
    AbstractMemoryBackend,
    MemoryCategory,
    MemoryItem,
    MemoryLayer,
)


class McpMemoryServiceBackend(AbstractMemoryBackend):
    """
    基于 mcp-memory-service 的记忆后端

    特点：
    - 通过 HTTP 调用 FastMCP 服务
    - 支持多客户端并发
    - 使用 content_hash 作为 ID
    """

    DEFAULT_BASE_URL = "http://localhost:3333"

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0
    ):
        """
        初始化 MCP Memory Service 后端

        Args:
            base_url: MCP Memory Service 的 HTTP 地址，默认 http://localhost:3333
            timeout: HTTP 请求超时时间（秒）
        """
        self.base_url = base_url or os.getenv(
            "MCP_MEMORY_SERVICE_URL",
            self.DEFAULT_BASE_URL
        )
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """延迟初始化 HTTP 客户端"""
        if self._client is None:
            if not self.base_url:
                raise ValueError("base_url must be set for MCP Memory Service backend")
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout
            )
        return self._client

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _call_tool(self, tool_name: str, arguments: dict) -> dict:
        """
        调用 MCP 工具

        FastMCP HTTP 端点格式：
        POST /api/mcp/tools/call
        Body: {"name": "tool_name", "arguments": {...}}
        """
        try:
            response = await self.client.post(
                "/api/mcp/tools/call",
                json={
                    "name": tool_name,
                    "arguments": arguments
                }
            )
            response.raise_for_status()
            data: dict[str, object] = response.json()
            return dict(data)
        except httpx.HTTPError as e:
            # 返回空结果而非抛异常，保持与 Qdrant 后端一致的行为
            return {"error": str(e), "success": False}

    def _layer_to_tags(self, layer: Optional[str], category: Optional[str]) -> list[str]:
        """将 layer 和 category 转换为 tags"""
        tags = []
        if layer:
            try:
                layer_value = MemoryLayer.from_string(layer).value
            except ValueError:
                layer_value = str(layer)
            tags.append(f"layer:{layer_value}")
        if category:
            tags.append(f"category:{category}")
        return tags

    def _tags_to_layer_category(self, tags: list[str]) -> tuple[Optional[str], Optional[str]]:
        """从 tags 中提取 layer 和 category"""
        layer = None
        category = None
        for tag in tags:
            if tag.startswith("layer:"):
                raw = tag.split(":", 1)[1]
                try:
                    layer = MemoryLayer.from_string(raw).value
                except ValueError:
                    layer = raw
            elif tag.startswith("category:"):
                category = tag.split(":", 1)[1]
        return layer, category

    async def _do_search(
        self,
        query: str,
        layer: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10
    ) -> list[dict]:
        """
        执行语义搜索

        使用 retrieve_memory API
        """
        # 空查询时使用通用关键词
        search_query = query if query else "记忆"

        result = await self._call_tool("retrieve_memory", {
            "query": search_query,
            "n_results": limit,
            "min_similarity": 0.3
        })

        if result.get("error"):
            return []

        memories = result.get("memories", [])

        # 按 layer/category 过滤
        filtered = []
        for mem in memories:
            mem_tags = mem.get("tags", [])
            mem_layer, mem_category = self._tags_to_layer_category(mem_tags)

            # 如果指定了 layer，只返回匹配的
            if layer and mem_layer != layer:
                continue
            # 如果指定了 category，只返回匹配的
            if category and mem_category != category:
                continue

            filtered.append({
                "id": mem.get("content_hash", str(uuid4())),
                "content": mem.get("content", ""),
                "layer": mem_layer or "fact",
                "category": mem_category,
                "score": mem.get("similarity", 0.0),
                "source": mem.get("metadata", {}).get("source"),
                "confidence": mem.get("metadata", {}).get("confidence", 1.0),
                "metadata": mem.get("metadata", {})
            })

        return filtered

    async def _do_index(
        self,
        memory_id: UUID,
        content: str,
        layer: str,
        category: Optional[str],
        metadata: dict
    ) -> bool:
        """
        执行存储

        使用 store_memory API
        """
        tags = self._layer_to_tags(layer, category)

        # 添加额外标签
        if metadata.get("tags"):
            tags.extend(metadata["tags"])

        result = await self._call_tool("store_memory", {
            "content": content,
            "tags": tags,
            "memory_type": "note",  # 固定类型
            "metadata": {
                **metadata,
                "memory_anchor_id": str(memory_id),
                "layer": layer,
                "category": category
            }
        })

        return bool(result.get("success", False))

    async def _do_delete(self, memory_id: UUID) -> bool:
        """
        执行删除

        使用 delete_memory API（需要 content_hash）

        注意：mcp-memory-service 使用 content_hash 作为 ID，
        而我们的 MemoryItem 使用 UUID。这里假设 memory_id
        实际上存储的是 content_hash。
        """
        result = await self._call_tool("delete_memory", {
            "content_hash": str(memory_id)
        })

        return bool(result.get("success", False))

    async def get_by_id(self, memory_id: UUID) -> Optional[MemoryItem]:
        """
        根据 ID 获取记忆

        mcp-memory-service 没有直接按 ID 查询的 API，
        使用 search_by_tag 配合 memory_anchor_id 查询
        """
        # 尝试通过 metadata 中的 memory_anchor_id 搜索
        result = await self._call_tool("retrieve_memory", {
            "query": str(memory_id),
            "n_results": 1,
            "min_similarity": 0.0
        })

        if result.get("error"):
            return None

        memories = result.get("memories", [])
        for mem in memories:
            # 检查 metadata 中的 ID 是否匹配
            if mem.get("metadata", {}).get("memory_anchor_id") == str(memory_id):
                mem_tags = mem.get("tags", [])
                mem_layer, mem_category = self._tags_to_layer_category(mem_tags)
                try:
                    layer = MemoryLayer.from_string(mem_layer or "fact")
                except ValueError:
                    layer = MemoryLayer.FACT

                return MemoryItem(
                    id=memory_id,
                    content=mem.get("content", ""),
                    layer=layer,
                    category=MemoryCategory(mem_category) if mem_category else None,
                    confidence=mem.get("metadata", {}).get("confidence", 1.0),
                    score=1.0,
                    source=mem.get("metadata", {}).get("source"),
                    metadata=mem.get("metadata", {})
                )

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

        mcp-memory-service 没有时间线 API，使用搜索代替
        """
        results = await self._do_search(
            query="记忆",
            limit=limit
        )

        return [
            self._dict_to_memory_item(r)
            for r in results
        ]

    async def health_check(self) -> dict:
        """
        健康检查

        使用 check_database_health API
        """
        result = await self._call_tool("check_database_health", {})

        return {
            "backend": "mcp-memory-service",
            "base_url": self.base_url,
            "healthy": result.get("success", False),
            "details": result
        }

    def get_stats(self) -> dict:
        """获取后端统计信息"""
        return {
            "backend": "mcp-memory-service",
            "base_url": self.base_url
        }


# 全局单例
_mcp_memory_backend: Optional[McpMemoryServiceBackend] = None


def get_mcp_memory_backend() -> McpMemoryServiceBackend:
    """获取 MCP Memory Service 后端单例"""
    global _mcp_memory_backend
    if _mcp_memory_backend is None:
        _mcp_memory_backend = McpMemoryServiceBackend()
    return _mcp_memory_backend


__all__ = ["McpMemoryServiceBackend", "get_mcp_memory_backend"]
