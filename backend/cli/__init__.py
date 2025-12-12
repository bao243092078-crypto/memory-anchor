"""
Memory Anchor CLI - 命令行工具

提供三个主要命令：
- memory-anchor init: 初始化新项目
- memory-anchor serve: 启动 MCP Server
- memory-anchor status: 查看记忆状态
"""

import typer

from backend.cli.init_cmd import init_command
from backend.cli.serve_cmd import serve_command
from backend.cli.status_cmd import status_command

app = typer.Typer(
    name="memory-anchor",
    help="Memory Anchor - AI 记忆系统 CLI\n\n为 AI 提供持久化记忆，如同阿尔茨海默症患者的便利贴。",
    add_completion=False,
    rich_markup_mode="rich",
)

# 注册子命令
app.command(name="init", help="初始化新的记忆项目")(init_command)
app.command(name="serve", help="启动 Memory Anchor 服务")(serve_command)
app.command(name="status", help="查看记忆系统状态")(status_command)


def main():
    """CLI 入口点"""
    app()


if __name__ == "__main__":
    main()


__all__ = ["app", "main"]
