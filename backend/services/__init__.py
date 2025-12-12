"""Business logic services for Memory Anchor"""

from backend.services.embedding import embed_text, embed_batch
from backend.services.search import SearchService, get_search_service

# 可插拔记忆后端抽象（Step 0 完成）
from backend.services.memory_backend import (
    MemoryBackend,
    AbstractMemoryBackend,
    MemoryItem,
    MemoryLayer,
    MemoryCategory,
    SearchRequest,
    AddRequest,
    AddResult,
    get_memory_backend,
    BackendType,
)
from backend.services.backends import (
    QdrantMemoryBackend,
    get_qdrant_backend,
    McpMemoryServiceBackend,
    get_mcp_memory_backend,
)

# TODO: 添加以下服务
# - tts.py: Edge TTS 语音合成
# - reminder.py: 定时提醒服务

__all__ = [
    # Embedding
    "embed_text",
    "embed_batch",
    # Search (底层)
    "SearchService",
    "get_search_service",
    # Memory Backend (抽象层)
    "MemoryBackend",
    "AbstractMemoryBackend",
    "MemoryItem",
    "MemoryLayer",
    "MemoryCategory",
    "SearchRequest",
    "AddRequest",
    "AddResult",
    # 后端工厂（推荐使用）
    "get_memory_backend",
    "BackendType",
    # Backends (具体实现)
    "QdrantMemoryBackend",
    "get_qdrant_backend",
    "McpMemoryServiceBackend",
    "get_mcp_memory_backend",
]
