"""
Tests for Stop Hook.

Phase 3 增强测试：
- 会话摘要生成
- TODO/FIXME 提取
- Memory Anchor 写入
- StateManager 集成
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.hooks import (
    HookContext,
    HookDecision,
    HookType,
    PostToolHook,
    StopHook,
    extract_todos_from_file,
    extract_todos_from_files,
    generate_memory_content,
    generate_session_summary,
    get_hook_registry,
    reset_hook_registry,
)


class TestGenerateSessionSummary:
    """测试会话摘要生成"""

    def test_minimal_summary(self):
        """测试最小摘要"""
        summary = generate_session_summary(session_id="test-123")

        assert summary["session_id"] == "test-123"
        assert "ended_at" in summary
        assert summary["statistics"]["total_file_modifications"] == 0
        assert summary["statistics"]["memory_operations"] == 0

    def test_summary_with_files(self):
        """测试包含文件修改的摘要"""
        modified_files = [
            {"file": "/src/main.py", "is_source": True, "is_test": False},
            {"file": "/src/utils.py", "is_source": True, "is_test": False},
            {"file": "/tests/test_main.py", "is_source": True, "is_test": True},
        ]

        summary = generate_session_summary(
            session_id="test-456",
            modified_files=modified_files,
        )

        assert summary["statistics"]["total_file_modifications"] == 3
        assert summary["statistics"]["source_files_modified"] == 2
        assert summary["statistics"]["test_files_modified"] == 1
        assert "/src/main.py" in summary["files"]["source"]
        assert "/tests/test_main.py" in summary["files"]["test"]

    def test_summary_with_memory_operations(self):
        """测试包含 memory 操作的摘要"""
        memory_ops = [
            {"tool": "add_memory", "timestamp": "2025-01-01T00:00:00"},
            {"tool": "search_memory", "timestamp": "2025-01-01T00:01:00"},
        ]

        summary = generate_session_summary(
            session_id="test-789",
            memory_operations=memory_ops,
        )

        assert summary["statistics"]["memory_operations"] == 2
        assert len(summary["memory_operations"]) == 2

    def test_summary_with_metadata(self):
        """测试包含元数据的摘要"""
        metadata = {"user": "test-user", "project": "test-project"}

        summary = generate_session_summary(
            session_id="test-meta",
            metadata=metadata,
        )

        assert summary["metadata"]["user"] == "test-user"
        assert summary["metadata"]["project"] == "test-project"

    def test_summary_with_todos(self):
        """测试包含未完成任务的摘要"""
        todos = [
            {"type": "TODO", "content": "Implement feature X", "file": "/src/main.py", "line": 10},
            {"type": "FIXME", "content": "Fix bug Y", "file": "/src/utils.py", "line": 20},
        ]

        summary = generate_session_summary(
            session_id="test-todos",
            todos=todos,
        )

        assert summary["statistics"]["unfinished_tasks"] == 2
        assert len(summary["unfinished_tasks"]) == 2
        assert summary["unfinished_tasks"][0]["type"] == "TODO"


class TestExtractTodos:
    """测试 TODO 提取功能"""

    def test_extract_python_todos(self):
        """测试从 Python 文件提取 TODO"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""
# TODO: Implement this function
def foo():
    pass

# FIXME: This is broken
def bar():
    return None

# XXX: Review this code
# HACK: Temporary workaround
""")
            f.flush()

            todos = extract_todos_from_file(f.name)

            assert len(todos) >= 4
            types = [t["type"] for t in todos]
            assert "TODO" in types
            assert "FIXME" in types
            assert "XXX" in types
            assert "HACK" in types

            Path(f.name).unlink()

    def test_extract_javascript_todos(self):
        """测试从 JavaScript 文件提取 TODO"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write("""
// TODO: Add error handling
function foo() {
    return null;
}

