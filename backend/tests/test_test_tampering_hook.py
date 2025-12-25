"""
Tests for TestTamperingHook (Phase 6).

测试内容：
1. 测试文件检测
2. assert 删除检测
3. 无理由 skip 检测
4. 期望值修改检测
5. 异常吞噬检测
6. Hook 集成测试
"""

import pytest

from backend.hooks.base import HookContext, HookDecision, HookType
from backend.hooks.test_tampering_hook import (
    TestTamperingHook,
    TamperingSeverity,
    TamperingType,
    analyze_test_modification,
    detect_assert_deletion,
    detect_boundary_test_deletion,
    detect_exception_swallowing,
    detect_expected_value_change,
    detect_skip_no_reason,
    is_test_file,
)


class TestIsTestFile:
    """测试文件检测"""

    def test_python_test_prefix(self):
        """测试 test_*.py 模式"""
        assert is_test_file("test_main.py") is True
        assert is_test_file("backend/tests/test_memory.py") is True
        assert is_test_file("/Users/user/project/test_utils.py") is True

    def test_python_test_suffix(self):
        """测试 *_test.py 模式"""
        assert is_test_file("main_test.py") is True
        assert is_test_file("backend/memory_test.py") is True

    def test_tests_directory(self):
        """测试 tests/ 目录"""
        assert is_test_file("tests/conftest.py") is True
        assert is_test_file("backend/tests/helpers.py") is True

    def test_javascript_test_files(self):
        """测试 JS/TS 测试文件"""
        assert is_test_file("app.test.js") is True
        assert is_test_file("app.test.ts") is True
        assert is_test_file("component.spec.tsx") is True
        assert is_test_file("__tests__/app.js") is True

    def test_non_test_files(self):
        """测试非测试文件"""
        assert is_test_file("main.py") is False
        assert is_test_file("backend/services/memory.py") is False
        assert is_test_file("src/app.ts") is False
        assert is_test_file("utils.js") is False


class TestDetectAssertDeletion:
    """assert 删除检测"""

    def test_detect_assert_deletion(self):
        """检测删除 assert"""
        old = """
def test_example():
    result = calculate(10)
    assert result == 100
    assert result > 0
"""
        new = """
def test_example():
    result = calculate(10)
    assert result > 0
"""
        result = detect_assert_deletion(old, new)
        assert result is not None
        assert result.tampering_type == TamperingType.ASSERT_DELETION
        assert result.severity == TamperingSeverity.CRITICAL

    def test_detect_commented_assert(self):
        """检测注释掉 assert"""
        old = """
def test_example():
    assert result == 100
"""
        new = """
def test_example():
    # assert result == 100
"""
        result = detect_assert_deletion(old, new)
        assert result is not None
        assert result.tampering_type == TamperingType.ASSERT_DELETION

    def test_no_deletion(self):
        """无删除时返回 None"""
        old = """
def test_example():
    assert result == 100
"""
        new = """
def test_example():
    assert result == 100
    assert another_value > 0
"""
        result = detect_assert_deletion(old, new)
        assert result is None


class TestDetectSkipNoReason:
    """无理由 skip 检测"""

    def test_detect_skip_no_reason(self):
        """检测无理由 @skip"""
        old = """
def test_critical():
    assert True
"""
        new = """
@pytest.mark.skip
def test_critical():
    assert True
"""
        result = detect_skip_no_reason(old, new)
        assert result is not None
        assert result.tampering_type == TamperingType.SKIP_NO_REASON
        assert result.severity == TamperingSeverity.CRITICAL

    def test_detect_skip_empty_parens(self):
        """检测 @skip() 无参数"""
        old = "def test_foo(): pass"
        new = "@pytest.mark.skip()\ndef test_foo(): pass"

        result = detect_skip_no_reason(old, new)
        assert result is not None
        assert result.tampering_type == TamperingType.SKIP_NO_REASON

    def test_allow_skip_with_reason(self):
        """允许带 reason 的 skip"""
        old = "def test_foo(): pass"
        new = '@pytest.mark.skip(reason="TODO: fix later")\ndef test_foo(): pass'

        result = detect_skip_no_reason(old, new)
        assert result is None


class TestDetectExpectedValueChange:
    """期望值修改检测"""

    def test_detect_numeric_value_change(self):
        """检测数字期望值变更"""
        old = "assert calculate(10) == 100"
        new = "assert calculate(10) == 99"

        result = detect_expected_value_change(old, new)
        assert result is not None
        assert result.tampering_type == TamperingType.EXPECTED_VALUE_CHANGE
        assert result.severity == TamperingSeverity.WARNING

    def test_detect_string_value_change(self):
        """检测字符串期望值变更"""
        old = 'assert get_name() == "Alice"'
        new = 'assert get_name() == "Bob"'

        result = detect_expected_value_change(old, new)
        assert result is not None
        assert result.tampering_type == TamperingType.EXPECTED_VALUE_CHANGE

    def test_no_change(self):
        """无变更时返回 None"""
        old = "assert result == 100"
        new = "assert result == 100"

        result = detect_expected_value_change(old, new)
        assert result is None


