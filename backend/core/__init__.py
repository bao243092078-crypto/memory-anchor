"""
Memory Anchor Core - 核心引擎

这个包包含 Memory Anchor 的核心逻辑，独立于任何特定的接入方式（MCP/SDK）。

核心类：
- MemoryKernel: 记忆管理核心引擎（同步版本）
"""

from backend.core.memory_kernel import MemoryKernel

__all__ = ["MemoryKernel"]
