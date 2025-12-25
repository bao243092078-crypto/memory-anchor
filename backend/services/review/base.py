"""
Review System Base Classes

定义审查系统的核心抽象：
- ReviewContext: 审查上下文（待审查的代码/文件）
- ReviewFinding: 单个发现
- ReviewResult: 审查结果
- BaseReviewer: 审查器抽象基类
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(Enum):
    """问题严重程度"""
    CRITICAL = "critical"   # 必须修复
    HIGH = "high"           # 强烈建议修复
    MEDIUM = "medium"       # 建议修复
    LOW = "low"             # 可选修复
    INFO = "info"           # 仅供参考


@dataclass
class ReviewContext:
    """审查上下文

    包含待审查的代码信息，支持多种输入：
    - 单个文件
    - 目录（递归）
    - Git diff
    - 代码片段
    """
    # 目标路径（文件或目录）
    target_path: Path | None = None

    # 文件列表（显式指定）
    files: list[Path] = field(default_factory=list)

    # Git diff 内容
    diff_content: str | None = None

    # 代码片段（直接传入）
    code_snippet: str | None = None

    # 项目根目录
    project_root: Path | None = None

    # 额外配置
    options: dict[str, Any] = field(default_factory=dict)

    def get_files(self) -> list[Path]:
        """获取所有待审查文件"""
        if self.files:
            return self.files

        if self.target_path:
            if self.target_path.is_file():
                return [self.target_path]
            elif self.target_path.is_dir():
                # 递归收集 Python 文件
                return list(self.target_path.rglob("*.py"))

        return []

    def has_content(self) -> bool:
        """是否有内容可审查"""
        return bool(
            self.files
            or self.target_path
            or self.diff_content
            or self.code_snippet
        )


@dataclass
class ReviewFinding:
    """单个审查发现

    记录一个具体问题/建议。
    """
    # 问题描述
    message: str

    # 严重程度
    severity: Severity

    # 审查视角（security/performance/quality/memory）
    perspective: str

    # 相关文件
    file_path: Path | None = None

    # 行号范围
    line_start: int | None = None
    line_end: int | None = None

    # 规则 ID（如 SEC-001, PERF-002）
    rule_id: str | None = None

    # 修复建议
    suggestion: str | None = None

    # 代码片段
    code_snippet: str | None = None

    def format_location(self) -> str:
        """格式化位置信息"""
        if not self.file_path:
            return ""

        loc = str(self.file_path)
        if self.line_start:
            if self.line_end and self.line_end != self.line_start:
                loc += f":{self.line_start}-{self.line_end}"
            else:
                loc += f":{self.line_start}"
        return loc


@dataclass
class ReviewResult:
    """单个视角的审查结果"""
    # 视角名称
    perspective: str

    # 发现列表
    findings: list[ReviewFinding] = field(default_factory=list)

    # 执行时间（秒）
    duration: float = 0.0

    # 是否成功
    success: bool = True

    # 错误信息（如果失败）
    error: str | None = None

    # 审查的文件数
    files_reviewed: int = 0

    # 统计信息
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.HIGH)

    @property
    def medium_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.MEDIUM)

    @property
    def low_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.LOW)

    @property
    def total_findings(self) -> int:
        return len(self.findings)

    @property
    def has_blocking_issues(self) -> bool:
        """是否有阻断性问题"""
        return self.critical_count > 0


class BaseReviewer(ABC):
    """审查器抽象基类

    所有具体审查器（Security/Performance/Quality/Memory）必须继承此类。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """审查器名称（用于显示）"""
        ...

    @property
    @abstractmethod
    def perspective(self) -> str:
        """视角标识（security/performance/quality/memory）"""
        ...

    @property
    def emoji(self) -> str:
        """视角 emoji"""
        return "🔍"

    @abstractmethod
    def review(self, context: ReviewContext) -> ReviewResult:
        """执行审查

        Args:
            context: 审查上下文

        Returns:
            审查结果
        """
        ...

    def create_finding(
        self,
        message: str,
        severity: Severity,
        *,
        file_path: Path | None = None,
        line_start: int | None = None,
        line_end: int | None = None,
        rule_id: str | None = None,
        suggestion: str | None = None,
        code_snippet: str | None = None,
    ) -> ReviewFinding:
        """创建发现（便捷方法）"""
        return ReviewFinding(
            message=message,
            severity=severity,
            perspective=self.perspective,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            rule_id=rule_id,
            suggestion=suggestion,
            code_snippet=code_snippet,
        )


__all__ = [
    "Severity",
    "ReviewContext",
    "ReviewFinding",
    "ReviewResult",
    "BaseReviewer",
]
