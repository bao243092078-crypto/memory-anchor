"""
conflicts_cmd.py - 冲突检测命令 (v3.0)

扫描项目记忆中的潜在冲突，帮助发现矛盾信息。
"""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import Optional

console = Console()


def conflicts_command(
    project: Optional[str] = typer.Option(
        None,
        "--project", "-p",
        help="项目 ID（默认从环境变量读取）",
    ),
    layer: Optional[str] = typer.Option(
        None,
        "--layer", "-l",
        help="过滤层级（verified_fact/event_log）",
    ),
    limit: int = typer.Option(
        50,
        "--limit", "-n",
        help="扫描记忆数量限制",
    ),
    json_output: bool = typer.Option(
        False,
        "--json", "-j",
        help="输出 JSON 格式",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="显示详细信息",
    ),
):
    """
    扫描项目记忆中的潜在冲突

    检测时间冲突、来源冲突和置信度冲突。
    """
    import json
    import os

    # 设置项目 ID
    if project:
        os.environ["MCP_MEMORY_PROJECT_ID"] = project

    project_id = project or os.getenv("MCP_MEMORY_PROJECT_ID", "unknown")

    console.print()
    console.print(Panel.fit(
        f"[bold cyan]Memory Conflict Scanner[/bold cyan]\n"
        f"[dim]扫描项目 {project_id} 的潜在冲突[/dim]",
        border_style="cyan"
    ))

    try:
        # 初始化服务
        from backend.services.search import SearchService
        from backend.core.conflict_detector import ConflictDetector

        search_service = SearchService(project_id=project_id)
        detector = ConflictDetector(search_service)

        # 扫描冲突
        console.print(f"\n[dim]正在扫描最近 {limit} 条记忆...[/dim]")

        conflicts = detector.scan_project(
            project_id=project_id,
            layer=layer,
            limit=limit,
        )

        if json_output:
            console.print_json(json.dumps(conflicts, ensure_ascii=False, indent=2))
            return

        # 显示结果
        if not conflicts:
            console.print("\n[green]✅ 未检测到冲突[/green]")
            console.print("[dim]所有记忆状态正常。[/dim]\n")
            return

        console.print(f"\n[yellow]⚠️ 检测到 {len(conflicts)} 个潜在冲突[/yellow]\n")

        # 按冲突类型分组
        by_type = {}
        for c in conflicts:
            conflict_type = c["conflict"]["conflict_type"] or "unknown"
            if conflict_type not in by_type:
                by_type[conflict_type] = []
            by_type[conflict_type].append(c)

        # 显示统计
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("冲突类型", style="cyan", width=15)
        table.add_column("数量", justify="right", width=8)
        table.add_column("严重程度", justify="center", width=12)

        type_names = {
            "temporal": "⏰ 时间冲突",
            "source": "👤 来源冲突",
            "confidence": "📊 置信度冲突",
            "semantic": "💬 语义冲突",
        }

        for conflict_type, items in by_type.items():
            type_display = type_names.get(conflict_type, conflict_type)
            # 找出最高严重程度
            severities = [c["conflict"]["severity"] for c in items]
            if "high" in severities:
                severity = "[red]高[/red]"
            elif "medium" in severities:
                severity = "[yellow]中[/yellow]"
            else:
                severity = "[green]低[/green]"

            table.add_row(type_display, str(len(items)), severity)

        console.print(table)

        # 详细信息
        if verbose:
            console.print("\n[bold]详细信息:[/bold]\n")

            for i, c in enumerate(conflicts[:10], 1):
                conflict = c["conflict"]
                console.print(f"[cyan]{i}. {type_names.get(conflict['conflict_type'], conflict['conflict_type'])}[/cyan]")
                console.print(f"   [dim]记忆:[/dim] {c['memory_content']}")
                console.print(f"   [dim]建议:[/dim] {conflict['resolution_hint']}")
                if conflict.get("details"):
                    console.print(f"   [dim]详情:[/dim] {conflict['details']}")
                console.print()

            if len(conflicts) > 10:
                console.print(f"[dim]... 还有 {len(conflicts) - 10} 个冲突，使用 --json 查看全部[/dim]\n")

        else:
            console.print("\n[dim]使用 --verbose 查看详细信息[/dim]\n")

    except Exception as e:
        console.print(f"\n[red]❌ 扫描失败: {e}[/red]\n")
        raise typer.Exit(1)
