"""
Memory Anchor Hooks - 钩子系统

提供 5 个 Hook 点位的统一框架：
1. PreToolUse - 工具执行前拦截（如 GatingHook）
2. PostToolUse - 工具执行后处理（如测试建议）
3. PermissionRequest - 权限请求
4. SessionStart - 会话开始，注入上下文
5. Stop - 会话结束，生成摘要

用法：
    from backend.hooks import get_hook_registry, GatingHook

    # 注册 Hook
    registry = get_hook_registry()
    registry.register(GatingHook())

    # 执行 Hook
    context = HookContext(hook_type=HookType.PRE_TOOL_USE, tool_name="delete_memory")
    result = registry.execute_single(HookType.PRE_TOOL_USE, context)
"""

from backend.hooks.base import (
    BaseHook,
    HookContext,
    HookDecision,
    HookResult,
    HookType,
)
from backend.hooks.gating_hook import (
    GatingHook,
    gate_operation,
    is_confirmation_present,
)
from backend.hooks.post_tool_hook import (
    PostToolHook,
    extract_modified_files,
    is_source_file,
    is_test_file,
)
from backend.hooks.registry import (
    HookRegistry,
    get_hook_registry,
    reset_hook_registry,
)
from backend.hooks.stop_hook import (
    StopHook,
    generate_session_summary,
    save_session_summary,
)

__all__ = [
    # Base
    "HookType",
    "HookDecision",
    "HookContext",
    "HookResult",
    "BaseHook",
    # Registry
    "HookRegistry",
    "get_hook_registry",
    "reset_hook_registry",
    # Gating Hook (PreToolUse)
    "GatingHook",
    "gate_operation",
    "is_confirmation_present",
    # PostToolUse Hook
    "PostToolHook",
    "extract_modified_files",
    "is_source_file",
    "is_test_file",
    # Stop Hook
    "StopHook",
    "generate_session_summary",
    "save_session_summary",
]
