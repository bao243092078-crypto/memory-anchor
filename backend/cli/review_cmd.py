"""
Review Command - 多视角代码审查命令

提供四视角并行审查：
- Security: 安全漏洞检测
- Performance: 性能问题检测
- Quality: 代码质量检测
- Memory: 记忆系统完整性检测
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from backend.services.review import (
    AggregatedResult,
    ReportGenerator,
    ReviewContext,
    ReviewRunner,
    Severity,
)

console = Console()

# 严重程度样式
SEVERITY_STYLE = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "green",
    Severity.INFO: "blue",
}

SEVERITY_EMOJI = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "🟢",
    Severity.INFO: "ℹ️",
}

PERSPECTIVE_EMOJI = {
    "security": "🔒",
    "performance": "⚡",
    "quality": "📊",
    "memory": "🧠",
}


def review_command(
    target: Optional[str] = typer.Argument(
        None,
        help="审查目标（文件或目录路径，默认当前目录）",
    ),
    perspectives: Optional[str] = typer.Option(
        None,
        "--perspectives",
        "-p",
        help="指定审查视角（逗号分隔：security,performance,quality,memory）",
    ),
    format: str = typer.Option(
        "terminal",
        "--format",
        "-f",
        help="输出格式（terminal, markdown, json）",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="保存报告到文件",
    ),
    diff: bool = typer.Option(
        False,
        "--diff",
        "-d",
        help="审查 Git 暂存区的变更（git diff --cached）",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="显示详细输出",
    ),
):
    """
    多视角代码审查

    四个审查视角：

    - 🔒 Security: 检测安全漏洞（硬编码密钥、SQL 注入、命令注入等）

    - ⚡ Performance: 检测性能问题（N+1 查询、阻塞调用等）

    - 📊 Quality: 检测代码质量（函数过长、复杂度过高等）

    - 🧠 Memory: 检测记忆系统使用问题（直接写宪法层、缺少错误处理等）

    示例：

        ma review                    # 审查当前目录

        ma review backend/           # 审查指定目录

        ma review -p security,memory # 只运行安全和记忆审查

        ma review --diff             # 审查 Git 暂存区变更

        ma review -o report.md -f markdown  # 保存 Markdown 报告
    """
    # 解析目标路径
    if target:
        target_path = Path(target).resolve()
    else:
        target_path = Path.cwd()

    if not target_path.exists():
        console.print(f"[red]错误: 路径不存在: {target_path}[/red]")
        raise typer.Exit(1)

    # 解析视角
    perspective_list: list[str] | None = None
    if perspectives:
        perspective_list = [p.strip() for p in perspectives.split(",")]
        valid_perspectives = {"security", "performance", "quality", "memory"}
        invalid = set(perspective_list) - valid_perspectives
        if invalid:
            console.print(f"[red]错误: 无效的视角: {invalid}[/red]")
            console.print(f"[dim]可用视角: {valid_perspectives}[/dim]")
            raise typer.Exit(1)

    # 创建审查上下文
    context = ReviewContext(target_path=target_path)

    # 如果是 diff 模式，获取 Git diff
    if diff:
        import subprocess

        try:
            git_result = subprocess.run(
                ["git", "diff", "--cached"],
                capture_output=True,
                text=True,
                cwd=target_path if target_path.is_dir() else target_path.parent,
            )
            if git_result.returncode == 0:
                context.diff_content = git_result.stdout
                if not context.diff_content.strip():
                    console.print("[yellow]暂存区没有变更[/yellow]")
                    raise typer.Exit(0)
            else:
                console.print(f"[red]Git diff 失败: {git_result.stderr}[/red]")
                raise typer.Exit(1)
        except FileNotFoundError:
            console.print("[red]错误: 未安装 Git[/red]")
            raise typer.Exit(1)

    # 显示开始信息
    console.print()
    console.print(
        Panel(
            f"[bold]🔍 多视角代码审查[/bold]\n\n"
            f"目标: [cyan]{target_path}[/cyan]\n"
            f"模式: {'Git Diff' if diff else '目录扫描'}",
            title="Memory Anchor Review",
            border_style="blue",
        )
    )

    # 创建运行器
    runner = ReviewRunner(perspectives=perspective_list)

    # 显示要运行的视角
    perspectives_str = ", ".join(
        f"{PERSPECTIVE_EMOJI.get(p, '🔍')} {p}" for p in runner.perspectives
    )
    console.print(f"\n[dim]视角: {perspectives_str}[/dim]\n")

    # 执行审查（带进度条）
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("正在审查...", total=None)

        def on_progress(perspective: str, status: str, pct: float):
            emoji = PERSPECTIVE_EMOJI.get(perspective, "🔍")
            if status == "started":
                progress.update(task, description=f"{emoji} 正在运行 {perspective}...")
            elif status == "completed":
                progress.update(task, description=f"{emoji} {perspective} ✅")
            elif status == "failed":
                progress.update(task, description=f"{emoji} {perspective} ❌")

        result = runner.run(context, progress_callback=on_progress)

    # 显示结果
    console.print()
    _display_results(result, verbose)

    # 保存报告
    if output:
        generator = ReportGenerator()
        saved_path = generator.save_report(result, output, format=format)
        console.print(f"\n[green]✅ 报告已保存到: {saved_path}[/green]")

    # 如果是 terminal 格式且没有指定输出，打印完整报告
    if format == "terminal" and not output:
        pass  # 已经在 _display_results 中显示了
    elif format != "terminal" and not output:
        generator = ReportGenerator()
        if format == "markdown":
            console.print(generator.generate_markdown(result))
        elif format == "json":
            console.print(generator.generate_json(result))

    # 返回码
    if result.has_blocking_issues:
        raise typer.Exit(1)


def _display_results(result: AggregatedResult, verbose: bool = False):
    """显示审查结果"""
    # 摘要面板
    summary_style = "red" if result.has_blocking_issues else "green"
    console.print(
        Panel(
            f"[{summary_style}]{result.summary}[/{summary_style}]",
            title="📋 审查结果",
            border_style=summary_style,
        )
    )

    # 统计表格
    stats_table = Table(title="📊 问题统计", show_header=True)
    stats_table.add_column("严重程度", style="bold")
    stats_table.add_column("数量", justify="right")

    stats_table.add_row("🔴 严重", str(result.critical_count))
    stats_table.add_row("🟠 高", str(result.high_count))
    stats_table.add_row("🟡 中", str(result.medium_count))
    stats_table.add_row("🟢 低", str(result.low_count))
    stats_table.add_row("ℹ️ 信息", str(result.info_count))
    stats_table.add_row("", "─" * 5)
    stats_table.add_row("[bold]总计[/bold]", f"[bold]{result.total_findings}[/bold]")

    console.print(stats_table)

    # 视角详情
    console.print("\n[bold]📑 视角详情[/bold]\n")

    for perspective, perspective_result in result.results.items():
        emoji = PERSPECTIVE_EMOJI.get(perspective, "🔍")
        status = "[green]✅[/green]" if perspective_result.success else "[red]❌[/red]"
        count = len(perspective_result.findings)
        duration = perspective_result.duration

        console.print(
            f"  {emoji} [bold]{perspective.upper()}[/bold] {status}  "
            f"[dim]({count} 问题, {duration:.2f}s)[/dim]"
        )

        if not perspective_result.success and perspective_result.error:
            console.print(f"     [red]⚠️ {perspective_result.error}[/red]")

    # 问题列表（只显示 CRITICAL 和 HIGH，除非 verbose）
    if result.all_findings:
        console.print("\n[bold]🔎 问题详情[/bold]\n")

        shown = 0
        hidden = 0

        for finding in result.all_findings:
            # 非 verbose 模式只显示 CRITICAL 和 HIGH
            if not verbose and finding.severity not in (Severity.CRITICAL, Severity.HIGH):
                hidden += 1
                continue

            shown += 1
            emoji = SEVERITY_EMOJI.get(finding.severity, "⚪")
            style = SEVERITY_STYLE.get(finding.severity, "")
            perspective_emoji = PERSPECTIVE_EMOJI.get(finding.perspective, "🔍")

            console.print(f"  {emoji} [{style}][{finding.rule_id or 'N/A'}][/{style}]")
            console.print(f"     {perspective_emoji} {finding.perspective.upper()}")
            console.print(f"     📝 {finding.message}")

            if finding.file_path:
                location = finding.format_location()
                console.print(f"     📍 [cyan]{location}[/cyan]")

            if finding.suggestion:
                console.print(f"     💡 [dim]{finding.suggestion}[/dim]")

            console.print()

        if hidden > 0:
            console.print(
                f"  [dim]... 还有 {hidden} 个低优先级问题（使用 -v 查看全部）[/dim]"
            )

    # 执行时间
    console.print(f"\n[dim]⏱️ 总耗时: {result.total_duration:.2f}s[/dim]")


__all__ = ["review_command"]
