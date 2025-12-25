"""
Report Generator - 审查报告生成器

支持多种输出格式：
- Terminal (Rich)
- Markdown
- JSON
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.services.review.base import ReviewFinding, ReviewResult, Severity
from backend.services.review.runner import AggregatedResult


class ReportGenerator:
    """审查报告生成器"""

    # 严重程度 emoji 映射
    SEVERITY_EMOJI = {
        Severity.CRITICAL: "🔴",
        Severity.HIGH: "🟠",
        Severity.MEDIUM: "🟡",
        Severity.LOW: "🟢",
        Severity.INFO: "ℹ️",
    }

    # 严重程度中文映射
    SEVERITY_CN = {
        Severity.CRITICAL: "严重",
        Severity.HIGH: "高",
        Severity.MEDIUM: "中",
        Severity.LOW: "低",
        Severity.INFO: "信息",
    }

    # 视角 emoji 映射
    PERSPECTIVE_EMOJI = {
        "security": "🔒",
        "performance": "⚡",
        "quality": "📊",
        "memory": "🧠",
    }

    def generate_terminal(self, result: AggregatedResult) -> str:
        """生成终端格式报告（用于 Rich console）

        Args:
            result: 聚合审查结果

        Returns:
            格式化的终端报告字符串
        """
        lines: list[str] = []

        # 标题
        lines.append("=" * 60)
        lines.append("🔍 多视角代码审查报告")
        lines.append("=" * 60)
        lines.append("")

        # 摘要
        lines.append(f"📋 摘要: {result.summary}")
        lines.append(f"⏱️  耗时: {result.total_duration:.2f}s")
        lines.append(f"📁 文件: {result.total_files} 个")
        lines.append("")

        # 统计
        lines.append("📊 问题统计:")
        lines.append(f"   🔴 严重: {result.critical_count}")
        lines.append(f"   🟠 高:   {result.high_count}")
        lines.append(f"   🟡 中:   {result.medium_count}")
        lines.append(f"   🟢 低:   {result.low_count}")
        lines.append(f"   ℹ️  信息: {result.info_count}")
        lines.append("")

        # 各视角结果
        lines.append("-" * 60)
        lines.append("📑 视角详情:")
        lines.append("-" * 60)

        for perspective, perspective_result in result.results.items():
            emoji = self.PERSPECTIVE_EMOJI.get(perspective, "🔍")
            status = "✅" if perspective_result.success else "❌"
            lines.append(
                f"\n{emoji} {perspective_result.perspective.upper()} {status}"
            )
            lines.append(f"   发现 {len(perspective_result.findings)} 个问题")
            lines.append(f"   耗时 {perspective_result.duration:.2f}s")

            if not perspective_result.success and perspective_result.error:
                lines.append(f"   ⚠️ 错误: {perspective_result.error}")

        # 问题详情
        if result.all_findings:
            lines.append("")
            lines.append("-" * 60)
            lines.append("🔎 问题详情:")
            lines.append("-" * 60)

            for i, finding in enumerate(result.all_findings, 1):
                severity_emoji = self.SEVERITY_EMOJI.get(finding.severity, "⚪")
                perspective_emoji = self.PERSPECTIVE_EMOJI.get(
                    finding.perspective, "🔍"
                )

                lines.append(f"\n{i}. {severity_emoji} [{finding.rule_id or 'N/A'}]")
                lines.append(f"   {perspective_emoji} {finding.perspective.upper()}")
                lines.append(f"   📝 {finding.message}")

                if finding.file_path:
                    location = finding.format_location()
                    lines.append(f"   📍 {location}")

                if finding.suggestion:
                    lines.append(f"   💡 {finding.suggestion}")

                if finding.code_snippet:
                    lines.append(f"   📄 {finding.code_snippet[:60]}...")

        lines.append("")
        lines.append("=" * 60)
        lines.append(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 60)

        return "\n".join(lines)

    def generate_markdown(self, result: AggregatedResult) -> str:
        """生成 Markdown 格式报告

        Args:
            result: 聚合审查结果

        Returns:
            Markdown 格式报告
        """
        lines: list[str] = []

        # 标题
        lines.append("# 🔍 多视角代码审查报告")
        lines.append("")
        lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 摘要
        lines.append("## 📋 摘要")
        lines.append("")
        lines.append(f"**状态**: {result.summary}")
        lines.append("")
        lines.append(f"| 指标 | 值 |")
        lines.append("|------|-----|")
        lines.append(f"| 耗时 | {result.total_duration:.2f}s |")
        lines.append(f"| 文件数 | {result.total_files} |")
        lines.append(f"| 问题总数 | {result.total_findings} |")
        lines.append("")

        # 统计
        lines.append("## 📊 问题统计")
        lines.append("")
        lines.append("| 严重程度 | 数量 |")
        lines.append("|----------|------|")
        lines.append(f"| 🔴 严重 | {result.critical_count} |")
        lines.append(f"| 🟠 高 | {result.high_count} |")
        lines.append(f"| 🟡 中 | {result.medium_count} |")
        lines.append(f"| 🟢 低 | {result.low_count} |")
        lines.append(f"| ℹ️ 信息 | {result.info_count} |")
        lines.append("")

        # 各视角结果
        lines.append("## 📑 视角详情")
        lines.append("")

        for perspective, perspective_result in result.results.items():
            emoji = self.PERSPECTIVE_EMOJI.get(perspective, "🔍")
            status = "✅ 成功" if perspective_result.success else "❌ 失败"

            lines.append(f"### {emoji} {perspective.upper()}")
            lines.append("")
            lines.append(f"- **状态**: {status}")
            lines.append(f"- **发现**: {len(perspective_result.findings)} 个问题")
            lines.append(f"- **耗时**: {perspective_result.duration:.2f}s")

            if not perspective_result.success and perspective_result.error:
                lines.append(f"- **错误**: {perspective_result.error}")

            lines.append("")

        # 问题详情
        if result.all_findings:
            lines.append("## 🔎 问题详情")
            lines.append("")

            # 按严重程度分组
            for severity in [
                Severity.CRITICAL,
                Severity.HIGH,
                Severity.MEDIUM,
                Severity.LOW,
                Severity.INFO,
            ]:
                severity_findings = [
                    f for f in result.all_findings if f.severity == severity
                ]
                if not severity_findings:
                    continue

                emoji = self.SEVERITY_EMOJI.get(severity, "⚪")
                cn = self.SEVERITY_CN.get(severity, "未知")
                lines.append(f"### {emoji} {cn}级问题")
                lines.append("")

                for finding in severity_findings:
                    perspective_emoji = self.PERSPECTIVE_EMOJI.get(
                        finding.perspective, "🔍"
                    )
                    lines.append(f"#### [{finding.rule_id or 'N/A'}] {finding.message}")
                    lines.append("")
                    lines.append(f"- **视角**: {perspective_emoji} {finding.perspective}")

                    if finding.file_path:
                        location = finding.format_location()
                        lines.append(f"- **位置**: `{location}`")

                    if finding.suggestion:
                        lines.append(f"- **建议**: {finding.suggestion}")

                    if finding.code_snippet:
                        lines.append(f"- **代码**: `{finding.code_snippet[:80]}...`")

                    lines.append("")

        return "\n".join(lines)

    def generate_json(self, result: AggregatedResult) -> str:
        """生成 JSON 格式报告

        Args:
            result: 聚合审查结果

        Returns:
            JSON 格式报告
        """
        data = {
            "generated_at": datetime.now().isoformat(),
            "summary": result.summary,
            "stats": {
                "total_duration": result.total_duration,
                "total_files": result.total_files,
                "total_findings": result.total_findings,
                "critical_count": result.critical_count,
                "high_count": result.high_count,
                "medium_count": result.medium_count,
                "low_count": result.low_count,
                "info_count": result.info_count,
                "all_success": result.all_success,
            },
            "perspectives": {},
            "findings": [],
            "errors": result.errors,
        }

        # 视角结果
        for perspective, perspective_result in result.results.items():
            data["perspectives"][perspective] = {
                "success": perspective_result.success,
                "duration": perspective_result.duration,
                "findings_count": len(perspective_result.findings),
                "files_reviewed": perspective_result.files_reviewed,
                "error": perspective_result.error,
            }

        # 问题详情
        for finding in result.all_findings:
            data["findings"].append(
                {
                    "rule_id": finding.rule_id,
                    "severity": finding.severity.value,
                    "perspective": finding.perspective,
                    "message": finding.message,
                    "file_path": str(finding.file_path) if finding.file_path else None,
                    "line_start": finding.line_start,
                    "line_end": finding.line_end,
                    "suggestion": finding.suggestion,
                    "code_snippet": finding.code_snippet,
                }
            )

        return json.dumps(data, ensure_ascii=False, indent=2)

    def save_report(
        self,
        result: AggregatedResult,
        output_path: Path,
        format: str = "markdown",
    ) -> Path:
        """保存报告到文件

        Args:
            result: 聚合审查结果
            output_path: 输出路径
            format: 格式 (markdown, json, terminal)

        Returns:
            保存的文件路径
        """
        if format == "markdown":
            content = self.generate_markdown(result)
            if not output_path.suffix:
                output_path = output_path.with_suffix(".md")
        elif format == "json":
            content = self.generate_json(result)
            if not output_path.suffix:
                output_path = output_path.with_suffix(".json")
        else:
            content = self.generate_terminal(result)
            if not output_path.suffix:
                output_path = output_path.with_suffix(".txt")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

        return output_path


__all__ = ["ReportGenerator"]
