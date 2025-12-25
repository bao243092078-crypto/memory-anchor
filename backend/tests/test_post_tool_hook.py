"""
Tests for PostToolUse Hook.

测试工具执行后处理：
- 文件修改检测
- 测试文件识别
- 会话摘要生成
"""

import pytest

from backend.hooks import (
    HookContext,
    HookDecision,
    HookType,
    PostToolHook,
    extract_modified_files,
    get_hook_registry,
    is_source_file,
    is_test_file,
    reset_hook_registry,
)


class TestFileDetection:
    """测试文件类型检测"""

    def test_is_test_file_python(self):
        """测试 Python 测试文件识别"""
        assert is_test_file("test_example.py") is True
        assert is_test_file("example_test.py") is True
        assert is_test_file("tests/test_foo.py") is True
        assert is_test_file("backend/tests/test_hook.py") is True

    def test_is_test_file_javascript(self):
        """测试 JavaScript 测试文件识别"""
        assert is_test_file("example.test.ts") is True
        assert is_test_file("example.test.js") is True
        assert is_test_file("example.spec.ts") is True
        assert is_test_file("example.spec.js") is True
        assert is_test_file("__tests__/example.ts") is True

    def test_is_not_test_file(self):
        """测试非测试文件"""
        assert is_test_file("main.py") is False
        assert is_test_file("app.ts") is False
        assert is_test_file("utils.js") is False
        assert is_test_file("config.yaml") is False

    def test_is_source_file(self):
        """测试源代码文件识别"""
        assert is_source_file("main.py") is True
        assert is_source_file("app.ts") is True
        assert is_source_file("utils.js") is True
        assert is_source_file("component.tsx") is True
        assert is_source_file("lib.rs") is True
        assert is_source_file("main.go") is True

    def test_is_not_source_file(self):
        """测试非源代码文件"""
        assert is_source_file("config.yaml") is False
        assert is_source_file("README.md") is False
        assert is_source_file("package.json") is False
        assert is_source_file("image.png") is False


class TestExtractModifiedFiles:
    """测试文件路径提取"""

    def test_extract_from_write(self):
        """测试从 Write 工具提取"""
        files = extract_modified_files("Write", {"file_path": "/path/to/file.py"})
        assert files == ["/path/to/file.py"]

    def test_extract_from_edit(self):
        """测试从 Edit 工具提取"""
        files = extract_modified_files("Edit", {"file_path": "/path/to/file.ts"})
        assert files == ["/path/to/file.ts"]

    def test_extract_from_multi_edit(self):
        """测试从 MultiEdit 工具提取"""
        files = extract_modified_files(
            "MultiEdit",
            {
                "edits": [
                    {"file_path": "/path/to/a.py"},
                    {"file_path": "/path/to/b.py"},
                ]
            },
        )
        assert files == ["/path/to/a.py", "/path/to/b.py"]

    def test_extract_empty_on_unknown_tool(self):
        """测试未知工具返回空列表"""
        files = extract_modified_files("Read", {"file_path": "/path/to/file.py"})
        assert files == []


class TestPostToolHook:
    """测试 PostToolHook"""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """每个测试前重置注册中心"""
        reset_hook_registry()
        yield
        reset_hook_registry()

    def test_hook_properties(self):
        """测试 Hook 属性"""
        hook = PostToolHook()
        assert hook.hook_type == HookType.POST_TOOL_USE
        assert hook.name == "PostToolHook"
        assert hook.priority == 50

    def test_should_run_file_modify_tools(self):
        """测试 should_run 识别文件修改工具"""
        hook = PostToolHook()

        for tool in ["Write", "Edit", "MultiEdit", "NotebookEdit"]:
            context = HookContext(
                hook_type=HookType.POST_TOOL_USE,
                tool_name=tool,
            )
            assert hook.should_run(context) is True

    def test_should_run_memory_tools(self):
        """测试 should_run 识别 memory-anchor 工具"""
        hook = PostToolHook()

        context = HookContext(
            hook_type=HookType.POST_TOOL_USE,
            tool_name="mcp__memory-anchor__add_memory",
        )
        assert hook.should_run(context) is True

    def test_should_not_run_other_tools(self):
        """测试 should_run 忽略其他工具"""
        hook = PostToolHook()

        context = HookContext(
            hook_type=HookType.POST_TOOL_USE,
            tool_name="Read",
        )
        assert hook.should_run(context) is False

    def test_execute_file_modification(self):
        """测试执行文件修改处理"""
        hook = PostToolHook()
        context = HookContext(
            hook_type=HookType.POST_TOOL_USE,
            tool_name="Write",
            tool_input={"file_path": "/path/to/main.py"},
        )

        result = hook.execute(context)

        assert result.decision == HookDecision.NOTIFY
        assert "main.py" in result.message

    def test_execute_memory_operation(self):
        """测试执行 memory 操作处理"""
        hook = PostToolHook()
        context = HookContext(
            hook_type=HookType.POST_TOOL_USE,
            tool_name="mcp__memory-anchor__add_memory",
            tool_input={"content": "test memory"},
        )

        result = hook.execute(context)

        assert result.decision == HookDecision.NOTIFY
        assert "add_memory" in result.message

    def test_modified_files_tracking(self):
        """测试文件修改追踪"""
        hook = PostToolHook()

        # 模拟多次文件修改
        for file_path in ["/a.py", "/b.py", "/test_c.py"]:
            context = HookContext(
                hook_type=HookType.POST_TOOL_USE,
                tool_name="Write",
                tool_input={"file_path": file_path},
            )
            hook.execute(context)

        files = hook.get_modified_files()
        assert len(files) == 3

    def test_session_summary(self):
        """测试会话摘要生成"""
        hook = PostToolHook()

        # 修改一个源文件
        hook.execute(
            HookContext(
                hook_type=HookType.POST_TOOL_USE,
                tool_name="Write",
                tool_input={"file_path": "/src/main.py"},
            )
        )

        # 修改一个测试文件
        hook.execute(
            HookContext(
                hook_type=HookType.POST_TOOL_USE,
                tool_name="Write",
                tool_input={"file_path": "/tests/test_main.py"},
            )
        )

        summary = hook.get_session_summary()
        assert summary["total_modifications"] == 2
        assert summary["source_files_modified"] == 1
        assert summary["test_files_modified"] == 1

    def test_clear_history(self):
        """测试清除历史"""
        hook = PostToolHook()

        hook.execute(
            HookContext(
                hook_type=HookType.POST_TOOL_USE,
                tool_name="Write",
                tool_input={"file_path": "/a.py"},
            )
        )

        hook.clear_history()
        assert hook.get_modified_files() == []
        assert hook.get_memory_operations() == []


class TestPostToolHookIntegration:
    """测试 PostToolHook 与 Registry 集成"""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """每个测试前重置注册中心"""
        reset_hook_registry()
        yield
        reset_hook_registry()

    def test_register_and_execute(self):
        """测试注册并执行"""
        registry = get_hook_registry()
        hook = PostToolHook()
        registry.register(hook)

        context = HookContext(
            hook_type=HookType.POST_TOOL_USE,
            tool_name="Write",
            tool_input={"file_path": "/src/app.py"},
        )

        result = registry.execute_single(HookType.POST_TOOL_USE, context)
        assert result.decision == HookDecision.NOTIFY
