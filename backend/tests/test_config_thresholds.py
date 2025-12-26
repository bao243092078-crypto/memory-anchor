"""
测试阈值配置（Phase 4）

测试内容：
1. 默认阈值值
2. 环境变量覆盖
3. YAML 配置覆盖
4. 无效值处理
"""

import os
from unittest.mock import patch

import pytest

from backend.config import (
    MemoryAnchorConfig,
    load_config,
    reset_config,
)


class TestThresholdDefaults:
    """测试阈值默认值"""

    @pytest.fixture(autouse=True)
    def reset(self):
        """每个测试前重置配置"""
        reset_config()
        yield
        reset_config()

    def test_default_plans_max_lines(self):
        """测试 plans_max_lines 默认值"""
        config = MemoryAnchorConfig()
        assert config.plans_max_lines == 200

    def test_default_session_log_max_lines(self):
        """测试 session_log_max_lines 默认值"""
        config = MemoryAnchorConfig()
        assert config.session_log_max_lines == 500

    def test_default_summary_max_files(self):
        """测试 summary_max_files 默认值"""
        config = MemoryAnchorConfig()
        assert config.summary_max_files == 5

    def test_default_summary_max_todos(self):
        """测试 summary_max_todos 默认值"""
        config = MemoryAnchorConfig()
        assert config.summary_max_todos == 5

    def test_default_todo_content_max_chars(self):
        """测试 todo_content_max_chars 默认值"""
        config = MemoryAnchorConfig()
        assert config.todo_content_max_chars == 50

    def test_default_checklist_max_items(self):
        """测试 checklist_max_items 默认值"""
        config = MemoryAnchorConfig()
        assert config.checklist_max_items == 20

    def test_default_memory_content_max_chars(self):
        """测试 memory_content_max_chars 默认值"""
        config = MemoryAnchorConfig()
        assert config.memory_content_max_chars == 500


class TestThresholdEnvOverrides:
    """测试阈值环境变量覆盖"""

    @pytest.fixture(autouse=True)
    def reset(self):
        """每个测试前重置配置"""
        reset_config()
        yield
        reset_config()

    def test_env_override_plans_max_lines(self, tmp_path):
        """测试 MA_PLANS_MAX_LINES 环境变量"""
        with patch.dict(os.environ, {"MA_PLANS_MAX_LINES": "100"}):
            config = load_config(config_dir=tmp_path)
            assert config.plans_max_lines == 100

    def test_env_override_session_log_max_lines(self, tmp_path):
        """测试 MA_SESSION_LOG_MAX_LINES 环境变量"""
        with patch.dict(os.environ, {"MA_SESSION_LOG_MAX_LINES": "1000"}):
            config = load_config(config_dir=tmp_path)
            assert config.session_log_max_lines == 1000

    def test_env_override_summary_max_files(self, tmp_path):
        """测试 MA_SUMMARY_MAX_FILES 环境变量"""
        with patch.dict(os.environ, {"MA_SUMMARY_MAX_FILES": "10"}):
            config = load_config(config_dir=tmp_path)
            assert config.summary_max_files == 10

    def test_env_override_summary_max_todos(self, tmp_path):
        """测试 MA_SUMMARY_MAX_TODOS 环境变量"""
        with patch.dict(os.environ, {"MA_SUMMARY_MAX_TODOS": "10"}):
            config = load_config(config_dir=tmp_path)
            assert config.summary_max_todos == 10

    def test_env_override_todo_content_max_chars(self, tmp_path):
        """测试 MA_TODO_CONTENT_MAX_CHARS 环境变量"""
        with patch.dict(os.environ, {"MA_TODO_CONTENT_MAX_CHARS": "100"}):
            config = load_config(config_dir=tmp_path)
            assert config.todo_content_max_chars == 100

    def test_env_override_checklist_max_items(self, tmp_path):
        """测试 MA_CHECKLIST_MAX_ITEMS 环境变量"""
        with patch.dict(os.environ, {"MA_CHECKLIST_MAX_ITEMS": "50"}):
            config = load_config(config_dir=tmp_path)
            assert config.checklist_max_items == 50

    def test_env_override_memory_content_max_chars(self, tmp_path):
        """测试 MA_MEMORY_CONTENT_MAX_CHARS 环境变量"""
        with patch.dict(os.environ, {"MA_MEMORY_CONTENT_MAX_CHARS": "1000"}):
            config = load_config(config_dir=tmp_path)
            assert config.memory_content_max_chars == 1000

    def test_invalid_env_value_uses_default(self, tmp_path, caplog):
        """测试无效的环境变量值使用默认值"""
        with patch.dict(os.environ, {"MA_PLANS_MAX_LINES": "not_a_number"}):
            config = load_config(config_dir=tmp_path)
            # 应该使用默认值
            assert config.plans_max_lines == 200
            # 应该有警告日志
            assert "Invalid integer value" in caplog.text


