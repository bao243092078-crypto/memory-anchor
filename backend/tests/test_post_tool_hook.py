"""
Tests for PostToolUse Hook.

测试工具执行后处理：
- 文件修改检测
- 测试文件识别
- 会话摘要生成
- Phase 5: 测试建议生成
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

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
from backend.services.test_mapping import (
    TestSuggestion,
    reset_test_mapping_service,
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
        hook = PostToolHook(enable_test_suggestions=False)  # 禁用测试建议以测试基础功能
        context = HookContext(
            hook_type=HookType.POST_TOOL_USE,
            tool_name="Write",
            tool_input={"file_path": "/path/to/main.py"},
        )

        result = hook.execute(context)

        # 基础功能：应该允许继续（无测试建议时返回 ALLOW）
        assert result.decision == HookDecision.ALLOW

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


class TestPostToolHookTestSuggestions:
    """测试 PostToolHook 测试建议功能 (Phase 5)"""

    @pytest.fixture(autouse=True)
    def reset_all(self):
        """每个测试前重置注册中心和测试映射服务"""
        reset_hook_registry()
        reset_test_mapping_service()
        yield
        reset_hook_registry()
        reset_test_mapping_service()

    def test_hook_with_test_suggestions_enabled(self, tmp_path):
        """测试启用测试建议功能"""
        hook = PostToolHook(
            enable_test_suggestions=True,
            project_root=tmp_path,
        )

        assert hook._enable_test_suggestions is True
        assert hook._project_root == tmp_path

    def test_hook_with_test_suggestions_disabled(self):
        """测试禁用测试建议功能"""
        hook = PostToolHook(enable_test_suggestions=False)

        # 执行源文件修改
        context = HookContext(
            hook_type=HookType.POST_TOOL_USE,
            tool_name="Write",
            tool_input={"file_path": "/src/main.py"},
        )
        result = hook.execute(context)

        # 不应该生成测试建议
        assert hook.get_test_suggestions() == []

    def test_lazy_load_test_mapping_service(self, tmp_path):
        """测试延迟加载 TestMappingService"""
        hook = PostToolHook(project_root=tmp_path)

        # 初始时没有加载
        assert hook._test_mapping_service is None

        # 获取服务时加载
        service = hook._get_test_mapping_service()
        assert service is not None
        assert hook._test_mapping_service is service

    def test_generate_test_suggestions_on_source_file_modify(self, tmp_path):
        """测试修改源文件时生成测试建议"""
        # 创建测试配置
        config_dir = tmp_path / ".ai"
        config_dir.mkdir()
        config_file = config_dir / "test-mapping.yaml"
        config_file.write_text("""
rules:
  - pattern: "backend/**/*.py"
    test_pattern: "backend/tests/test_{basename}.py"
""")

        hook = PostToolHook(
            enable_test_suggestions=True,
            project_root=tmp_path,
        )

        context = HookContext(
            hook_type=HookType.POST_TOOL_USE,
            tool_name="Write",
            tool_input={"file_path": "backend/services/memory.py"},
        )

        result = hook.execute(context)

        # 应该生成测试建议
        suggestions = hook.get_test_suggestions()
        assert len(suggestions) == 1
        assert suggestions[0].source_file == "backend/services/memory.py"

    def test_no_suggestions_for_test_files(self, tmp_path):
        """测试修改测试文件时不生成建议"""
        config_dir = tmp_path / ".ai"
        config_dir.mkdir()
        config_file = config_dir / "test-mapping.yaml"
        config_file.write_text("""
rules:
  - pattern: "**/*.py"
    test_pattern: "tests/test_{basename}.py"

exclude_patterns:
  - "**/test_*.py"
