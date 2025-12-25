"""
Performance Reviewer - 性能审查视角

检测常见性能问题：
- PERF-001: N+1 查询模式
- PERF-002: 循环中重复计算
- PERF-003: 未使用生成器（大数据集）
- PERF-004: 同步阻塞调用
- PERF-005: 未缓存的重复计算
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
    """构建性能检测规则"""
    return [
        {
            "id": "PERF-001",
            "name": "N+1 查询模式",
            "severity": Severity.HIGH,
            "patterns": [
                # for item in items: query(item.id)
                r"for\s+\w+\s+in\s+\w+:.*\n\s+.*\.(get|filter|query|find|select)\s*\(",
                # async for with await query
                r"async\s+for\s+\w+\s+in\s+\w+:.*\n\s+.*await\s+.*\.(get|filter|query)\s*\(",
            ],
            "suggestion": "使用批量查询或预加载（prefetch_related/select_related）",
        },
        {
            "id": "PERF-002",
            "name": "循环中重复计算",
            "severity": Severity.MEDIUM,
            "patterns": [
                # for ... in ...: len(something)
                r"for\s+\w+\s+in\s+\w+:.*\n.*len\s*\(\s*\w+\s*\)",
                # while with repeated function call in condition
                r"while\s+.*\w+\(\s*\).*:",
            ],
            "suggestion": "将不变的计算提取到循环外部",
        },
        {
            "id": "PERF-003",
            "name": "大数据集未使用生成器",
            "severity": Severity.MEDIUM,
            "patterns": [
                # readlines() on potentially large files
                r"\.readlines\s*\(\s*\)",
                # list comprehension with large iteration
                r"\[.*for\s+\w+\s+in\s+range\s*\(\s*\d{5,}\s*\)",
            ],
            "suggestion": "使用生成器表达式或 yield 避免内存峰值",
        },
        {
            "id": "PERF-004",
            "name": "同步阻塞调用",
            "severity": Severity.MEDIUM,
            "patterns": [
                # time.sleep in async context
                r"async\s+def\s+\w+.*\n(?:.*\n)*?\s+time\.sleep\s*\(",
                # requests in async function
                r"async\s+def\s+\w+.*\n(?:.*\n)*?\s+requests\.(get|post|put|delete)\s*\(",
            ],
            "suggestion": "在 async 上下文中使用 asyncio.sleep 和 httpx/aiohttp",
        },
        {
            "id": "PERF-005",
            "name": "未缓存的重复计算",
            "severity": Severity.LOW,
            "patterns": [
                # Same function called multiple times with same args
                r"(\w+)\s*\(\s*([^)]+)\s*\).*\n.*\1\s*\(\s*\2\s*\)",
            ],
            "suggestion": "考虑使用 @functools.cache 或 @lru_cache 缓存结果",
        },
    ]


class PerformanceReviewer(BaseReviewer):
    """性能审查器"""

    def __init__(self):
        self._rules = _build_rules()

    @property
    def name(self) -> str:
        return "Performance Review"

    @property
    def perspective(self) -> str:
        return "performance"

    @property
    def emoji(self) -> str:
        return "⚡"

    def review(self, context: ReviewContext) -> ReviewResult:
        """执行性能审查"""
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
        return self._review_content(content, file_path)

    def _review_content(
        self,
        content: str,
        file_path: Path | None,
    ) -> list[ReviewFinding]:
        """审查内容"""
        findings: list[ReviewFinding] = []

        for rule in self._rules:
            for pattern in rule["patterns"]:
                # 使用 DOTALL 和 MULTILINE 模式
                matches = list(re.finditer(pattern, content, re.MULTILINE | re.DOTALL))

                for match in matches:
                    # 计算行号
                    line_start = content[: match.start()].count("\n") + 1
                    matched_text = match.group(0)
                    # 截取匹配的第一行作为代码片段
                    snippet = matched_text.split("\n")[0].strip()[:80]

                    findings.append(
                        self.create_finding(
                            message=f"{rule['name']}: {snippet}...",
                            severity=rule["severity"],
                            file_path=file_path,
                            line_start=line_start,
                            rule_id=rule["id"],
                            suggestion=rule["suggestion"],
                            code_snippet=snippet,
                        )
                    )

        return findings

    def _review_diff(self, diff_content: str) -> list[ReviewFinding]:
        """审查 Git diff"""
        findings: list[ReviewFinding] = []
        current_file: Path | None = None
        added_lines: list[str] = []
        line_offset = 0

        for line in diff_content.split("\n"):
            if line.startswith("+++ b/"):
                # 检查之前积累的内容
                if added_lines and current_file:
                    content = "\n".join(added_lines)
                    file_findings = self._review_content(content, current_file)
                    findings.extend(file_findings)

                current_file = Path(line[6:])
                added_lines = []
                line_offset = 0
            elif line.startswith("@@ "):
                match = re.search(r"\+(\d+)", line)
                if match:
                    line_offset = int(match.group(1))
            elif line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])
                line_offset += 1

        # 处理最后一个文件
        if added_lines and current_file:
            content = "\n".join(added_lines)
            file_findings = self._review_content(content, current_file)
            findings.extend(file_findings)

        return findings


__all__ = ["PerformanceReviewer"]
