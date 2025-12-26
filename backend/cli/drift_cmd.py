"""
memory-anchor drift-check - 偏离度检查

计算当前工作与北极星目标的语义偏离度。

使用方法：
    ./ma drift-check "最近在做 XXX"
    ./ma drift-check --file recent_work.md
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


def drift_check_command(
    work_summary: Optional[str] = typer.Argument(
        None,
        help="当前工作摘要（一句话描述最近在做什么）",
    ),
    file: Optional[Path] = typer.Option(
        None,
        "--file",
        "-f",
        help="从文件读取工作摘要",
    ),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="项目名称",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="显示详细信息（包括相似度数值）",
    ),
):
    """
    检查当前工作与北极星的偏离度。

    示例：
        ./ma drift-check "在优化 embedding 模型的性能"
        ./ma drift-check "重构了整个前端架构"
        ./ma drift-check --file CURRENT_TASK.md
    """
    # 获取工作摘要
    if file:
        if not file.exists():
            console.print(f"[red]文件不存在: {file}[/red]")
            raise typer.Exit(1)
        work_summary = file.read_text(encoding="utf-8")
    elif not work_summary:
        console.print("[yellow]请提供工作摘要：[/yellow]")
        console.print("  ./ma drift-check \"最近在做什么\"")
        console.print("  ./ma drift-check --file CURRENT_TASK.md")
        raise typer.Exit(1)

    # 设置项目
    if project:
        os.environ["MCP_MEMORY_PROJECT_ID"] = project

    # 查找北极星
    from backend.services.drift import find_north_star_content

    north_star = find_north_star_content()
    if not north_star:
        console.print("[red]未找到北极星文件 (.ai/NORTH_STAR.md)[/red]")
        console.print("[dim]提示：先创建北极星文件，定义项目的核心目标[/dim]")
        raise typer.Exit(1)

    # 计算偏离度
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("计算偏离度...", total=None)

        from backend.services.drift import calculate_drift
        result = calculate_drift(north_star, work_summary)

    # 显示结果
    console.print()
    console.print(Panel.fit(
        "[bold]偏离度检查报告[/bold]",
        border_style="blue",
    ))

    # 偏离度仪表盘
    drift_bar = _create_drift_bar(result.drift_percent)
    console.print(f"\n{result.emoji} [bold]偏离度: {result.drift_percent}%[/bold]")
    console.print(drift_bar)
    console.print(f"[dim]{result.message}[/dim]\n")

    # 详细信息表格
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Label", style="dim")
    table.add_column("Value")

    table.add_row("北极星", result.north_star_summary)
    table.add_row("当前工作", result.work_summary)

    if verbose:
        table.add_row("余弦相似度", f"{result.similarity:.4f}")
        table.add_row("偏离等级", result.level)

    console.print(table)

    # 根据偏离度给出建议
    console.print()
    if result.level == "aligned":
        console.print("[green]✓ 工作方向正确，继续推进[/green]")
    elif result.level == "slight":
        console.print("[yellow]⚡ 建议：定期回顾北极星，确保不偏离[/yellow]")
    elif result.level == "moderate":
        console.print("[yellow]⚠️ 建议：暂停一下，重新阅读北极星，确认方向[/yellow]")
    elif result.level == "severe":
        console.print("[red]🚨 警告：当前工作严重偏离目标，建议立即调整[/red]")
    else:
        console.print("[red]🛑 危险：已完全偏离北极星，请停止当前工作，重新规划[/red]")


def _create_drift_bar(drift_percent: float, width: int = 30) -> str:
    """创建偏离度进度条"""
    filled = int(drift_percent / 100 * width)
    empty = width - filled

    # 根据偏离度选择颜色
    if drift_percent <= 20:
        color = "green"
    elif drift_percent <= 40:
        color = "yellow"
    elif drift_percent <= 60:
        color = "bright_yellow"
    elif drift_percent <= 80:
        color = "red"
    else:
        color = "bright_red"

    bar = f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"
    return f"[{bar}] {drift_percent:.0f}%"


__all__ = ["drift_check_command"]
