"""
Quality Reviewer - 代码质量审查视角

检测代码质量问题：
- QUAL-001: 函数过长
- QUAL-002: 圈复杂度过高
- QUAL-003: 重复代码模式
- QUAL-004: 魔法数字
- QUAL-005: 过深嵌套
- QUAL-006: 命名不规范
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from backend.services.review.base import (
    BaseReviewer,
    ReviewContext,
    ReviewFinding,
    ReviewResult,
    Severity,
)

# 阈值配置
MAX_FUNCTION_LINES = 50
MAX_NESTING_DEPTH = 4
MIN_VARIABLE_NAME_LENGTH = 2


def _build_rules() -> list[dict]:
    """构建代码质量检测规则"""
    return [
        {
            "id": "QUAL-004",
            "name": "魔法数字",
            "severity": Severity.LOW,
            "patterns": [
                # 硬编码数字（排除 0, 1, 2, -1 等常见值）
                r"(?<![a-zA-Z_])(?:if|elif|while|return|==|!=|<=|>=|<|>)\s*\d{3,}",
                r"\*\s*\d{3,}(?!\d)",
                r"\d{3,}\s*\*",
            ],
            "suggestion": "将魔法数字提取为有意义的常量",
        },
        {
            "id": "QUAL-006",
            "name": "单字符变量名",
            "severity": Severity.INFO,
            "patterns": [
                # 单字符变量赋值（排除循环变量 i, j, k, x, y, z）
                r"\b([a-hA-H]|[l-wL-W])\s*=\s*[^=]",
            ],
            "suggestion": "使用有意义的变量名提高可读性",
        },
    ]


class QualityReviewer(BaseReviewer):
    """代码质量审查器"""

    def __init__(self):
        self._rules = _build_rules()

    @property
    def name(self) -> str:
        return "Quality Review"

    @property
    def perspective(self) -> str:
        return "quality"

    @property
    def emoji(self) -> str:
        return "📊"

    def review(self, context: ReviewContext) -> ReviewResult:
        """执行代码质量审查"""
        start_time = time.time()
        findings: list[ReviewFinding] = []
        files_reviewed = 0

        try:
            for file_path in context.get_files():
                if not file_path.suffix == ".py":
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8")
                    file_findings = self._review_file(file_path, content)
                    findings.extend(file_findings)
                    files_reviewed += 1
                except Exception:
                    pass

            if context.code_snippet:
                snippet_findings = self._review_content(
                    context.code_snippet,
                    file_path=None,
                )
                findings.extend(snippet_findings)

            if context.diff_content:
                diff_findings = self._review_diff(context.diff_content)
                findings.extend(diff_findings)

            duration = time.time() - start_time

            return ReviewResult(
                perspective=self.perspective,
                findings=findings,
                duration=duration,
                success=True,
                files_reviewed=files_reviewed,
                stats={
                    "rules_checked": len(self._rules) + 3,  # 包括函数长度、嵌套深度、复杂度
                },
            )

        except Exception as e:
            return ReviewResult(
                perspective=self.perspective,
                findings=findings,
                duration=time.time() - start_time,
                success=False,
                error=str(e),
                files_reviewed=files_reviewed,
            )

    def _review_file(self, file_path: Path, content: str) -> list[ReviewFinding]:
        """审查单个文件"""
        findings: list[ReviewFinding] = []

        # 1. 正则规则检测
        findings.extend(self._review_content(content, file_path))

        # 2. 函数长度检测
        findings.extend(self._check_function_length(content, file_path))

        # 3. 嵌套深度检测
        findings.extend(self._check_nesting_depth(content, file_path))

        # 4. 圈复杂度估算
        findings.extend(self._check_complexity(content, file_path))

        return findings

    def _review_content(
        self,
        content: str,
        file_path: Path | None,
    ) -> list[ReviewFinding]:
        """审查内容（正则规则）"""
        findings: list[ReviewFinding] = []
        lines = content.split("\n")

        for rule in self._rules:
            for pattern in rule["patterns"]:
                for i, line in enumerate(lines, 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue

                    if re.search(pattern, line):
                        findings.append(
                            self.create_finding(
                                message=f"{rule['name']}: {stripped[:60]}...",
                                severity=rule["severity"],
                                file_path=file_path,
                                line_start=i,
                                rule_id=rule["id"],
                                suggestion=rule["suggestion"],
                                code_snippet=line.strip(),
                            )
                        )

        return findings

    def _check_function_length(
        self,
        content: str,
        file_path: Path | None,
    ) -> list[ReviewFinding]:
        """检测过长函数"""
        findings: list[ReviewFinding] = []
        lines = content.split("\n")

        func_pattern = re.compile(r"^\s*(async\s+)?def\s+(\w+)\s*\(")
        current_func = None
        current_func_start = 0

        for i, line in enumerate(lines):
            match = func_pattern.match(line)
            if match:
                # 检查前一个函数
                if current_func:
                    func_length = i - current_func_start
                    if func_length > MAX_FUNCTION_LINES:
                        findings.append(
                            self.create_finding(
                                message=f"函数过长: {current_func}() 有 {func_length} 行（建议 < {MAX_FUNCTION_LINES}）",
                                severity=Severity.MEDIUM,
                                file_path=file_path,
                                line_start=current_func_start + 1,
                                line_end=i,
                                rule_id="QUAL-001",
                                suggestion="考虑拆分为多个小函数",
                            )
                        )

                current_func = match.group(2)
                current_func_start = i
                _current_indent = len(line) - len(line.lstrip())  # noqa: F841

        # 检查最后一个函数
        if current_func:
            func_length = len(lines) - current_func_start
            if func_length > MAX_FUNCTION_LINES:
                findings.append(
                    self.create_finding(
                        message=f"函数过长: {current_func}() 有 {func_length} 行（建议 < {MAX_FUNCTION_LINES}）",
                        severity=Severity.MEDIUM,
                        file_path=file_path,
                        line_start=current_func_start + 1,
                        rule_id="QUAL-001",
                        suggestion="考虑拆分为多个小函数",
                    )
                )

        return findings

    def _check_nesting_depth(
        self,
        content: str,
        file_path: Path | None,
    ) -> list[ReviewFinding]:
        """检测过深嵌套"""
        findings: list[ReviewFinding] = []
        lines = content.split("\n")

        nesting_keywords = {"if", "for", "while", "with", "try", "elif", "else", "except", "finally"}

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # 计算缩进级别（假设 4 空格）
            indent = len(line) - len(line.lstrip())
            indent_level = indent // 4

            # 检查是否是嵌套关键字
            first_word = stripped.split()[0].rstrip(":") if stripped.split() else ""
            if first_word in nesting_keywords and indent_level > MAX_NESTING_DEPTH:
                findings.append(
                    self.create_finding(
                        message=f"嵌套过深: {indent_level} 层（建议 < {MAX_NESTING_DEPTH}）",
                        severity=Severity.MEDIUM,
                        file_path=file_path,
                        line_start=i,
                        rule_id="QUAL-005",
                        suggestion="考虑使用早返回、提取函数或重构条件逻辑",
                        code_snippet=stripped[:60],
                    )
                )

        return findings

    def _check_complexity(
        self,
        content: str,
        file_path: Path | None,
    ) -> list[ReviewFinding]:
        """估算圈复杂度"""
        findings: list[ReviewFinding] = []

        # 查找所有函数
        func_pattern = re.compile(r"^\s*(async\s+)?def\s+(\w+)\s*\(", re.MULTILINE)
        complexity_keywords = ["if", "elif", "for", "while", "and", "or", "except"]

        matches = list(func_pattern.finditer(content))

        for i, match in enumerate(matches):
            func_name = match.group(2)
            func_start = match.start()

            # 确定函数结束位置
            if i + 1 < len(matches):
                func_end = matches[i + 1].start()
            else:
                func_end = len(content)

            func_content = content[func_start:func_end]

            # 计算复杂度（简化版：统计分支关键字）
            complexity = 1  # 基础复杂度
            for keyword in complexity_keywords:
                complexity += len(re.findall(rf"\b{keyword}\b", func_content))

            if complexity > 10:
                line_num = content[:func_start].count("\n") + 1
                findings.append(
                    self.create_finding(
                        message=f"圈复杂度过高: {func_name}() 复杂度 {complexity}（建议 < 10）",
                        severity=Severity.HIGH if complexity > 15 else Severity.MEDIUM,
                        file_path=file_path,
                        line_start=line_num,
                        rule_id="QUAL-002",
                        suggestion="拆分复杂逻辑，使用策略模式或提取子函数",
                    )
                )

        return findings

    def _review_diff(self, diff_content: str) -> list[ReviewFinding]:
        """审查 Git diff"""
        findings: list[ReviewFinding] = []
        current_file: Path | None = None
        added_lines: list[str] = []

        for line in diff_content.split("\n"):
            if line.startswith("+++ b/"):
                if added_lines and current_file:
                    content = "\n".join(added_lines)
                    findings.extend(self._review_content(content, current_file))

                current_file = Path(line[6:])
                added_lines = []
            elif line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])

        if added_lines and current_file:
            content = "\n".join(added_lines)
            findings.extend(self._review_content(content, current_file))

        return findings


__all__ = ["QualityReviewer"]
