"""
Tests for TestMappingService (Phase 5).

测试内容：
1. 规则加载和解析
2. 文件模式匹配
3. 排除模式过滤
4. 测试建议生成
5. 测试命令生成
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from backend.services.test_mapping import (
    TestMappingService,
    TestMapping,
    TestSuggestion,
    TestMappingConfig,
    get_test_mapping_service,
    reset_test_mapping_service,
    _parse_rules,
    _expand_test_pattern,
    DEFAULT_RULES,
    DEFAULT_EXCLUDE_PATTERNS,
)


class TestParseRules:
    """测试规则解析"""

    def test_parse_valid_rules(self):
        """测试解析有效规则"""
        raw_rules = [
            {
                "pattern": "src/**/*.py",
                "test_pattern": "tests/test_{basename}.py",
                "priority": 10,
                "description": "Python source files",
            },
            {
                "pattern": "lib/**/*.ts",
                "test_pattern": "lib/**/{basename}.test.ts",
            },
        ]

        rules = _parse_rules(raw_rules)

        assert len(rules) == 2
        assert rules[0].pattern == "src/**/*.py"
        assert rules[0].priority == 10
        assert rules[0].description == "Python source files"
        assert rules[1].priority == 1  # default

    def test_parse_empty_rules(self):
        """测试解析空规则列表"""
        rules = _parse_rules([])
        assert rules == []

    def test_parse_invalid_rules_missing_pattern(self):
        """测试解析缺少 pattern 的规则"""
        raw_rules = [
            {"test_pattern": "tests/test_{basename}.py"},
        ]
        rules = _parse_rules(raw_rules)
        assert rules == []

    def test_parse_invalid_rules_missing_test_pattern(self):
        """测试解析缺少 test_pattern 的规则"""
        raw_rules = [
            {"pattern": "src/**/*.py"},
        ]
        rules = _parse_rules(raw_rules)
        assert rules == []


class TestExpandTestPattern:
    """测试模式展开"""

    def test_expand_basename(self, tmp_path):
        """测试 {basename} 占位符"""
        result = _expand_test_pattern(
            "tests/test_{basename}.py",
            "src/main.py",
            tmp_path,
        )
        assert result == ["tests/test_main.py"]

    def test_expand_dirname(self, tmp_path):
        """测试 {dirname} 占位符"""
        result = _expand_test_pattern(
            "tests/{dirname}/test_{basename}.py",
            "src/utils/helper.py",
            tmp_path,
        )
        assert result == ["tests/utils/test_helper.py"]

    def test_expand_ext(self, tmp_path):
        """测试 {ext} 占位符"""
        result = _expand_test_pattern(
            "tests/test_{basename}{ext}",
            "src/app.ts",
            tmp_path,
        )
        assert result == ["tests/test_app.ts"]

    def test_expand_with_glob_finds_existing(self, tmp_path):
        """测试 glob 模式查找已存在的文件"""
        # 创建测试文件
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_main.py").touch()

        result = _expand_test_pattern(
            "tests/test_{basename}.py",
            "src/main.py",
            tmp_path,
        )
        assert "tests/test_main.py" in result


class TestTestMappingService:
    """测试 TestMappingService"""

    @pytest.fixture(autouse=True)
    def reset_service(self):
        """每个测试前重置服务单例"""
        reset_test_mapping_service()
        yield
        reset_test_mapping_service()

    def test_default_rules(self, tmp_path):
        """测试默认规则加载"""
        service = TestMappingService(project_root=tmp_path)
        config = service._load_config()

        # 应该使用默认规则
        assert len(config.rules) > 0
        assert config.fallback_command == "pytest"

    def test_load_yaml_config(self, tmp_path):
        """测试从 YAML 加载配置"""
        # 创建配置文件
        config_dir = tmp_path / ".ai"
        config_dir.mkdir()
        config_file = config_dir / "test-mapping.yaml"
        config_file.write_text("""
version: 1
fallback_command: "uv run pytest"

rules:
  - pattern: "backend/**/*.py"
    test_pattern: "backend/tests/test_{basename}.py"
    priority: 10
    description: "Backend Python modules"

exclude_patterns:
  - "**/__pycache__/**"
  - "**/test_*.py"
""")

        service = TestMappingService(project_root=tmp_path)
        config = service._load_config()

        assert len(config.rules) == 1
        assert config.rules[0].pattern == "backend/**/*.py"
        assert config.fallback_command == "uv run pytest"
        assert "**/__pycache__/**" in config.exclude_patterns

    def test_match_rule_python(self, tmp_path):
        """测试匹配 Python 规则"""
        # 创建配置
        config_dir = tmp_path / ".ai"
        config_dir.mkdir()
        config_file = config_dir / "test-mapping.yaml"
        config_file.write_text("""