class TestDetectExceptionSwallowing:
    """异常吞噬检测"""

    def test_detect_except_pass(self):
        """检测 except: pass"""
        old = "result = risky_operation()"
        new = """
try:
    result = risky_operation()
except:
    pass
"""
        result = detect_exception_swallowing(old, new)
        assert result is not None
        assert result.tampering_type == TamperingType.EXCEPTION_SWALLOWING
        assert result.severity == TamperingSeverity.CRITICAL

    def test_detect_except_exception_pass(self):
        """检测 except Exception: pass"""
        old = "result = risky_operation()"
        new = """
try:
    result = risky_operation()
except Exception:
    pass
"""
        result = detect_exception_swallowing(old, new)
        assert result is not None

    def test_allow_except_with_handling(self):
        """允许有处理逻辑的 except"""
        old = "result = risky_operation()"
        new = """
try:
    result = risky_operation()
except Exception as e:
    logger.error(f"Error: {e}")
    raise
"""
        result = detect_exception_swallowing(old, new)
        assert result is None


class TestDetectBoundaryTestDeletion:
    """边界测试删除检测"""

    def test_detect_boundary_test_deletion(self):
        """检测边界测试删除"""
        old = """
def test_normal_case():
    pass

def test_boundary_values():
    pass
"""
        new = """
def test_normal_case():
    pass
"""
        result = detect_boundary_test_deletion(old, new)
        assert result is not None
        assert result.tampering_type == TamperingType.BOUNDARY_TEST_DELETION
        assert result.severity == TamperingSeverity.CRITICAL

    def test_detect_edge_case_deletion(self):
        """检测 edge case 测试删除"""
        old = """
def test_edge_case_empty():
    pass
"""
        new = ""

        result = detect_boundary_test_deletion(old, new)
        assert result is not None

    def test_no_boundary_deletion(self):
        """无边界测试删除"""
        old = "def test_normal(): pass"
        new = "def test_normal(): pass\ndef test_another(): pass"

        result = detect_boundary_test_deletion(old, new)
        assert result is None


class TestAnalyzeTestModification:
    """综合分析测试"""

    def test_multiple_issues(self):
        """检测多个问题"""
        old = """
def test_boundary_check():
    result = calculate(10)
    assert result == 100
"""
        new = """
@pytest.mark.skip
def test_another():
    try:
        result = calculate(10)
    except:
        pass
"""
        detections = analyze_test_modification(old, new)

        # 应该检测到多个问题
        assert len(detections) >= 2

        types = {d.tampering_type for d in detections}
        assert TamperingType.ASSERT_DELETION in types or TamperingType.SKIP_NO_REASON in types

    def test_no_issues(self):
        """无问题时返回空列表"""
        old = "def test_foo(): assert True"
        new = "def test_foo(): assert True\ndef test_bar(): assert 1 == 1"

        detections = analyze_test_modification(old, new)
        assert len(detections) == 0


class TestTestTamperingHook:
    """Hook 集成测试"""

    @pytest.fixture
    def hook(self):
        return TestTamperingHook()

    def test_should_run_edit_test_file(self, hook):
        """Edit 测试文件应该运行"""
        context = HookContext(
            hook_type=HookType.PRE_TOOL_USE,
            tool_name="Edit",
            tool_input={"file_path": "backend/tests/test_memory.py"},
        )
        assert hook.should_run(context) is True

    def test_should_not_run_non_test_file(self, hook):
        """非测试文件不运行"""
        context = HookContext(
            hook_type=HookType.PRE_TOOL_USE,
            tool_name="Edit",
            tool_input={"file_path": "backend/services/memory.py"},
        )
        assert hook.should_run(context) is False

    def test_should_not_run_read_tool(self, hook):
        """Read 工具不运行"""
        context = HookContext(
            hook_type=HookType.PRE_TOOL_USE,
            tool_name="Read",
            tool_input={"file_path": "backend/tests/test_memory.py"},
        )
        assert hook.should_run(context) is False

    def test_execute_block_on_critical(self, hook):
        """严重问题应该阻止"""
        context = HookContext(
            hook_type=HookType.PRE_TOOL_USE,
            tool_name="Edit",
            tool_input={
                "file_path": "test_example.py",
                "old_string": "assert result == 100",
                "new_string": "# assert result == 100",
            },
        )

        result = hook.execute(context)
        assert result.decision == HookDecision.BLOCK

    def test_execute_warn_on_warning(self, hook):
        """警告问题应该通知"""
        context = HookContext(
            hook_type=HookType.PRE_TOOL_USE,
            tool_name="Edit",
            tool_input={
                "file_path": "test_example.py",
                "old_string": "assert result == 100",
                "new_string": "assert result == 99",
            },
        )

        result = hook.execute(context)
        # 期望值变更是 WARNING 级别，应该是 NOTIFY 而不是 BLOCK
        assert result.decision in (HookDecision.NOTIFY, HookDecision.ALLOW)

    def test_execute_allow_safe_modification(self, hook):
        """安全修改应该允许"""
        context = HookContext(
            hook_type=HookType.PRE_TOOL_USE,
            tool_name="Edit",
            tool_input={
                "file_path": "test_example.py",
                "old_string": "def test_foo(): pass",
                "new_string": "def test_foo():\n    assert True",
            },
        )

        result = hook.execute(context)
        assert result.decision == HookDecision.ALLOW

    def test_hook_properties(self, hook):
        """测试 Hook 属性"""
        assert hook.hook_type == HookType.PRE_TOOL_USE
        assert hook.name == "TestTamperingHook"
        assert hook.priority == 50  # 中等优先级
