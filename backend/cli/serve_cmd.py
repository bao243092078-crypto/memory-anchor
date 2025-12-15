"""
memory-anchor serve - 启动 MCP Server

支持两种模式：
1. HTTP Server (FastAPI)
2. MCP stdio (用于 Claude Code 集成)
"""

import os
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

console_stdout = Console()
console_stderr = Console(stderr=True)


def serve_command(
    project: Optional[str] = typer.Option(
        None,
        "--project", "-p",
        help="项目名称（默认使用环境变量 MCP_MEMORY_PROJECT_ID）",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host", "-h",
        help="监听地址",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        help="监听端口",
    ),
    mode: str = typer.Option(
        "mcp-stdio",
        "--mode", "-m",
        help="运行模式: mcp-stdio / http",
    ),
    reload: bool = typer.Option(
        False,
        "--reload", "-r",
        help="开发模式（自动重载）",
    ),
):
    """
    启动 Memory Anchor 服务

    HTTP 模式用于 API 访问，MCP stdio 模式用于 Claude Code 集成。
    """
    normalized_mode = _normalize_mode(mode)

    # 设置项目 ID
    if project:
        os.environ["MCP_MEMORY_PROJECT_ID"] = project

    project_id = os.getenv("MCP_MEMORY_PROJECT_ID", "default")

    # 注意：mcp-stdio 模式下 stdout 属于 MCP 协议通道（JSON-RPC），严禁输出任何人类可读文本
    console = console_stderr if normalized_mode == "mcp-stdio" else console_stdout

    if normalized_mode == "http":
        console.print(
            Panel.fit(
                f"[bold blue]Memory Anchor[/bold blue] - 启动服务\n\n"
                f"[bold]项目:[/bold] {project_id}\n"
                f"[bold]模式:[/bold] {normalized_mode}",
                border_style="blue",
            )
        )

    if normalized_mode == "http":
        _serve_http(console, host, port, reload)
    elif normalized_mode == "mcp-stdio":
        _serve_mcp_stdio(console)
    else:
        console_stderr.print(f"[red]未知模式: {mode}[/red]")
        raise typer.Exit(1)


def _serve_http(console: Console, host: str, port: int, reload: bool):
    """启动 HTTP Server"""
    import uvicorn

    console.print()
    console.print(f"[green]✓ 启动 HTTP Server: http://{host}:{port}[/green]")
    console.print()
    console.print(f"[dim]API 文档: http://{host}:{port}/docs[/dim]")
    console.print("[dim]按 Ctrl+C 停止服务[/dim]")
    console.print()

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=reload,
    )


def _serve_mcp_stdio(console: Console):
    """启动 MCP stdio Server"""
    # 注意：stdout 是 MCP 协议通道；日志仅允许写到 stderr
    console.print("[dim]Memory Anchor MCP stdio server starting...[/dim]")

    # 导入并运行 MCP Server
    import asyncio

    from backend.mcp_memory import main as mcp_main

    asyncio.run(mcp_main())


def _normalize_mode(mode: str) -> str:
    value = mode.strip().lower().replace("_", "-")
    if value in {"mcp", "stdio", "mcp-stdio", "mcpstdio"}:
        return "mcp-stdio"
    if value in {"http", "api"}:
        return "http"
    return value


if __name__ == "__main__":
    typer.run(serve_command)
