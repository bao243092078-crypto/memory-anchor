"""
测试配置错误处理

Bug 4: Config loading errors silently swallowed
确保配置加载错误被正确记录和抛出，而不是静默吞掉
"""


import pytest

from backend.config import (
    ConfigLoadError,
    _load_constitution_yaml,
    _load_yaml_config,
)


class TestConfigErrorHandling:
    """测试配置错误处理"""

    def test_valid_yaml_loads_successfully(self, tmp_path):
        """测试有效的 YAML 可以成功加载"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
project_name: test_project
vector_size: 384
        """)

        result = _load_yaml_config(config_file)
        assert result["project_name"] == "test_project"
        assert result["vector_size"] == 384

    def test_missing_file_returns_empty_dict(self, tmp_path):
        """测试缺失的文件返回空字典（graceful）"""
        non_existent = tmp_path / "does_not_exist.yaml"
        result = _load_yaml_config(non_existent)
        assert result == {}

    def test_invalid_yaml_raises_config_load_error(self, tmp_path):
        """测试无效的 YAML 抛出 ConfigLoadError"""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("""
project_name: test
  invalid_indentation:
    - this should fail
        """)

        with pytest.raises(ConfigLoadError, match="Invalid YAML"):
            _load_yaml_config(config_file)

    def test_empty_yaml_returns_empty_dict(self, tmp_path):
        """测试空 YAML 文件返回空字典"""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        result = _load_yaml_config(config_file)
        assert result == {}


class TestConstitutionYamlErrorHandling:
    """测试宪法层 YAML 错误处理"""

    def test_valid_constitution_loads_successfully(self, tmp_path):
        """测试有效的宪法层 YAML 可以成功加载"""
        constitution_file = tmp_path / "constitution.yaml"
        constitution_file.write_text("""
constitution:
  - id: test-1
    content: "测试条目"
    category: person
        """)

        result = _load_constitution_yaml(constitution_file)
        assert len(result) == 1
        assert result[0].id == "test-1"
        assert result[0].content == "测试条目"
        assert result[0].category == "person"

    def test_missing_constitution_file_returns_empty_list(self, tmp_path):
        """测试缺失的宪法层文件返回空列表（graceful）"""
        non_existent = tmp_path / "does_not_exist.yaml"
        result = _load_constitution_yaml(non_existent)
        assert result == []

    def test_invalid_constitution_yaml_raises_error(self, tmp_path):
        """测试无效的宪法层 YAML 抛出 ConfigLoadError"""
        constitution_file = tmp_path / "invalid_constitution.yaml"
        # 使用真正的无效 YAML 语法（缩进错误）
        constitution_file.write_text("""
constitution:
  - id: test
    content: "valid"
- id: test2
   content: "invalid indentation"
        """)

        with pytest.raises(ConfigLoadError, match="Invalid YAML"):
            _load_constitution_yaml(constitution_file)

    def test_empty_constitution_list_returns_empty(self, tmp_path):
        """测试空的 constitution 列表返回空列表"""
        constitution_file = tmp_path / "empty_constitution.yaml"
        constitution_file.write_text("""
constitution: []
        """)

        result = _load_constitution_yaml(constitution_file)
        assert result == []

    def test_missing_content_field_skipped(self, tmp_path):
        """测试缺少 content 字段的条目被跳过"""
        constitution_file = tmp_path / "missing_content.yaml"
        constitution_file.write_text("""
constitution:
  - id: test-1
    content: "有效条目"
  - id: test-2
    category: person
  - id: test-3
    content: "另一个有效条目"
        """)

        result = _load_constitution_yaml(constitution_file)
        assert len(result) == 2
        assert result[0].id == "test-1"
        assert result[1].id == "test-3"

    def test_auto_generated_id_when_missing(self, tmp_path):
        """测试缺少 id 时自动生成"""
        constitution_file = tmp_path / "no_id.yaml"
        constitution_file.write_text("""
constitution:
  - content: "第一条"
  - content: "第二条"
        """)

        result = _load_constitution_yaml(constitution_file)
        assert len(result) == 2
        assert result[0].id == "item-0"
        assert result[1].id == "item-1"
