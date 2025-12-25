#!/usr/bin/env python3
"""
Test Mapping Service - 测试映射规则服务

Phase 5 实现：
1. 加载 .ai/test-mapping.yaml 规则
2. 根据源文件路径匹配测试文件
3. 生成测试建议

用法：
    from backend.services.test_mapping import TestMappingService, get_test_mapping_service

    service = get_test_mapping_service()
    suggestions = service.suggest_tests(["/src/main.py", "/src/utils.py"])
"""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

# 默认测试映射规则
DEFAULT_RULES: list[dict[str, Any]] = [
    # Python: backend/**/*.py → backend/tests/test_*.py
    {
        "pattern": "backend/**/*.py",
        "test_pattern": "backend/tests/test_{basename}.py",
        "priority": 1,
    },
    # Python: src/**/*.py → tests/test_*.py
    {
        "pattern": "src/**/*.py",
        "test_pattern": "tests/test_{basename}.py",
        "priority": 1,
    },
    # TypeScript/JavaScript: src/**/*.ts → src/**/*.test.ts
    {
        "pattern": "src/**/*.ts",
        "test_pattern": "src/**/{basename}.test.ts",
        "priority": 1,
    },
    {
        "pattern": "src/**/*.tsx",
        "test_pattern": "src/**/{basename}.test.tsx",
        "priority": 1,
    },
    # Frontend: components → __tests__
    {
        "pattern": "frontend/**/components/**/*.tsx",
        "test_pattern": "frontend/**/__tests__/{basename}.test.tsx",
        "priority": 2,
    },
]


@dataclass
class TestMapping:
    """单条测试映射规则"""

    pattern: str  # 源文件 glob 模式
    test_pattern: str  # 测试文件模式（支持 {basename}, {dirname}）
    priority: int = 1  # 优先级（越大越优先）
    description: str = ""  # 规则描述


@dataclass
class TestSuggestion:
    """测试建议"""

    source_file: str  # 源文件路径
    suggested_tests: list[str]  # 建议的测试文件/命令
    confidence: float  # 置信度 (0-1)
    rule_used: Optional[str] = None  # 使用的规则描述


@dataclass
class TestMappingConfig:
    """测试映射配置"""

    rules: list[TestMapping] = field(default_factory=list)
    project_root: Path = field(default_factory=Path.cwd)
    fallback_command: str = "pytest"  # 默认测试命令
    exclude_patterns: list[str] = field(default_factory=list)  # 排除模式


# 默认排除模式
DEFAULT_EXCLUDE_PATTERNS: list[str] = [
    "**/__pycache__/**",
    "**/*.pyc",
    "**/node_modules/**",
    "**/.git/**",
    "**/conftest.py",
    "**/test_*.py",
    "**/*_test.py",
    "**/*.test.ts",
    "**/*.test.tsx",
]


def _load_yaml_config(path: Path) -> dict[str, Any]:
    """加载 YAML 配置文件"""
    if not path.exists():
        logger.debug(f"Test mapping config not found: {path}")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
            return content or {}
    except yaml.YAMLError as e:
        logger.warning(f"Invalid YAML in {path}: {e}")
        return {}
    except Exception as e:
        logger.warning(f"Failed to load test mapping from {path}: {e}")
        return {}


def _parse_rules(raw_rules: list[dict[str, Any]]) -> list[TestMapping]:
    """解析规则列表"""
    rules = []
    for rule in raw_rules:
        if "pattern" in rule and "test_pattern" in rule:
            rules.append(
                TestMapping(
                    pattern=rule["pattern"],
                    test_pattern=rule["test_pattern"],
                    priority=rule.get("priority", 1),
                    description=rule.get("description", ""),
                )
            )
    return rules


def _expand_test_pattern(
    test_pattern: str,
    source_file: str,
    project_root: Path,
) -> list[str]:
    """展开测试模式为具体文件路径

    支持的占位符：
    - {basename}: 文件名（不含扩展名）
    - {dirname}: 目录名
    - {ext}: 扩展名
    """
    source_path = Path(source_file)
    basename = source_path.stem
    dirname = source_path.parent.name
    ext = source_path.suffix

    # 替换占位符
    expanded = test_pattern.format(
        basename=basename,
        dirname=dirname,
        ext=ext,
    )

    # 如果模式包含 **，使用 glob 搜索
    if "**" in expanded or "*" in expanded:
        matches = list(project_root.glob(expanded))
        return [str(m.relative_to(project_root)) for m in matches if m.exists()]

    # 直接返回路径（检查是否存在）
    test_path = project_root / expanded
    if test_path.exists():
        return [expanded]

    # 返回建议的路径（即使不存在）
    return [expanded]


