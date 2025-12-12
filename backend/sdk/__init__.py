"""
Memory Anchor SDK - Native Python API

这个包提供 Memory Anchor 的原生 Python 接口，
供 Codex 等外部 AI 直接调用（无需 MCP 协议）。

核心类：
- MemoryClient: 记忆访问客户端（同步接口）
"""

from backend.sdk.memory_client import MemoryClient

__all__ = ["MemoryClient"]
