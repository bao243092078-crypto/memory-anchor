"""
Tests for Stop Hook.

测试会话结束处理：
- 会话摘要生成
- 摘要保存
- PostToolHook 集成
"""

import json
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
    generate_session_summary,
    get_hook_registry,
    reset_hook_registry,
    save_session_summary,
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


class TestSaveSessionSummary:
    """测试会话摘要保存"""

    def test_save_summary(self):
        """测试保存摘要"""
        summary = generate_session_summary(session_id="save-test")

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("backend.hooks.stop_hook.STATE_DIR", Path(tmpdir)):
                file_path = save_session_summary(summary)

                assert file_path.exists()
                assert "save-test" in file_path.name
                assert file_path.suffix == ".json"

                # 验证内容
                with open(file_path, encoding="utf-8") as f:
                    saved = json.load(f)
                assert saved["session_id"] == "save-test"


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
        hook = StopHook()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("backend.hooks.stop_hook.STATE_DIR", Path(tmpdir)):
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

        stop_hook = StopHook(post_tool_hook=post_hook)

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("backend.hooks.stop_hook.STATE_DIR", Path(tmpdir)):
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
        }

        message = stop_hook._format_summary_message(summary)

        # 应该只显示 5 个文件
        assert "还有 5 个" in message


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
        hook = StopHook()
        registry.register(hook)

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("backend.hooks.stop_hook.STATE_DIR", Path(tmpdir)):
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
        stop_hook = StopHook(post_tool_hook=post_hook)

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
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("backend.hooks.stop_hook.STATE_DIR", Path(tmpdir)):
                stop_context = HookContext(
                    hook_type=HookType.STOP,
                    session_id="full-workflow",
                )

                result = registry.execute_single(HookType.STOP, stop_context)

                assert result.decision == HookDecision.NOTIFY
                assert "源文件: 1" in result.message