class TestMappingService:
    """测试映射服务

    职责：
    1. 加载测试映射规则
    2. 根据源文件匹配测试
    3. 生成测试建议
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        project_root: Optional[Path] = None,
    ):
        """初始化服务

        Args:
            config_path: 配置文件路径（默认 .ai/test-mapping.yaml）
            project_root: 项目根目录
        """
        self._project_root = project_root or Path.cwd()
        self._config_path = config_path or (self._project_root / ".ai" / "test-mapping.yaml")
        self._config: Optional[TestMappingConfig] = None

    def _load_config(self) -> TestMappingConfig:
        """加载配置（延迟加载）"""
        if self._config is not None:
            return self._config

        raw_config = _load_yaml_config(self._config_path)

        # 解析规则
        raw_rules = raw_config.get("rules", [])
        if raw_rules:
            rules = _parse_rules(raw_rules)
        else:
            # 使用默认规则
            rules = _parse_rules(DEFAULT_RULES)

        # 解析排除模式
        exclude_patterns = raw_config.get("exclude_patterns", DEFAULT_EXCLUDE_PATTERNS)

        self._config = TestMappingConfig(
            rules=sorted(rules, key=lambda r: -r.priority),  # 按优先级排序
            project_root=self._project_root,
            fallback_command=raw_config.get("fallback_command", "pytest"),
            exclude_patterns=exclude_patterns,
        )

        return self._config

    def _is_excluded(self, file_path: str) -> bool:
        """检查文件是否被排除"""
        config = self._load_config()
        for pattern in config.exclude_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return True
        return False

    def reload(self) -> None:
        """重新加载配置"""
        self._config = None
        self._load_config()

    def match_rule(self, source_file: str) -> Optional[TestMapping]:
        """匹配源文件到规则

        Args:
            source_file: 源文件路径

        Returns:
            匹配的规则，无匹配返回 None
        """
        config = self._load_config()

        for rule in config.rules:
            if fnmatch.fnmatch(source_file, rule.pattern):
                return rule

        return None

    def suggest_tests(
        self,
        source_files: list[str],
        check_existence: bool = True,
    ) -> list[TestSuggestion]:
        """根据源文件生成测试建议

        Args:
            source_files: 源文件路径列表
            check_existence: 是否检查测试文件是否存在

        Returns:
            测试建议列表
        """
        config = self._load_config()
        suggestions: list[TestSuggestion] = []

        for source_file in source_files:
            # 跳过被排除的文件
            if self._is_excluded(source_file):
                continue

            rule = self.match_rule(source_file)

            if rule:
                # 展开测试模式
                test_files = _expand_test_pattern(
                    rule.test_pattern,
                    source_file,
                    config.project_root,
                )

                # 计算置信度
                if check_existence:
                    existing = [
                        f for f in test_files if (config.project_root / f).exists()
                    ]
                    confidence = 0.9 if existing else 0.5
                    test_files = existing if existing else test_files
                else:
                    confidence = 0.7

                suggestions.append(
                    TestSuggestion(
                        source_file=source_file,
                        suggested_tests=test_files,
                        confidence=confidence,
                        rule_used=rule.description or rule.pattern,
                    )
                )
            else:
                # 无匹配规则，使用 fallback
                suggestions.append(
                    TestSuggestion(
                        source_file=source_file,
                        suggested_tests=[config.fallback_command],
                        confidence=0.3,
                        rule_used="fallback",
                    )
                )

        return suggestions

    def generate_test_command(
        self,
        source_files: list[str],
    ) -> str:
        """生成测试命令

        Args:
            source_files: 源文件路径列表

        Returns:
            测试命令字符串
        """
        config = self._load_config()
        suggestions = self.suggest_tests(source_files, check_existence=True)

        # 收集所有建议的测试文件
        test_files: list[str] = []
        for suggestion in suggestions:
            if suggestion.confidence >= 0.5:
                test_files.extend(suggestion.suggested_tests)

        # 去重
        test_files = list(dict.fromkeys(test_files))

        if test_files:
            return f"{config.fallback_command} {' '.join(test_files)}"
        return config.fallback_command

    def format_suggestions(
        self,
        suggestions: list[TestSuggestion],
    ) -> str:
        """格式化测试建议为可读字符串

        Args:
            suggestions: 测试建议列表

        Returns:
            格式化的字符串
        """
        if not suggestions:
            return "No test suggestions available."

        lines = ["📋 **Test Suggestions**", ""]

        for suggestion in suggestions:
            confidence_emoji = "🟢" if suggestion.confidence >= 0.7 else "🟡" if suggestion.confidence >= 0.5 else "🔴"

            lines.append(f"{confidence_emoji} `{suggestion.source_file}`:")
            for test in suggestion.suggested_tests:
                lines.append(f"  → `{test}`")

        return "\n".join(lines)


# 单例管理
_test_mapping_service: Optional[TestMappingService] = None


def get_test_mapping_service(
    config_path: Optional[Path] = None,
    project_root: Optional[Path] = None,
) -> TestMappingService:
    """获取 TestMappingService 单例"""
    global _test_mapping_service

    if _test_mapping_service is None:
        _test_mapping_service = TestMappingService(
            config_path=config_path,
            project_root=project_root,
        )

    return _test_mapping_service


def reset_test_mapping_service() -> None:
    """重置单例（用于测试）"""
    global _test_mapping_service
    _test_mapping_service = None


__all__ = [
    "TestMappingService",
    "TestMapping",
    "TestSuggestion",
    "TestMappingConfig",
    "get_test_mapping_service",
    "reset_test_mapping_service",
]