rules:
  - pattern: "backend/**/*.py"
    test_pattern: "backend/tests/test_{basename}.py"
    priority: 10
""")

        service = TestMappingService(project_root=tmp_path)

        rule = service.match_rule("backend/services/memory.py")
        assert rule is not None
        assert rule.pattern == "backend/**/*.py"

    def test_match_rule_no_match(self, tmp_path):
        """测试无匹配规则"""
        config_dir = tmp_path / ".ai"
        config_dir.mkdir()
        config_file = config_dir / "test-mapping.yaml"
        config_file.write_text("""
rules:
  - pattern: "backend/**/*.py"
    test_pattern: "backend/tests/test_{basename}.py"
""")

        service = TestMappingService(project_root=tmp_path)

        rule = service.match_rule("frontend/app.tsx")
        assert rule is None

    def test_is_excluded(self, tmp_path):
        """测试排除模式"""
        config_dir = tmp_path / ".ai"
        config_dir.mkdir()
        config_file = config_dir / "test-mapping.yaml"
        config_file.write_text("""
rules:
  - pattern: "**/*.py"
    test_pattern: "tests/test_{basename}.py"

exclude_patterns:
  - "**/__pycache__/**"
  - "**/test_*.py"
  - "**/*.pyc"
""")

        service = TestMappingService(project_root=tmp_path)

        # 应该排除
        assert service._is_excluded("backend/__pycache__/foo.py") is True
        assert service._is_excluded("backend/tests/test_main.py") is True
        assert service._is_excluded("backend/cache.pyc") is True  # 需要目录前缀

        # 不应该排除
        assert service._is_excluded("backend/main.py") is False
        assert service._is_excluded("backend/services/memory.py") is False


class TestSuggestTests:
    """测试测试建议生成"""

    @pytest.fixture(autouse=True)
    def reset_service(self):
        """每个测试前重置服务单例"""
        reset_test_mapping_service()
        yield
        reset_test_mapping_service()

    def test_suggest_tests_with_existing_test(self, tmp_path):
        """测试存在对应测试文件时的建议"""
        # 创建目录结构
        (tmp_path / "backend" / "tests").mkdir(parents=True)
        (tmp_path / "backend" / "tests" / "test_memory.py").touch()

        # 创建配置
        config_dir = tmp_path / ".ai"
        config_dir.mkdir()
        config_file = config_dir / "test-mapping.yaml"
        config_file.write_text("""
rules:
  - pattern: "backend/**/*.py"
    test_pattern: "backend/tests/test_{basename}.py"
""")

        service = TestMappingService(project_root=tmp_path)
        suggestions = service.suggest_tests(["backend/services/memory.py"])

        assert len(suggestions) == 1
        assert suggestions[0].source_file == "backend/services/memory.py"
        assert suggestions[0].confidence == 0.9  # 存在 → 高置信度
        assert "backend/tests/test_memory.py" in suggestions[0].suggested_tests

    def test_suggest_tests_without_existing_test(self, tmp_path):
        """测试不存在对应测试文件时的建议"""
        # 创建配置
        config_dir = tmp_path / ".ai"
        config_dir.mkdir()
        config_file = config_dir / "test-mapping.yaml"
        config_file.write_text("""
rules:
  - pattern: "backend/**/*.py"
    test_pattern: "backend/tests/test_{basename}.py"
""")

        service = TestMappingService(project_root=tmp_path)
        suggestions = service.suggest_tests(["backend/services/memory.py"])

        assert len(suggestions) == 1
        assert suggestions[0].confidence == 0.5  # 不存在 → 中等置信度

    def test_suggest_tests_no_matching_rule(self, tmp_path):
        """测试无匹配规则时使用 fallback"""
        config_dir = tmp_path / ".ai"
        config_dir.mkdir()
        config_file = config_dir / "test-mapping.yaml"
        config_file.write_text("""
fallback_command: "pytest"

rules:
  - pattern: "backend/**/*.py"
    test_pattern: "backend/tests/test_{basename}.py"
""")

        service = TestMappingService(project_root=tmp_path)
        suggestions = service.suggest_tests(["frontend/app.tsx"])

        assert len(suggestions) == 1
        assert suggestions[0].confidence == 0.3  # fallback → 低置信度
        assert "pytest" in suggestions[0].suggested_tests

    def test_suggest_tests_skips_excluded(self, tmp_path):
        """测试排除文件不生成建议"""
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

        service = TestMappingService(project_root=tmp_path)
        suggestions = service.suggest_tests(["backend/tests/test_main.py"])

        # 测试文件应该被排除，不生成建议
        assert len(suggestions) == 0

    def test_suggest_tests_multiple_files(self, tmp_path):
        """测试多个文件的建议"""
        config_dir = tmp_path / ".ai"
        config_dir.mkdir()
        config_file = config_dir / "test-mapping.yaml"
        config_file.write_text("""
