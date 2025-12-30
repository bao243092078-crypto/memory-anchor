"""
budget_cmd.py - 上下文预算查看命令 (v3.0)

显示各层记忆的 token 使用情况，帮助了解上下文消耗。
"""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import Optional

console = Console()


def budget_command(
    project: Optional[str] = typer.Option(
        None,
        "--project", "-p",
        help="项目 ID（默认从环境变量读取）",
    ),
    json_output: bool = typer.Option(
        False,
        "--json", "-j",
        help="输出 JSON 格式",
    ),
    simulate: bool = typer.Option(
        False,
        "--simulate", "-s",
        help="模拟加载记忆并显示预算使用",
    ),
):
    """
    查看上下文预算使用情况

    显示各层记忆的 token 分配和使用情况，帮助了解上下文消耗。
    """
    import json
    import os
    from backend.core.context_budget import ContextBudgetManager, ContextBudget

    # 设置项目 ID
    if project:
        os.environ["MCP_MEMORY_PROJECT_ID"] = project

    # 创建预算管理器
    manager = ContextBudgetManager()

    if simulate:
        # 模拟加载记忆
        _simulate_budget_usage(manager, project or os.getenv("MCP_MEMORY_PROJECT_ID", "unknown"))

    report = manager.get_report()

    if json_output:
        console.print_json(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return

    # Rich 格式输出
    _print_budget_report(report, manager.budget)


def _simulate_budget_usage(manager: "ContextBudgetManager", project_id: str):
    """模拟加载记忆，计算实际使用情况"""
    from backend.core.memory_kernel import get_memory_kernel

    try:
        kernel = get_memory_kernel()

        # 加载宪法层
        constitution = kernel.get_constitution()
        for mem in constitution:
            tokens = manager.estimate_memory_tokens(mem)
            manager.allocate("identity_schema", tokens, 1)

        # 搜索事实层（模拟常见查询）
        facts = kernel.search_memory(query="项目", layer="verified_fact", limit=20)
        for mem in facts:
            if not mem.get("is_constitution"):
                tokens = manager.estimate_memory_tokens(mem)
                manager.allocate("verified_fact", tokens, 1)

        # 搜索事件层
        events = kernel.search_memory(query="事件", layer="event_log", limit=10)
        for mem in events:
            tokens = manager.estimate_memory_tokens(mem)
            manager.allocate("event_log", tokens, 1)

    except Exception as e:
        console.print(f"[yellow]模拟加载失败: {e}[/yellow]")


def _print_budget_report(report, budget):
    """打印预算报告"""
    from backend.core.context_budget import BudgetReport

    # 标题
    console.print()
    console.print(Panel.fit(
        "[bold cyan]Context Budget Report[/bold cyan]\n"
        "[dim]上下文预算使用情况（v3.0）[/dim]",
        border_style="cyan"
    ))

    # 表格
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("层级", style="cyan", width=20)
    table.add_column("已用", justify="right", width=8)
    table.add_column("上限", justify="right", width=8)
    table.add_column("使用率", justify="center", width=12)
    table.add_column("状态", justify="center", width=8)

    for layer, usage in report.layers.items():
        # 进度条
        bar_len = 10
        filled = int(usage.usage_ratio * bar_len)
        empty = bar_len - filled
        if filled > 0:
            bar = f"[green]{'█' * filled}[/green]" + f"[dim]{'░' * empty}[/dim]"
        else:
            bar = f"[dim]{'░' * bar_len}[/dim]"

        # 状态
        if usage.usage_ratio > 0.9:
            status = "[red]⚠️ 高[/red]"
        elif usage.usage_ratio > 0.7:
            status = "[yellow]⚡ 中[/yellow]"
        else:
            status = "[green]✅ 低[/green]"

        # 格式化层级名称
        layer_display = {
            "identity_schema": "L0 身份层",
            "active_context": "L1 工作记忆",
            "event_log": "L2 事件层",
            "verified_fact": "L3 事实层",
            "operational_knowledge": "L4 操作层",
        }.get(layer, layer)

        table.add_row(
            layer_display,
            str(usage.allocated),
            str(usage.limit),
            bar,
            status
        )

    console.print(table)

    # 总计
    total_bar_len = 20
    total_filled = int(report.total_usage_ratio * total_bar_len)
    total_bar = "█" * total_filled + "░" * (total_bar_len - total_filled)

    total_status = "[red]🔴 超限[/red]" if report.is_over_budget else "[green]✅ 正常[/green]"

    console.print()
    console.print(f"[bold]总计[/bold]: [{total_bar}] {report.total_allocated}/{report.total_limit} tokens {total_status}")
    console.print()

    # 配置说明
    console.print("[dim]配置说明:[/dim]")
    console.print(f"[dim]  - 字符/token 比例: {budget.chars_per_token}[/dim]")
    console.print(f"[dim]  - 截断策略: {budget.truncate_strategy}[/dim]")
    console.print(f"[dim]  - 可通过 MA_BUDGET_* 环境变量覆盖[/dim]")
    console.print()
