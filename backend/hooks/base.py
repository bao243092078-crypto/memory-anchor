"""
Memory Anchor Hook Framework - 基础抽象层

提供统一的 Hook 框架，支持 5 个 Hook 点位：
1. PreToolUse - 工具执行前拦截
2. PostToolUse - 工具执行后处理
3. PermissionRequest - 权限请求
4. SessionStart - 会话开始
5. Stop - 会话结束

学习来源：claude-code-harness 的 Hook 系统
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HookType(Enum):
    """Hook 类型枚举

    基于 Claude Code 的 6 个 Hook 点位：
    - PreToolUse: 工具调用前，可阻止执行
    - PostToolUse: 工具调用后，可添加提醒/建议
    - PermissionRequest: 权限请求时
    - SessionStart: 会话开始时，注入上下文
    - Stop: 会话结束时，生成摘要
    - PreCompact: 上下文压缩前，保存运行时状态（关键！）
    """
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    PERMISSION_REQUEST = "PermissionRequest"
    SESSION_START = "SessionStart"
    STOP = "Stop"
    PRE_COMPACT = "PreCompact"  # 上下文保护核心 Hook


class HookDecision(Enum):
    """Hook 决策类型"""
    ALLOW = "allow"          # 允许继续
    BLOCK = "block"          # 阻止执行
    MODIFY = "modify"        # 修改输入/输出
    NOTIFY = "notify"        # 仅通知，不影响执行


@dataclass
class HookContext:
    """Hook 执行上下文

    Attributes:
        hook_type: Hook 类型
        tool_name: 工具名称（PreToolUse/PostToolUse 时有效）
        tool_input: 工具输入参数
        tool_output: 工具输出（PostToolUse 时有效）
        session_id: 会话 ID
        user_message: 用户最近的消息
        metadata: 额外元数据
    """
    hook_type: HookType
    tool_name: str | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    tool_output: Any = None
    session_id: str | None = None
    user_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HookResult:
    """Hook 执行结果

    Attributes:
        decision: 决策类型
        reason: 决策原因
        message: 显示给用户的消息
        modified_input: 修改后的输入（decision=MODIFY 时使用）
        modified_output: 修改后的输出（PostToolUse + MODIFY 时使用）
        metadata: 额外元数据
    """
    decision: HookDecision = HookDecision.ALLOW
    reason: str | None = None
    message: str | None = None
    modified_input: dict[str, Any] | None = None
    modified_output: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def allow(cls, reason: str | None = None) -> HookResult:
        """创建允许结果"""
        return cls(decision=HookDecision.ALLOW, reason=reason)

    @classmethod
    def block(cls, reason: str, message: str | None = None) -> HookResult:
        """创建阻止结果"""
        return cls(
            decision=HookDecision.BLOCK,
            reason=reason,
            message=message or reason
        )

    @classmethod
    def notify(cls, message: str, reason: str | None = None) -> HookResult:
        """创建通知结果"""
        return cls(
            decision=HookDecision.NOTIFY,
            reason=reason,
            message=message
        )

    @classmethod
    def modify(
        cls,
        modified_input: dict[str, Any] | None = None,
        modified_output: Any = None,
        reason: str | None = None
    ) -> HookResult:
        """创建修改结果"""
        return cls(
            decision=HookDecision.MODIFY,
            reason=reason,
            modified_input=modified_input,
            modified_output=modified_output
        )


class BaseHook(ABC):
    """Hook 基类

    所有 Hook 实现必须继承此类并实现：
    - hook_type: 返回此 Hook 处理的类型
    - name: Hook 名称（用于日志和调试）
    - execute(): 执行 Hook 逻辑

    可选重写：
    - priority: Hook 优先级（数字越小越先执行，默认 100）
    - should_run(): 判断是否应该执行此 Hook
    """

    @property
    @abstractmethod
    def hook_type(self) -> HookType:
        """返回此 Hook 处理的类型"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Hook 名称"""
        pass

    @property
    def priority(self) -> int:
        """执行优先级，数字越小越先执行"""
        return 100

    def should_run(self, context: HookContext) -> bool:
        """判断是否应该执行此 Hook

        默认返回 True。子类可重写实现条件执行。

        Args:
            context: Hook 执行上下文

        Returns:
            是否应该执行
        """
        return True

    @abstractmethod
    def execute(self, context: HookContext) -> HookResult:
        """执行 Hook 逻辑

        Args:
            context: Hook 执行上下文

        Returns:
            Hook 执行结果
        """
        pass


__all__ = [
    "HookType",
    "HookDecision",
    "HookContext",
    "HookResult",
    "BaseHook",
]
