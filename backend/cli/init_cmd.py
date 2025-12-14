"""
memory-anchor init - 初始化新项目

交互式向导，帮助用户创建记忆项目配置。
"""

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from backend.config import (
    DEFAULT_GLOBAL_CONFIG_DIR,
    create_default_constitution_yaml,
)

console = Console()


def init_command(
    project_name: Optional[str] = typer.Argument(
        None,
        help="项目名称（留空则交互式输入）",
    ),
    project_type: Optional[str] = typer.Option(
        None,
        "--type", "-t",
        help="项目类型: patient-care / ai-development / knowledge-base",
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="强制覆盖已存在的配置",
    ),
):
    """
    初始化 Memory Anchor 项目

    创建项目配置文件和宪法层模板。
    """
    console.print(Panel.fit(
        "[bold blue]Memory Anchor[/bold blue] - AI 记忆系统初始化向导",
        border_style="blue",
    ))
    console.print()

    # 1. 获取项目名称
    if not project_name:
        project_name = Prompt.ask(
            "[bold]项目名称[/bold]",
            default="my-project",
        )

    # 安全过滤项目名
    safe_name = "".join(c for c in project_name if c.isalnum() or c in ("_", "-"))
    if safe_name != project_name:
        console.print(f"[yellow]项目名称已标准化为: {safe_name}[/yellow]")
        project_name = safe_name

    # 2. 检查项目是否已存在
    project_dir = DEFAULT_GLOBAL_CONFIG_DIR / "projects" / project_name
    constitution_path = project_dir / "constitution.yaml"

    if constitution_path.exists() and not force:
        console.print(f"[red]项目 '{project_name}' 已存在！[/red]")
        if not Confirm.ask("是否覆盖？"):
            raise typer.Exit(1)

    # 3. 选择项目类型
    if not project_type:
        console.print()
        console.print("[bold]选择项目类型：[/bold]")

        type_table = Table(show_header=False, box=None, padding=(0, 2))
        type_table.add_column("选项", style="cyan")
        type_table.add_column("说明")
        type_table.add_row("1. patient-care", "患者照护（阿尔茨海默症辅助）")
        type_table.add_row("2. ai-development", "AI 开发（跨会话记忆）")
        type_table.add_row("3. knowledge-base", "个人知识管理")
        console.print(type_table)
        console.print()

        choice = Prompt.ask(
            "请选择",
            choices=["1", "2", "3"],
            default="2",
        )

        type_map = {
            "1": "patient-care",
            "2": "ai-development",
            "3": "knowledge-base",
        }
        project_type = type_map[choice]

    # 4. 创建配置
    console.print()
    console.print("[bold]创建项目配置...[/bold]")

    project_dir.mkdir(parents=True, exist_ok=True)
    create_default_constitution_yaml(constitution_path, project_type)

    # 5. 显示结果
    console.print()
    console.print(Panel(
        f"""[green]✓ 项目初始化成功！[/green]

[bold]项目名称:[/bold] {project_name}
[bold]项目类型:[/bold] {project_type}
[bold]配置目录:[/bold] {project_dir}
[bold]宪法层配置:[/bold] {constitution_path}

[bold yellow]下一步:[/bold yellow]
1. 编辑 {constitution_path} 添加你的核心身份信息
2. 运行 [cyan]memory-anchor serve --project {project_name}[/cyan] 启动服务
3. 在 Claude Code 中配置 MCP Server""",
        title="[bold green]初始化完成[/bold green]",
        border_style="green",
    ))

    # 6. 询问是否立即编辑宪法层
    if Confirm.ask("是否现在编辑宪法层配置？", default=False):
        import subprocess
        editor = Prompt.ask("选择编辑器", default="code")
        subprocess.run([editor, str(constitution_path)])


if __name__ == "__main__":
    typer.run(init_command)