// FIXME: Memory leak here
// BUG: Race condition
""")
            f.flush()

            todos = extract_todos_from_file(f.name)

            assert len(todos) >= 3
            types = [t["type"] for t in todos]
            assert "TODO" in types
            assert "FIXME" in types
            assert "BUG" in types

            Path(f.name).unlink()

    def test_extract_todos_nonexistent_file(self):
        """测试不存在的文件"""
        todos = extract_todos_from_file("/nonexistent/file.py")
        assert todos == []

    def test_extract_todos_unsupported_extension(self):
        """测试不支持的文件类型"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("# TODO: This should be ignored\n")
            f.flush()

            todos = extract_todos_from_file(f.name)
            assert todos == []

            Path(f.name).unlink()

    def test_extract_todos_from_multiple_files(self):
        """测试从多个文件提取 TODO"""
        files = []
        try:
            for i in range(3):
                f = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
                f.write(f"# TODO: Task {i}\n")
                f.flush()
                f.close()
                files.append(f.name)

            todos = extract_todos_from_files(files)

            assert len(todos) == 3
            contents = [t["content"] for t in todos]
            assert "Task 0" in contents[0]
        finally:
            for f in files:
                Path(f).unlink()

    def test_extract_todos_deduplication(self):
        """测试 TODO 去重"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# TODO: Same task\n")
            f.flush()

            # Pass the same file twice
            todos = extract_todos_from_files([f.name, f.name])

            # Should be deduplicated
            assert len(todos) == 1

            Path(f.name).unlink()


class TestGenerateMemoryContent:
    """测试记忆内容生成"""

    def test_minimal_content(self):
        """测试最小内容"""
        summary = generate_session_summary(session_id="mem-test")
        content = generate_memory_content(summary)

        assert "mem-test" in content
        assert "结束" in content

    def test_content_with_files(self):
        """测试包含文件修改的内容"""
        summary = generate_session_summary(
            session_id="file-test",
            modified_files=[
                {"file": "/src/a.py", "is_source": True, "is_test": False},
                {"file": "/src/b.py", "is_source": True, "is_test": False},
            ],
        )
        content = generate_memory_content(summary)

        assert "2 个源文件" in content

    def test_content_with_todos(self):
        """测试包含 TODO 的内容"""
        summary = generate_session_summary(
            session_id="todo-test",
            todos=[
                {"type": "TODO", "content": "Task 1", "file": "/a.py", "line": 1},
                {"type": "FIXME", "content": "Task 2", "file": "/b.py", "line": 2},
            ],
        )
        content = generate_memory_content(summary)

        assert "2 个未完成任务" in content


class TestStopHook:
    """测试 StopHook"""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """每个测试前重置注册中心"""
        reset_hook_registry()
        yield
        reset_hook_registry()

    def test_hook_properties(self):
        """测试 Hook 属性"""
        hook = StopHook()
        assert hook.hook_type == HookType.STOP
        assert hook.name == "StopHook"
        assert hook.priority == 100

    def test_execute_without_post_tool_hook(self):
        """测试无 PostToolHook 时执行"""
        hook = StopHook(auto_write_memory=False)  # 禁用 Memory 写入避免依赖

        context = HookContext(
            hook_type=HookType.STOP,
            session_id="stop-test",
        )

        result = hook.execute(context)

        assert result.decision == HookDecision.NOTIFY
        assert "会话摘要" in result.message

    def test_execute_with_post_tool_hook(self):
        """测试有 PostToolHook 时执行"""
        post_hook = PostToolHook()

        # 模拟文件修改
        post_hook.execute(
            HookContext(
                hook_type=HookType.POST_TOOL_USE,
                tool_name="Write",
                tool_input={"file_path": "/src/main.py"},
            )
        )

        stop_hook = StopHook(post_tool_hook=post_hook, auto_write_memory=False)

        context = HookContext(
            hook_type=HookType.STOP,
            session_id="integrated-test",
        )

        result = stop_hook.execute(context)

        assert result.decision == HookDecision.NOTIFY
        assert "源文件: 1" in result.message

    def test_set_post_tool_hook(self):
        """测试设置 PostToolHook"""
        stop_hook = StopHook()
        post_hook = PostToolHook()

        stop_hook.set_post_tool_hook(post_hook)

        # 验证已设置
        assert stop_hook._post_tool_hook is post_hook

    def test_format_summary_message(self):
        """测试摘要消息格式化"""
        stop_hook = StopHook()

        summary = {
            "statistics": {
                "total_file_modifications": 5,
                "source_files_modified": 3,
                "test_files_modified": 2,
                "memory_operations": 1,
            },
            "files": {
                "source": ["/a.py", "/b.py", "/c.py"],
                "test": ["/test_a.py", "/test_b.py"],
            },
            "unfinished_tasks": [],
        }

        message = stop_hook._format_summary_message(summary)

        assert "会话摘要" in message
        assert "文件修改: 5" in message
        assert "源文件: 3" in message
        assert "测试文件: 2" in message
        assert "Memory 操作: 1" in message

    def test_format_summary_many_files(self):
        """测试多文件时消息截断"""
        stop_hook = StopHook()

        summary = {
            "statistics": {
                "total_file_modifications": 10,
                "source_files_modified": 10,
                "test_files_modified": 0,
                "memory_operations": 0,
            },
            "files": {
                "source": [f"/file_{i}.py" for i in range(10)],
                "test": [],
            },
            "unfinished_tasks": [],
        }

        message = stop_hook._format_summary_message(summary)

        # 应该只显示 5 个文件
        assert "还有 5 个" in message

    def test_format_summary_with_todos(self):
        """测试包含 TODO 的摘要消息"""
        stop_hook = StopHook()

        summary = {
            "statistics": {
                "total_file_modifications": 1,
                "source_files_modified": 1,
                "test_files_modified": 0,
                "memory_operations": 0,
            },
            "files": {"source": ["/main.py"], "test": []},
            "unfinished_tasks": [
                {"type": "TODO", "content": "Implement feature X", "file": "/main.py", "line": 10},
                {"type": "FIXME", "content": "Fix bug Y", "file": "/main.py", "line": 20},
            ],
        }

        message = stop_hook._format_summary_message(summary)

        assert "未完成任务" in message
        assert "[TODO]" in message
        assert "[FIXME]" in message

    def test_disable_todo_extraction(self):
        """测试禁用 TODO 提取"""
        hook = StopHook(extract_todos=False, auto_write_memory=False)

        context = HookContext(
            hook_type=HookType.STOP,
            session_id="no-todos",
        )

        result = hook.execute(context)
        # Should work without TODO extraction
        assert result.decision == HookDecision.NOTIFY

    @patch("backend.core.memory_kernel.get_memory_kernel")
    @patch("backend.services.search.get_search_service")
    def test_auto_write_memory(self, mock_get_search, mock_get_kernel):
        """测试自动写入 Memory Anchor"""
        mock_search = MagicMock()
        mock_get_search.return_value = mock_search

        mock_kernel = MagicMock()
        mock_kernel.add_memory.return_value = {"id": "test-id"}
        mock_get_kernel.return_value = mock_kernel

        hook = StopHook(auto_write_memory=True)

        context = HookContext(
            hook_type=HookType.STOP,
            session_id="memory-write-test",
        )

        result = hook.execute(context)

        # Should have called add_memory
        mock_kernel.add_memory.assert_called_once()
        assert "Memory Anchor" in result.message


class TestStopHookIntegration:
    """测试 StopHook 与 Registry 集成"""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """每个测试前重置注册中心"""
        reset_hook_registry()
        yield
        reset_hook_registry()

    def test_register_and_execute(self):
        """测试注册并执行"""
        registry = get_hook_registry()
        hook = StopHook(auto_write_memory=False)
        registry.register(hook)

        context = HookContext(
            hook_type=HookType.STOP,
            session_id="registry-test",
        )

        result = registry.execute_single(HookType.STOP, context)
        assert result.decision == HookDecision.NOTIFY

    def test_full_workflow(self):
        """测试完整工作流"""
        registry = get_hook_registry()

        # 注册两个 Hook
        post_hook = PostToolHook()
        stop_hook = StopHook(post_tool_hook=post_hook, auto_write_memory=False)

        registry.register(post_hook)
        registry.register(stop_hook)

        # 模拟文件操作
        file_context = HookContext(
            hook_type=HookType.POST_TOOL_USE,
            tool_name="Write",
            tool_input={"file_path": "/src/app.py"},
        )
        registry.execute_single(HookType.POST_TOOL_USE, file_context)

        # 模拟会话结束
        stop_context = HookContext(
            hook_type=HookType.STOP,
            session_id="full-workflow",
        )

        result = registry.execute_single(HookType.STOP, stop_context)

        assert result.decision == HookDecision.NOTIFY
        assert "源文件: 1" in result.message
