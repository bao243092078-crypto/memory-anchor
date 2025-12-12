"""
memory-anchor status - 查看记忆状态

显示当前项目配置、连接状态和记忆统计。
"""

import os
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def status_command(
    project: Optional[str] = typer.Option(
        None,
        "--project", "-p",
        help="项目名称（默认使用环境变量 MCP_MEMORY_PROJECT_ID）",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="显示详细信息",
    ),
):
    """
    查看 Memory Anchor 状态

    显示项目配置、Qdrant 连接状态和记忆统计。
    """
    # 设置项目 ID
    if project:
        os.environ["MCP_MEMORY_PROJECT_ID"] = project

    from backend.config import get_config, reset_config

    # 强制重新加载配置
    reset_config()
    config = get_config()

    console.print(Panel.fit(
        "[bold blue]Memory Anchor[/bold blue] - 系统状态",
        border_style="blue",
    ))
    console.print()

    # 1. 项目配置
    config_table = Table(title="📋 项目配置", show_header=False, box=None)
    config_table.add_column("Key", style="cyan")
    config_table.add_column("Value")

    config_table.add_row("项目名称", config.project_name)
    config_table.add_row("项目类型", config.project_type)
    config_table.add_row("数据目录", str(config.data_dir))
    config_table.add_row("Collection", config.collection_name)
    config_table.add_row("向量维度", str(config.vector_size))

    console.print(config_table)
    console.print()

    # 2. 宪法层状态
    constitution_table = Table(title="🏛️ 宪法层", show_header=True)
    constitution_table.add_column("#", style="dim", width=3)
    constitution_table.add_column("ID", style="cyan", width=20)
    constitution_table.add_column("分类", width=10)
    constitution_table.add_column("内容", overflow="fold")

    for i, item in enumerate(config.constitution, 1):
        content = item.content[:60] + "..." if len(item.content) > 60 else item.content
        constitution_table.add_row(
            str(i),
            item.id,
            item.category or "-",
            content,
        )

    console.print(constitution_table)
    console.print(f"[dim]共 {len(config.constitution)} 条宪法层条目[/dim]")
    console.print()

    # 3. Qdrant 连接状态
    console.print("[bold]🔗 Qdrant 连接状态[/bold]")

    try:
        from backend.services.search import SearchService
        service = SearchService()
        stats = service.get_stats()

        status_table = Table(show_header=False, box=None)
        status_table.add_column("Key", style="cyan")
        status_table.add_column("Value")

        status_table.add_row("连接模式", f"[green]{stats['mode']}[/green]")
        status_table.add_row("Collection", stats["collection_name"])
        status_table.add_row("记忆总数", str(stats["total_count"]))
        status_table.add_row("向量维度", str(stats["vector_size"]))
        status_table.add_row("距离度量", stats["distance"])

        console.print(status_table)
        console.print("[green]✓ Qdrant 连接正常[/green]")

    except Exception as e:
        console.print(f"[red]✗ Qdrant 连接失败: {e}[/red]")
        if verbose:
            console.print_exception()

    console.print()

    # 4. 配置文件路径
    if verbose:
        console.print("[bold]📁 配置文件[/bold]")
        paths_table = Table(show_header=False, box=None)
        paths_table.add_column("类型", style="cyan")
        paths_table.add_column("路径")

        paths_table.add_row("宪法层配置", str(config.constitution_yaml_path))
        paths_table.add_row("Qdrant 路径", str(config.qdrant_path))
        paths_table.add_row("SQLite 路径", str(config.sqlite_path))

        console.print(paths_table)


if __name__ == "__main__":
    typer.run(status_command)
