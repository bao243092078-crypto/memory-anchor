"""
Tests for Hook Framework (base.py and registry.py).

测试 Hook 基础框架的核心功能：
- HookType 枚举
- HookResult 工厂方法
- HookContext 数据类
- HookRegistry 注册和执行
"""

import pytest

from backend.hooks import (
    BaseHook,
    GatingHook,
    HookContext,
    HookDecision,
    HookResult,
    HookType,
    get_hook_registry,
    reset_hook_registry,
)
from backend.hooks.registry import HookRegistry


class TestHookType:
    """测试 HookType 枚举"""

    def test_all_hook_types_defined(self):
        """验证所有 5 个 Hook 类型已定义"""
        assert HookType.PRE_TOOL_USE.value == "PreToolUse"
        assert HookType.POST_TOOL_USE.value == "PostToolUse"
        assert HookType.PERMISSION_REQUEST.value == "PermissionRequest"
        assert HookType.SESSION_START.value == "SessionStart"
        assert HookType.STOP.value == "Stop"

    def test_hook_type_count(self):
        """验证 Hook 类型数量"""
        assert len(HookType) == 5


class TestHookDecision:
    """测试 HookDecision 枚举"""

    def test_all_decisions_defined(self):
        """验证所有决策类型已定义"""
        assert HookDecision.ALLOW.value == "allow"
        assert HookDecision.BLOCK.value == "block"
        assert HookDecision.MODIFY.value == "modify"
        assert HookDecision.NOTIFY.value == "notify"


class TestHookResult:
    """测试 HookResult 数据类和工厂方法"""

    def test_allow_factory(self):
        """测试 allow() 工厂方法"""
        result = HookResult.allow("test reason")
        assert result.decision == HookDecision.ALLOW
        assert result.reason == "test reason"
        assert result.message is None

    def test_block_factory(self):
        """测试 block() 工厂方法"""
        result = HookResult.block("危险操作", "请确认后重试")
        assert result.decision == HookDecision.BLOCK
        assert result.reason == "危险操作"
        assert result.message == "请确认后重试"

    def test_block_factory_default_message(self):
        """测试 block() 默认使用 reason 作为 message"""
        result = HookResult.block("需要确认")
        assert result.message == "需要确认"

    def test_notify_factory(self):
        """测试 notify() 工厂方法"""
        result = HookResult.notify("操作完成", "success")
        assert result.decision == HookDecision.NOTIFY
        assert result.message == "操作完成"
        assert result.reason == "success"

    def test_modify_factory(self):
        """测试 modify() 工厂方法"""
        result = HookResult.modify(
            modified_input={"key": "new_value"},
            reason="参数已修改"
        )
        assert result.decision == HookDecision.MODIFY
        assert result.modified_input == {"key": "new_value"}
        assert result.reason == "参数已修改"


class TestHookContext:
    """测试 HookContext 数据类"""

    def test_minimal_context(self):
        """测试最小上下文"""
        context = HookContext(hook_type=HookType.PRE_TOOL_USE)
        assert context.hook_type == HookType.PRE_TOOL_USE
        assert context.tool_name is None
        assert context.tool_input == {}
        assert context.tool_output is None

    def test_full_context(self):
        """测试完整上下文"""
        context = HookContext(
            hook_type=HookType.POST_TOOL_USE,
            tool_name="search_memory",
            tool_input={"query": "test"},
            tool_output={"results": []},
            session_id="session-123",
            user_message="搜索一下",
            metadata={"extra": "data"}
        )
        assert context.tool_name == "search_memory"
        assert context.tool_input == {"query": "test"}
        assert context.tool_output == {"results": []}
        assert context.session_id == "session-123"
        assert context.user_message == "搜索一下"
        assert context.metadata == {"extra": "data"}


class MockHook(BaseHook):
    """测试用 Mock Hook"""

    def __init__(self, name: str = "MockHook", priority: int = 100, result: HookResult | None = None):
        self._name = name
        self._priority = priority
        self._result = result or HookResult.allow()

    @property
    def hook_type(self) -> HookType:
        return HookType.PRE_TOOL_USE

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    def execute(self, context: HookContext) -> HookResult:
        return self._result


