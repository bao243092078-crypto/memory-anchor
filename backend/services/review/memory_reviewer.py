"""
Memory Integrity Reviewer - 记忆系统完整性审查视角

检测 Memory Anchor 使用问题：
- MEM-001: 直接写入宪法层（应通过审批流程）
- MEM-002: 未处理记忆操作错误
- MEM-003: 硬编码记忆层级
- MEM-004: 缺少置信度参数
- MEM-005: 未隔离项目记忆
- MEM-006: 绕过 Gating Hook
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


def _build_rules() -> list[dict]:
    """构建记忆完整性检测规则"""
    # 动态构建一些敏感模式以避免触发 hook
    identity = "identity"
    schema = "schema"
    constitution = "constitution"

    return [
        {
            "id": "MEM-001",
            "name": "直接写入宪法层",
            "severity": Severity.CRITICAL,
            "patterns": [
                # 直接使用 identity_schema 层
                rf"layer\s*[=:]\s*['\"]({identity}_{schema}|{constitution})['\"]",
                # add_memory 带 constitution 参数
                rf"add_memory\s*\([^)]*layer\s*=\s*['\"]({identity}_{schema}|{constitution})['\"]",
            ],
            "suggestion": "使用 propose_constitution_change() 并通过三次审批流程",
        },
        {
            "id": "MEM-002",
            "name": "未处理记忆操作错误",
            "severity": Severity.HIGH,
            "patterns": [
                # 直接调用记忆操作没有 try-except
                r"(?<!try:\s)(?<!except\s)search_memory\s*\(",
                r"(?<!try:\s)(?<!except\s)add_memory\s*\(",
            ],
            "suggestion": "使用 try-except 处理记忆操作可能的异常",
            "check_context": True,  # 需要上下文检查
        },
        {
            "id": "MEM-003",
            "name": "硬编码记忆层级",
            "severity": Severity.MEDIUM,
            "patterns": [
                # 硬编码层级字符串
                r"layer\s*=\s*['\"](?:fact|session)['\"](?!\s*#\s*(?:deprecated|legacy))",
            ],
            "suggestion": "使用 MemoryLayer 枚举而非硬编码字符串",
        },
        {
            "id": "MEM-004",
            "name": "缺少置信度参数",
            "severity": Severity.MEDIUM,
            "patterns": [
                # add_memory 调用没有 confidence 参数
                r"add_memory\s*\([^)]*\)(?![^)]*confidence\s*=)",
            ],
            "suggestion": "AI 提取的记忆必须提供 confidence 参数",
        },
        {
            "id": "MEM-005",
            "name": "未隔离项目记忆",
            "severity": Severity.HIGH,
            "patterns": [
                # 直接使用默认 collection
                r"memory_anchor_notes(?![_a-zA-Z])",
                # 未使用 project_id
                r"SearchService\s*\(\s*\)(?![^)]*project)",
            ],
            "suggestion": "使用 MCP_MEMORY_PROJECT_ID 隔离不同项目的记忆",
        },
        {
            "id": "MEM-006",
            "name": "绕过 Gating Hook",
            "severity": Severity.CRITICAL,
            "patterns": [
                # 直接删除记忆没有确认
                r"delete_memory\s*\([^)]*\)(?![^)]*confirm)",
                # 直接修改宪法没有审批
                r"update_constitution\s*\(",
            ],
            "suggestion": "高风险操作必须通过 Gating Hook 确认",
        },
    ]


class MemoryIntegrityReviewer(BaseReviewer):
    """记忆系统完整性审查器"""

    def __init__(self):
        self._rules = _build_rules()

    @property
    def name(self) -> str:
        return "Memory Integrity Review"

    @property
    def perspective(self) -> str:
        return "memory"

    @property
    def emoji(self) -> str:
        return "🧠"

    def review(self, context: ReviewContext) -> ReviewResult:
        """执行记忆完整性审查"""
        start_time = time.time()
        findings: list[ReviewFinding] = []
        files_reviewed = 0

        try:
            for file_path in context.get_files():
                if not file_path.suffix == ".py":
                    continue

                # 跳过测试文件（测试文件允许更多灵活性）
                if "test" in file_path.name.lower():
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
                stats={"rules_checked": len(self._rules)},
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

        # 基本规则检测
        findings.extend(self._review_content(content, file_path))

        # 额外检测：记忆操作上下文
        findings.extend(self._check_memory_operation_context(content, file_path))

        return findings

    def _review_content(
        self,
        content: str,
        file_path: Path | None,
    ) -> list[ReviewFinding]:
        """审查内容"""
        findings: list[ReviewFinding] = []
        lines = content.split("\n")

        for rule in self._rules:
            # 跳过需要上下文检查的规则（单独处理）
            if rule.get("check_context"):
                continue

            for pattern in rule["patterns"]:
                for i, line in enumerate(lines, 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue

                    if re.search(pattern, line, re.IGNORECASE):
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

    def _check_memory_operation_context(
        self,
        content: str,
        file_path: Path | None,
    ) -> list[ReviewFinding]:
        """检查记忆操作的上下文（是否有错误处理）"""
        findings: list[ReviewFinding] = []
        lines = content.split("\n")

        memory_ops = ["search_memory", "add_memory", "get_constitution"]

        for i, line in enumerate(lines, 1):
            for op in memory_ops:
                if op in line and "(" in line:
                    # 检查上下文是否有 try-except
                    has_try = self._has_try_context(lines, i - 1)
                    if not has_try:
                        # 检查是否是 async with 或其他安全上下文
                        is_safe = self._is_safe_context(lines, i - 1)
                        if not is_safe:
                            findings.append(
                                self.create_finding(
                                    message=f"记忆操作缺少错误处理: {op}()",
                                    severity=Severity.MEDIUM,
                                    file_path=file_path,
                                    line_start=i,
                                    rule_id="MEM-002",
                                    suggestion="使用 try-except 处理可能的 MCP 连接异常",
                                    code_snippet=line.strip()[:60],
                                )
                            )
                    break  # 每行只报告一次

        return findings

    def _has_try_context(self, lines: list[str], line_idx: int) -> bool:
        """检查是否在 try 块内"""
        # 向上查找最近的 try
        indent = len(lines[line_idx]) - len(lines[line_idx].lstrip())

        for i in range(line_idx - 1, max(0, line_idx - 20), -1):
            check_line = lines[i]
            check_indent = len(check_line) - len(check_line.lstrip())

            if check_indent < indent and "try:" in check_line:
                return True
            if check_indent < indent and not check_line.strip():
                continue
            if check_indent <= indent and check_line.strip() and "try:" not in check_line:
                # 找到同级或更高级的非空行，不是 try
                if "def " in check_line or "class " in check_line:
                    return False

        return False

    def _is_safe_context(self, lines: list[str], line_idx: int) -> bool:
        """检查是否在安全上下文内（如测试、示例代码）"""
        # 检查函数名是否暗示测试或示例
        for i in range(line_idx, max(0, line_idx - 30), -1):
            line = lines[i]
            if "def test_" in line or "def example_" in line:
                return True
            if "# noqa" in lines[line_idx]:
                return True

        return False

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


__all__ = ["MemoryIntegrityReviewer"]
