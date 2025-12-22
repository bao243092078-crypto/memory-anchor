"""
Memory Anchor Hooks - 钩子系统

提供：
- gating_hook: 高风险操作拦截
"""

from backend.hooks.gating_hook import gate_operation, is_confirmation_present

__all__ = ["gate_operation", "is_confirmation_present"]