rules:
  - pattern: "backend/**/*.py"
    test_pattern: "backend/tests/test_{basename}.py"
""")

        service = TestMappingService(project_root=tmp_path)
        suggestions = service.suggest_tests([
            "backend/services/memory.py",
            "backend/services/search.py",
            "backend/core/kernel.py",
        ])

        assert len(suggestions) == 3


class TestGenerateTestCommand:
    """测试测试命令生成"""

    @pytest.fixture(autouse=True)
    def reset_service(self):
        """每个测试前重置服务单例"""
        reset_test_mapping_service()
        yield
        reset_test_mapping_service()

    def test_generate_command_with_matches(self, tmp_path):
        """测试生成带匹配文件的命令"""
        # 创建测试文件
        (tmp_path / "backend" / "tests").mkdir(parents=True)
        (tmp_path / "backend" / "tests" / "test_memory.py").touch()

        # 创建配置
        config_dir = tmp_path / ".ai"
        config_dir.mkdir()
        config_file = config_dir / "test-mapping.yaml"
        config_file.write_text("""
fallback_command: "uv run pytest"

rules:
  - pattern: "backend/**/*.py"
    test_pattern: "backend/tests/test_{basename}.py"
""")

        service = TestMappingService(project_root=tmp_path)
        command = service.generate_test_command(["backend/services/memory.py"])

        assert "uv run pytest" in command
        assert "backend/tests/test_memory.py" in command

    def test_generate_command_fallback(self, tmp_path):
        """测试无匹配时的 fallback 命令"""
        config_dir = tmp_path / ".ai"
        config_dir.mkdir()
        config_file = config_dir / "test-mapping.yaml"
        config_file.write_text("""
fallback_command: "npm test"

rules: []
""")

        service = TestMappingService(project_root=tmp_path)
        command = service.generate_test_command(["src/app.ts"])

        assert command == "npm test"


class TestFormatSuggestions:
    """测试建议格式化"""

    @pytest.fixture(autouse=True)
    def reset_service(self):
        """每个测试前重置服务单例"""
        reset_test_mapping_service()
        yield
        reset_test_mapping_service()

    def test_format_empty_suggestions(self, tmp_path):
        """测试格式化空建议"""
        service = TestMappingService(project_root=tmp_path)
        output = service.format_suggestions([])
        assert "No test suggestions" in output

    def test_format_with_suggestions(self, tmp_path):
        """测试格式化有建议"""
        service = TestMappingService(project_root=tmp_path)
        suggestions = [
            TestSuggestion(
                source_file="backend/main.py",
                suggested_tests=["backend/tests/test_main.py"],
                confidence=0.9,
                rule_used="backend/**/*.py",
            ),
            TestSuggestion(
                source_file="frontend/app.ts",
                suggested_tests=["frontend/__tests__/app.test.ts"],
                confidence=0.5,
                rule_used=None,
            ),
        ]

        output = service.format_suggestions(suggestions)

        assert "Test Suggestions" in output
        assert "backend/main.py" in output
        assert "backend/tests/test_main.py" in output
        assert "🟢" in output  # 高置信度
        assert "🟡" in output  # 中置信度


class TestServiceSingleton:
    """测试服务单例"""

    @pytest.fixture(autouse=True)
    def reset_service(self):
        """每个测试前重置服务单例"""
        reset_test_mapping_service()
        yield
        reset_test_mapping_service()

    def test_get_service_singleton(self, tmp_path):
        """测试获取单例服务"""
        service1 = get_test_mapping_service(project_root=tmp_path)
        service2 = get_test_mapping_service()

        assert service1 is service2

    def test_reset_service_singleton(self, tmp_path):
        """测试重置单例服务"""
        service1 = get_test_mapping_service(project_root=tmp_path)
        reset_test_mapping_service()
        service2 = get_test_mapping_service(project_root=tmp_path)

        assert service1 is not service2


class TestDefaultConfig:
    """测试默认配置"""

    def test_default_rules_exist(self):
        """测试默认规则存在"""
        assert len(DEFAULT_RULES) > 0

    def test_default_rules_have_required_fields(self):
        """测试默认规则有必填字段"""
        for rule in DEFAULT_RULES:
            assert "pattern" in rule
            assert "test_pattern" in rule

    def test_default_exclude_patterns_exist(self):
        """测试默认排除模式存在"""
        assert len(DEFAULT_EXCLUDE_PATTERNS) > 0
        assert "**/__pycache__/**" in DEFAULT_EXCLUDE_PATTERNS
        assert "**/test_*.py" in DEFAULT_EXCLUDE_PATTERNS
