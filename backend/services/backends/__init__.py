"""
Memory Backends - 可插拔记忆后端

当前支持：
- QdrantMemoryBackend: 基于 Qdrant 向量数据库
- McpMemoryServiceBackend: 基于 mcp-memory-service

规划中：
- MemOSBackend: 基于 MemOS

切换后端：
    export MEMORY_BACKEND=qdrant              # 默认
    export MEMORY_BACKEND=mcp-memory-service  # 切换到 mcp-memory-service
"""

from backend.services.backends.qdrant_backend import (
    QdrantMemoryBackend,
    get_qdrant_backend,
)
from backend.services.backends.mcp_memory_service_backend import (
    McpMemoryServiceBackend,
    get_mcp_memory_backend,
)

__all__ = [
    # Qdrant 后端
    "QdrantMemoryBackend",
    "get_qdrant_backend",
    # MCP Memory Service 后端
    "McpMemoryServiceBackend",
    "get_mcp_memory_backend",
]