class TestHookRegistry:
    """测试 HookRegistry"""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """每个测试前重置注册中心"""
        reset_hook_registry()
        yield
        reset_hook_registry()

    def test_register_hook(self):
        """测试注册 Hook"""
        registry = HookRegistry()
        hook = MockHook("TestHook")
        registry.register(hook)

        hooks = registry.get_hooks(HookType.PRE_TOOL_USE)
        assert len(hooks) == 1
        assert hooks[0].name == "TestHook"

    def test_unregister_hook(self):
        """测试注销 Hook"""
        registry = HookRegistry()
        hook = MockHook("TestHook")
        registry.register(hook)

        result = registry.unregister(hook)
        assert result is True
        assert len(registry.get_hooks(HookType.PRE_TOOL_USE)) == 0

    def test_unregister_by_name(self):
        """测试按名称注销 Hook"""
        registry = HookRegistry()
        registry.register(MockHook("Hook1"))
        registry.register(MockHook("Hook2"))

        count = registry.unregister_by_name("Hook1")
        assert count == 1
        hooks = registry.get_hooks(HookType.PRE_TOOL_USE)
        assert len(hooks) == 1
        assert hooks[0].name == "Hook2"

    def test_hooks_sorted_by_priority(self):
        """测试 Hook 按优先级排序"""
        registry = HookRegistry()
        registry.register(MockHook("Low", priority=100))
        registry.register(MockHook("High", priority=10))
        registry.register(MockHook("Medium", priority=50))

        hooks = registry.get_hooks(HookType.PRE_TOOL_USE)
        assert [h.name for h in hooks] == ["High", "Medium", "Low"]

    def test_execute_all_hooks(self):
        """测试执行所有 Hook"""
        registry = HookRegistry()
        registry.register(MockHook("Hook1"))
        registry.register(MockHook("Hook2"))

        context = HookContext(hook_type=HookType.PRE_TOOL_USE)
        results = registry.execute(HookType.PRE_TOOL_USE, context)

        assert len(results) == 2

    def test_execute_stops_on_block(self):
        """测试遇到 BLOCK 时停止执行"""
        registry = HookRegistry()
        registry.register(MockHook("Blocker", priority=10, result=HookResult.block("blocked")))
        registry.register(MockHook("AfterBlocker", priority=20))

        context = HookContext(hook_type=HookType.PRE_TOOL_USE)
        results = registry.execute(HookType.PRE_TOOL_USE, context, stop_on_block=True)

        # 只有第一个 Hook 执行了
        assert len(results) == 1
        assert results[0].decision == HookDecision.BLOCK

    def test_execute_continues_without_stop_on_block(self):
        """测试不停止时继续执行"""
        registry = HookRegistry()
        registry.register(MockHook("Blocker", priority=10, result=HookResult.block("blocked")))
        registry.register(MockHook("AfterBlocker", priority=20))

        context = HookContext(hook_type=HookType.PRE_TOOL_USE)
        results = registry.execute(HookType.PRE_TOOL_USE, context, stop_on_block=False)

        # 两个 Hook 都执行了
        assert len(results) == 2

    def test_execute_single_returns_block(self):
        """测试 execute_single 返回 BLOCK 结果"""
        registry = HookRegistry()
        registry.register(MockHook("Allow", priority=10))
        registry.register(MockHook("Blocker", priority=20, result=HookResult.block("blocked")))

        context = HookContext(hook_type=HookType.PRE_TOOL_USE)
        result = registry.execute_single(HookType.PRE_TOOL_USE, context)

        assert result.decision == HookDecision.BLOCK

    def test_execute_single_returns_allow_when_all_allow(self):
        """测试所有 ALLOW 时返回 ALLOW"""
        registry = HookRegistry()
        registry.register(MockHook("Allow1"))
        registry.register(MockHook("Allow2"))

        context = HookContext(hook_type=HookType.PRE_TOOL_USE)
        result = registry.execute_single(HookType.PRE_TOOL_USE, context)

        assert result.decision == HookDecision.ALLOW

    def test_execute_single_empty_registry(self):
        """测试空注册中心返回 ALLOW"""
        registry = HookRegistry()
        context = HookContext(hook_type=HookType.PRE_TOOL_USE)
        result = registry.execute_single(HookType.PRE_TOOL_USE, context)

        assert result.decision == HookDecision.ALLOW

    def test_stats(self):
        """测试统计信息"""
        registry = HookRegistry()
        registry.register(MockHook("Hook1"))
        registry.register(MockHook("Hook2"))

        stats = registry.stats()
        assert stats.get("PreToolUse") == 2

    def test_clear_specific_type(self):
        """测试清除特定类型"""
        registry = HookRegistry()
        registry.register(MockHook("Hook1"))

        registry.clear(HookType.PRE_TOOL_USE)
        assert len(registry.get_hooks(HookType.PRE_TOOL_USE)) == 0

    def test_clear_all(self):
        """测试清除所有"""
        registry = HookRegistry()
        registry.register(MockHook("Hook1"))

        registry.clear()
        assert registry.stats() == {}


