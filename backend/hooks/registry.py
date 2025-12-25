"""
Memory Anchor Hook Registry - Hook 注册中心

职责：
1. 管理所有已注册的 Hook
2. 按类型和优先级执行 Hook
3. 合并多个 Hook 的结果

用法：
    from backend.hooks import get_hook_registry

    registry = get_hook_registry()
    registry.register(MyCustomHook())

    # 执行 PreToolUse hooks
    results = registry.execute(HookType.PRE_TOOL_USE, context)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from backend.hooks.base import (
    BaseHook,
    HookContext,
    HookDecision,
    HookResult,
    HookType,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class HookRegistry:
    """Hook 注册中心

    管理所有 Hook 的注册、注销和执行。
    Hook 按优先级排序执行，数字越小越先执行。
    """

    def __init__(self):
        """初始化注册中心"""
        self._hooks: dict[HookType, list[BaseHook]] = defaultdict(list)
        self._sorted: dict[HookType, bool] = defaultdict(lambda: True)

    def register(self, hook: BaseHook) -> None:
        """注册 Hook

        Args:
            hook: Hook 实例
        """
        hook_type = hook.hook_type
        self._hooks[hook_type].append(hook)
        self._sorted[hook_type] = False
        logger.debug(f"Registered hook: {hook.name} (type={hook_type.value}, priority={hook.priority})")

    def unregister(self, hook: BaseHook) -> bool:
        """注销 Hook

        Args:
            hook: Hook 实例

        Returns:
            是否成功注销
        """
        hook_type = hook.hook_type
        if hook in self._hooks[hook_type]:
            self._hooks[hook_type].remove(hook)
            logger.debug(f"Unregistered hook: {hook.name}")
            return True
        return False

    def unregister_by_name(self, name: str, hook_type: HookType | None = None) -> int:
        """按名称注销 Hook

        Args:
            name: Hook 名称
            hook_type: 可选，指定类型

        Returns:
            注销的 Hook 数量
        """
        count = 0
        types_to_check = [hook_type] if hook_type else list(HookType)

        for ht in types_to_check:
            hooks_to_remove = [h for h in self._hooks[ht] if h.name == name]
            for hook in hooks_to_remove:
                self._hooks[ht].remove(hook)
                count += 1

        if count > 0:
            logger.debug(f"Unregistered {count} hook(s) with name: {name}")

        return count

    def get_hooks(self, hook_type: HookType) -> list[BaseHook]:
        """获取指定类型的所有 Hook（按优先级排序）

        Args:
            hook_type: Hook 类型

        Returns:
            Hook 列表（按优先级排序）
        """
        if not self._sorted[hook_type]:
            self._hooks[hook_type].sort(key=lambda h: h.priority)
            self._sorted[hook_type] = True

        return list(self._hooks[hook_type])

    def execute(
        self,
        hook_type: HookType,
        context: HookContext,
        stop_on_block: bool = True
    ) -> list[HookResult]:
        """执行指定类型的所有 Hook

        Args:
            hook_type: Hook 类型
            context: 执行上下文
            stop_on_block: 遇到 BLOCK 决策时是否停止执行后续 Hook

        Returns:
            所有 Hook 的执行结果列表
        """
        hooks = self.get_hooks(hook_type)
        results: list[HookResult] = []

        for hook in hooks:
            try:
                # 检查是否应该执行
                if not hook.should_run(context):
                    logger.debug(f"Hook {hook.name} skipped (should_run=False)")
                    continue

                # 执行 Hook
                result = hook.execute(context)
                results.append(result)

                logger.debug(
                    f"Hook {hook.name} executed: decision={result.decision.value}, "
                    f"reason={result.reason}"
                )

                # 如果遇到 BLOCK 且配置了 stop_on_block，停止执行
                if stop_on_block and result.decision == HookDecision.BLOCK:
                    logger.info(f"Hook chain stopped by {hook.name}: {result.reason}")
                    break

            except Exception as e:
                logger.error(f"Hook {hook.name} error: {e}", exc_info=True)
                # Hook 出错不阻止执行，继续下一个 Hook
                results.append(HookResult.notify(
                    message=f"Hook {hook.name} error: {e}",
                    reason="hook_error"
                ))

        return results

    def execute_single(
        self,
        hook_type: HookType,
        context: HookContext
    ) -> HookResult:
        """执行并合并所有 Hook 结果

        便捷方法，返回单个合并后的结果：
        - 如果任何 Hook 返回 BLOCK，最终结果为 BLOCK
        - 否则返回最后一个非 ALLOW 的结果
        - 如果全部 ALLOW，返回 ALLOW

        Args:
            hook_type: Hook 类型
            context: 执行上下文

        Returns:
            合并后的单个结果
        """
        results = self.execute(hook_type, context, stop_on_block=True)

        if not results:
            return HookResult.allow()

        # 检查是否有 BLOCK
        for result in results:
            if result.decision == HookDecision.BLOCK:
                return result

        # 检查是否有 MODIFY
        for result in reversed(results):
            if result.decision == HookDecision.MODIFY:
                return result

        # 检查是否有 NOTIFY
        for result in reversed(results):
            if result.decision == HookDecision.NOTIFY:
                return result

        # 全部 ALLOW
        return HookResult.allow()

    def clear(self, hook_type: HookType | None = None) -> None:
        """清除已注册的 Hook

        Args:
            hook_type: 可选，指定类型。如果不指定则清除所有。
        """
        if hook_type:
            self._hooks[hook_type].clear()
            self._sorted[hook_type] = True
        else:
            self._hooks.clear()
            self._sorted.clear()

    def stats(self) -> dict[str, int]:
        """获取统计信息

        Returns:
            {hook_type: count} 字典
        """
        return {ht.value: len(hooks) for ht, hooks in self._hooks.items() if hooks}


# === 全局单例 ===

_registry: HookRegistry | None = None


def get_hook_registry() -> HookRegistry:
    """获取全局 Hook 注册中心

    Returns:
        HookRegistry 单例
    """
    global _registry
    if _registry is None:
        _registry = HookRegistry()
    return _registry


def reset_hook_registry() -> None:
    """重置全局注册中心（用于测试）"""
    global _registry
    _registry = None


__all__ = [
    "HookRegistry",
    "get_hook_registry",
    "reset_hook_registry",
]