""")

        hook = PostToolHook(
            enable_test_suggestions=True,
            project_root=tmp_path,
        )

        # 修改测试文件
        context = HookContext(
            hook_type=HookType.POST_TOOL_USE,
            tool_name="Write",
            tool_input={"file_path": "tests/test_main.py"},
        )

        result = hook.execute(context)

        # 测试文件不应该生成建议
        suggestions = hook.get_test_suggestions()
        assert len(suggestions) == 0

    def test_format_test_suggestion_message(self, tmp_path):
        """测试格式化测试建议消息"""
        hook = PostToolHook(project_root=tmp_path)

        suggestions = [
            TestSuggestion(
                source_file="backend/main.py",
                suggested_tests=["backend/tests/test_main.py"],
                confidence=0.9,
                rule_used="backend/**/*.py",
            ),
        ]

        message = hook._format_test_suggestion_message(
            ["backend/main.py"],
            suggestions,
        )

        assert "文件修改检测" in message
        assert "建议运行的测试" in message
        assert "test_main.py" in message
        assert "🟢" in message  # 高置信度 emoji

    def test_format_message_with_multiple_suggestions(self, tmp_path):
        """测试格式化多个建议"""
        hook = PostToolHook(project_root=tmp_path)

        suggestions = [
            TestSuggestion(
                source_file="backend/a.py",
                suggested_tests=["backend/tests/test_a.py", "backend/tests/test_a_2.py"],
                confidence=0.9,
                rule_used=None,
            ),
            TestSuggestion(
                source_file="backend/b.py",
                suggested_tests=["backend/tests/test_b.py"],
                confidence=0.5,
                rule_used=None,
            ),
        ]

        message = hook._format_test_suggestion_message(
            ["backend/a.py", "backend/b.py"],
            suggestions,
        )

        assert "2 个源文件" in message
        assert "🟢" in message  # 高置信度
        assert "🟡" in message  # 中置信度

    def test_format_message_limits_tests_shown(self, tmp_path):
        """测试消息中限制显示的测试数量"""
        hook = PostToolHook(project_root=tmp_path)

        # 5 个测试建议
        suggestions = [
            TestSuggestion(
                source_file="backend/main.py",
                suggested_tests=[
                    "tests/test_1.py",
                    "tests/test_2.py",
                    "tests/test_3.py",
                    "tests/test_4.py",
                    "tests/test_5.py",
                ],
                confidence=0.7,
                rule_used=None,
            ),
        ]

        message = hook._format_test_suggestion_message(
            ["backend/main.py"],
            suggestions,
        )

        # 应该显示"还有 X 个"
        assert "还有 2 个" in message

    def test_session_summary_includes_test_suggestions(self, tmp_path):
        """测试会话摘要包含测试建议"""
        config_dir = tmp_path / ".ai"
        config_dir.mkdir()
        config_file = config_dir / "test-mapping.yaml"
        config_file.write_text("""
rules:
  - pattern: "backend/**/*.py"
    test_pattern: "backend/tests/test_{basename}.py"
""")

        hook = PostToolHook(
            enable_test_suggestions=True,
            project_root=tmp_path,
        )

        # 修改源文件
        hook.execute(
            HookContext(
                hook_type=HookType.POST_TOOL_USE,
                tool_name="Write",
                tool_input={"file_path": "backend/services/memory.py"},
            )
        )

        summary = hook.get_session_summary()

        assert "test_suggestions_count" in summary
        assert summary["test_suggestions_count"] == 1
        assert "suggested_tests" in summary
        assert len(summary["suggested_tests"]) > 0

    def test_clear_history_clears_test_suggestions(self, tmp_path):
        """测试清除历史也清除测试建议"""
        config_dir = tmp_path / ".ai"
        config_dir.mkdir()
        config_file = config_dir / "test-mapping.yaml"
        config_file.write_text("""
rules:
  - pattern: "**/*.py"
    test_pattern: "tests/test_{basename}.py"
""")

        hook = PostToolHook(
            enable_test_suggestions=True,
            project_root=tmp_path,
        )

        # 添加一些记录
        hook.execute(
            HookContext(
                hook_type=HookType.POST_TOOL_USE,
                tool_name="Write",
                tool_input={"file_path": "src/main.py"},
            )
        )

        assert len(hook.get_test_suggestions()) > 0

        # 清除历史
        hook.clear_history()

        assert hook.get_test_suggestions() == []

    def test_handles_test_mapping_service_error(self, tmp_path):
        """测试处理 TestMappingService 错误"""
        hook = PostToolHook(
            enable_test_suggestions=True,
            project_root=tmp_path,
        )

        # Mock 服务抛出错误
        with patch.object(hook, "_get_test_mapping_service") as mock_get:
            mock_service = MagicMock()
            mock_service.suggest_tests.side_effect = Exception("Test error")
            mock_get.return_value = mock_service

            context = HookContext(
                hook_type=HookType.POST_TOOL_USE,
                tool_name="Write",
                tool_input={"file_path": "backend/main.py"},
            )

            # 不应该抛出异常
            result = hook.execute(context)

            # 应该返回 NOTIFY 并包含文件名
            assert result.decision == HookDecision.NOTIFY
            assert "main.py" in result.message