class TestGlobalRegistry:
    """测试全局注册中心"""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """每个测试前重置注册中心"""
        reset_hook_registry()
        yield
        reset_hook_registry()

    def test_singleton(self):
        """测试单例模式"""
        r1 = get_hook_registry()
        r2 = get_hook_registry()
        assert r1 is r2

    def test_reset_creates_new_instance(self):
        """测试重置后创建新实例"""
        r1 = get_hook_registry()
        r1.register(MockHook("Test"))

        reset_hook_registry()
        r2 = get_hook_registry()

        assert r1 is not r2
        assert len(r2.get_hooks(HookType.PRE_TOOL_USE)) == 0


class TestGatingHookIntegration:
    """测试 GatingHook 与新框架的集成"""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """每个测试前重置注册中心"""
        reset_hook_registry()
        yield
        reset_hook_registry()

    def test_gating_hook_properties(self):
        """测试 GatingHook 属性"""
        hook = GatingHook()
        assert hook.hook_type == HookType.PRE_TOOL_USE
        assert hook.name == "GatingHook"
        assert hook.priority == 10

    def test_gating_hook_should_run_memory_anchor_tool(self):
        """测试 should_run 识别 memory-anchor 工具"""
        hook = GatingHook()
        context = HookContext(
            hook_type=HookType.PRE_TOOL_USE,
            tool_name="mcp__memory-anchor__delete_memory"
        )
        assert hook.should_run(context) is True

    def test_gating_hook_should_not_run_other_tool(self):
        """测试 should_run 忽略其他工具"""
        hook = GatingHook()
        context = HookContext(
            hook_type=HookType.PRE_TOOL_USE,
            tool_name="other_tool"
        )
        assert hook.should_run(context) is False

    def test_gating_hook_blocks_without_confirmation(self):
        """测试无确认时阻止"""
        hook = GatingHook()
        context = HookContext(
            hook_type=HookType.PRE_TOOL_USE,
            tool_name="delete_memory",
            tool_input={"note_id": "123"}
        )
        result = hook.execute(context)
        assert result.decision == HookDecision.BLOCK

    def test_gating_hook_allows_with_confirmation(self):
        """测试有确认时放行"""
        hook = GatingHook()
        context = HookContext(
            hook_type=HookType.PRE_TOOL_USE,
            tool_name="delete_memory",
            tool_input={"note_id": "123"},
            user_message="确认删除这条记忆"
        )
        result = hook.execute(context)
        assert result.decision == HookDecision.ALLOW

    def test_register_and_execute_gating_hook(self):
        """测试注册并执行 GatingHook"""
        registry = get_hook_registry()
        registry.register(GatingHook())

        context = HookContext(
            hook_type=HookType.PRE_TOOL_USE,
            tool_name="mcp__memory-anchor__delete_memory",
            tool_input={"note_id": "123"}
        )

        result = registry.execute_single(HookType.PRE_TOOL_USE, context)
        assert result.decision == HookDecision.BLOCK