class TestThresholdYamlOverrides:
    """测试阈值 YAML 配置覆盖"""

    @pytest.fixture(autouse=True)
    def reset(self):
        """每个测试前重置配置"""
        reset_config()
        yield
        reset_config()

    def test_yaml_override_thresholds(self, tmp_path):
        """测试 YAML 配置覆盖阈值"""
        # 创建配置目录
        config_dir = tmp_path / ".memory-anchor"
        config_dir.mkdir(parents=True)

        # 创建项目目录
        project_dir = config_dir / "projects" / "default"
        project_dir.mkdir(parents=True)

        # 写入配置文件
        config_file = project_dir / "config.yaml"
        config_file.write_text("""
plans_max_lines: 150
summary_max_files: 8
checklist_max_items: 30
        """)

        config = load_config(config_dir=config_dir)

        assert config.plans_max_lines == 150
        assert config.summary_max_files == 8
        assert config.checklist_max_items == 30
        # 未配置的使用默认值
        assert config.session_log_max_lines == 500

    def test_env_overrides_yaml(self, tmp_path):
        """测试环境变量优先于 YAML 配置"""
        # 创建配置目录
        config_dir = tmp_path / ".memory-anchor"
        config_dir.mkdir(parents=True)

        # 创建项目目录
        project_dir = config_dir / "projects" / "default"
        project_dir.mkdir(parents=True)

        # YAML 配置
        config_file = project_dir / "config.yaml"
        config_file.write_text("""
plans_max_lines: 150
        """)

        # 环境变量覆盖
        with patch.dict(os.environ, {"MA_PLANS_MAX_LINES": "300"}):
            config = load_config(config_dir=config_dir)
            # 环境变量优先
            assert config.plans_max_lines == 300


class TestStopHookUsesConfigThresholds:
    """测试 StopHook 使用配置阈值"""

    @pytest.fixture(autouse=True)
    def reset(self):
        """每个测试前重置配置"""
        reset_config()
        yield
        reset_config()

    def test_format_summary_uses_config_max_files(self, tmp_path):
        """测试摘要消息使用配置的 max_files"""
        from backend.hooks import StopHook

        # 设置较小的阈值
        with patch.dict(os.environ, {"MA_SUMMARY_MAX_FILES": "2"}):
            # 强制重新加载配置
            reset_config()

            hook = StopHook(auto_write_memory=False)
            summary = {
                "statistics": {
                    "total_file_modifications": 5,
                    "source_files_modified": 5,
                    "test_files_modified": 0,
                    "memory_operations": 0,
                },
                "files": {
                    "source": ["/a.py", "/b.py", "/c.py", "/d.py", "/e.py"],
                    "test": [],
                },
                "unfinished_tasks": [],
            }

            message = hook._format_summary_message(summary)

            # 应该只显示 2 个文件，然后 "还有 3 个"
            assert "/a.py" in message
            assert "/b.py" in message
            assert "/c.py" not in message
            assert "还有 3 个" in message

    def test_format_summary_uses_config_max_todos(self, tmp_path):
        """测试摘要消息使用配置的 max_todos"""
        from backend.hooks import StopHook

        # 设置较小的阈值
        with patch.dict(os.environ, {"MA_SUMMARY_MAX_TODOS": "1"}):
            reset_config()

            hook = StopHook(auto_write_memory=False)
            summary = {
                "statistics": {
                    "total_file_modifications": 0,
                    "source_files_modified": 0,
                    "test_files_modified": 0,
                    "memory_operations": 0,
                },
                "files": {"source": [], "test": []},
                "unfinished_tasks": [
                    {"type": "TODO", "content": "First task", "file": "/a.py", "line": 1},
                    {"type": "FIXME", "content": "Second task", "file": "/b.py", "line": 2},
                    {"type": "TODO", "content": "Third task", "file": "/c.py", "line": 3},
                ],
            }

            message = hook._format_summary_message(summary)

            # 应该只显示 1 个 TODO，然后 "还有 2 个"
            assert "[TODO] First task" in message
            assert "[FIXME]" not in message
            assert "还有 2 个" in message

    def test_format_summary_uses_config_todo_max_chars(self, tmp_path):
        """测试 TODO 内容使用配置的最大字符数"""
        from backend.hooks import StopHook

        # 设置较小的阈值
        with patch.dict(os.environ, {"MA_TODO_CONTENT_MAX_CHARS": "10"}):
            reset_config()

            hook = StopHook(auto_write_memory=False)
            summary = {
                "statistics": {
                    "total_file_modifications": 0,
                    "source_files_modified": 0,
                    "test_files_modified": 0,
                    "memory_operations": 0,
                },
                "files": {"source": [], "test": []},
                "unfinished_tasks": [
                    {"type": "TODO", "content": "This is a very long task description", "file": "/a.py", "line": 1},
                ],
            }

            message = hook._format_summary_message(summary)

            # 内容应该被截断到 10 个字符
            assert "[TODO] This is a " in message
            assert "very long task description" not in message
