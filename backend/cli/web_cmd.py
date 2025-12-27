"""
memory-anchor web - 启动 Memory Viewer Web 界面

启动一个临时 Web 服务用于浏览记忆。
"""

import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()

# 默认端口
DEFAULT_PORT = 37778


def web_command(
    project: Optional[str] = typer.Option(
        None,
        "--project", "-p",
        help="项目名称（默认使用环境变量 MCP_MEMORY_PROJECT_ID）",
    ),
    port: int = typer.Option(
        DEFAULT_PORT,
        "--port",
        help=f"监听端口（默认 {DEFAULT_PORT}）",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host", "-h",
        help="监听地址",
    ),
    no_browser: bool = typer.Option(
        False,
        "--no-browser",
        help="不自动打开浏览器",
    ),
    dev: bool = typer.Option(
        False,
        "--dev",
        help="开发模式（启动 Vite 开发服务器）",
    ),
):
    """
    启动 Memory Viewer Web 界面

    用于浏览和搜索 Memory Anchor 中的记忆。
    支持语义搜索、按层级/分类筛选、查看可追溯性字段。
    """
    # 设置项目 ID
    if project:
        os.environ["MCP_MEMORY_PROJECT_ID"] = project

    project_id = os.getenv("MCP_MEMORY_PROJECT_ID", "default")

    # 获取路径
    project_root = Path(__file__).parent.parent.parent
    viewer_dir = project_root / "frontend" / "viewer"

    # 检查 viewer 目录
    if not viewer_dir.exists():
        console.print("[red]错误: frontend/viewer 目录不存在[/red]")
        raise typer.Exit(1)

    console.print(
        Panel.fit(
            f"[bold blue]Memory Anchor Viewer[/bold blue]\n\n"
            f"[bold]项目:[/bold] {project_id}\n"
            f"[bold]端口:[/bold] {port}\n"
            f"[bold]模式:[/bold] {'开发' if dev else '生产'}",
            border_style="blue",
        )
    )

    if dev:
        _serve_dev(viewer_dir, port, host, no_browser, project_root)
    else:
        _serve_production(viewer_dir, port, host, no_browser, project_root)


def _serve_dev(viewer_dir: Path, port: int, host: str, no_browser: bool, project_root: Path):
    """开发模式：启动 Vite + FastAPI"""
    console.print()
    console.print("[yellow]开发模式: 启动 Vite 开发服务器[/yellow]")
    console.print()

    # 检查是否安装了依赖
    node_modules = viewer_dir / "node_modules"
    if not node_modules.exists():
        console.print("[dim]首次运行，安装依赖...[/dim]")
        subprocess.run(["npm", "install"], cwd=viewer_dir, check=True)

    # 启动 FastAPI 后端（在后台）
    console.print("[dim]启动后端 API...[/dim]")
    api_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", host, "--port", "8000"],
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # 启动 Vite 开发服务器
    console.print(f"[green]✓ 启动 Viewer: http://{host}:{port}[/green]")
    console.print("[dim]按 Ctrl+C 停止服务[/dim]")
    console.print()

    # 打开浏览器
    if not no_browser:
        webbrowser.open(f"http://{host}:{port}")

    try:
        subprocess.run(
            ["npm", "run", "dev", "--", "--port", str(port), "--host", host],
            cwd=viewer_dir,
            check=True,
        )
    finally:
        api_process.terminate()


def _serve_production(viewer_dir: Path, port: int, host: str, no_browser: bool, project_root: Path):
    """生产模式：构建前端 + 启动 FastAPI 提供静态文件"""
    dist_dir = viewer_dir / "dist"

    # 检查是否需要构建
    if not dist_dir.exists():
        console.print("[dim]首次运行，构建前端...[/dim]")
        _build_frontend(viewer_dir)

    console.print()
    console.print(f"[green]✓ 启动 Memory Viewer: http://{host}:{port}[/green]")
    console.print()
    console.print(f"[dim]API: http://{host}:{port}/api/v1[/dim]")
    console.print("[dim]按 Ctrl+C 停止服务[/dim]")
    console.print()

    # 打开浏览器
    if not no_browser:
        webbrowser.open(f"http://{host}:{port}")

    # 启动 FastAPI 服务（带静态文件）
    _run_server_with_static(dist_dir, port, host)


def _build_frontend(viewer_dir: Path):
    """构建前端"""
    console.print("[dim]检查依赖...[/dim]")

    node_modules = viewer_dir / "node_modules"
    if not node_modules.exists():
        console.print("[dim]安装依赖...[/dim]")
        subprocess.run(["npm", "install"], cwd=viewer_dir, check=True)

    console.print("[dim]构建前端...[/dim]")
    subprocess.run(["npm", "run", "build"], cwd=viewer_dir, check=True)
    console.print("[green]✓ 前端构建完成[/green]")


def _run_server_with_static(dist_dir: Path, port: int, host: str):
    """启动带静态文件服务的 FastAPI"""
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from fastapi.middleware.cors import CORSMiddleware

    from backend.api.constitution import router as constitution_router
    from backend.api.memory import router as memory_router
    from backend.api.notes import router as notes_router
    from backend.api.pending import router as pending_router
    from backend.api.search import router as search_router

    # 创建新的 FastAPI 应用
    app = FastAPI(title="Memory Anchor Viewer")

    # CORS 配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册 API 路由（与 backend/main.py 相同）
    app.include_router(notes_router, prefix="/api/v1")
    app.include_router(search_router)  # search 路由已有 /api/v1 前缀
    app.include_router(memory_router)  # memory 路由已有 /api/v1/memory 前缀
    app.include_router(constitution_router, prefix="/api/v1")
    app.include_router(pending_router)  # pending 路由已有 /api/v1/pending 前缀

    # 挂载静态文件
    app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")

    # 所有其他路由返回 index.html (SPA)
    @app.get("/")
    async def serve_index():
        return FileResponse(str(dist_dir / "index.html"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # 如果是 API 路径，返回 404
        if full_path.startswith("api/"):
            return {"error": "Not Found"}
        index_path = dist_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"error": "index.html not found"}

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    typer.run(web_command)
