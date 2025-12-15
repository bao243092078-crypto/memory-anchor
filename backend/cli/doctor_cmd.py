"""
memory-anchor doctor - 一键自诊断

目标：把“红叉/端口冲突/依赖缺失/配置缺失”这类问题，收敛为可执行的修复动作。
"""

from __future__ import annotations

import json
import os
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    fix: Optional[str] = None


def doctor_command(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="项目名称（默认使用环境变量 MCP_MEMORY_PROJECT_ID）",
    ),
    check_http: bool = typer.Option(
        True,
        "--http/--no-http",
        help="检查 HTTP 端口占用（只用于 http 模式）",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="HTTP 模式监听地址（用于端口检测）",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        help="HTTP 模式端口（用于端口检测）",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="显示详细异常堆栈",
    ),
):
    """
    运行自诊断，输出“可直接执行”的修复建议。

    适用场景：
    - Claude/Codex MCP 出现红叉
    - Qdrant/本地数据目录不可写
    - HTTP 端口冲突
    - 项目配置缺失
    """
    if project:
        os.environ["MCP_MEMORY_PROJECT_ID"] = project

    from backend.config import get_config, reset_config

    reset_config()
    config = get_config()

    console.print(
        Panel.fit(
            "[bold blue]Memory Anchor[/bold blue] - doctor 自诊断",
            border_style="blue",
        )
    )

    results: list[CheckResult] = []

    # 1) Python 版本
    py_ok = sys.version_info >= (3, 12)
    results.append(
        CheckResult(
            name="Python >= 3.12",
            ok=py_ok,
            detail=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            fix="安装/切换到 Python 3.12（推荐用 uv 管理：uv python install 3.12）" if not py_ok else None,
        )
    )

    # 2) 配置目录/权限
    try:
        config.ensure_directories()
        results.append(
            CheckResult(
                name="配置目录可写",
                ok=True,
                detail=str(config.data_dir),
            )
        )
    except Exception as e:
        results.append(
            CheckResult(
                name="配置目录可写",
                ok=False,
                detail=str(e),
                fix=f"检查目录权限：{config.data_dir}",
            )
        )

    # 3) 宪法层是否存在
    constitution_path = config.constitution_yaml_path
    if constitution_path.exists():
        results.append(
            CheckResult(
                name="宪法层配置",
                ok=True,
                detail=f"{constitution_path}（{len(config.constitution)} 条）",
            )
        )
    else:
        results.append(
            CheckResult(
                name="宪法层配置",
                ok=False,
                detail=f"缺少 {constitution_path}",
                fix="运行：memory-anchor init --force（或指定 --project 创建对应项目）",
            )
        )

    # 4) Qdrant（本地/Server）可用性
    qdrant_url = os.getenv("QDRANT_URL") or (str(config.qdrant_url) if config.qdrant_url else None)
    try:
        from backend.services.search import SearchService

        service = SearchService()
        stats = service.get_stats()

        location = qdrant_url or str(config.qdrant_path)
        results.append(
            CheckResult(
                name="向量存储(Qdrant)",
                ok=True,
                detail=f"mode={stats['mode']} collection={stats['collection_name']} count={stats['total_count']} ({location})",
            )
        )
    except Exception as e:
        fix = "如需 Server 模式：启动 Qdrant 并设置 QDRANT_URL=http://localhost:6333；否则删除损坏的本地目录后重试（默认用本地模式）。"
        results.append(CheckResult(name="向量存储(Qdrant)", ok=False, detail=str(e), fix=fix))
        if verbose:
            console.print_exception()

    # 5) HTTP 端口占用（仅提示，不强依赖）
    if check_http:
        port_ok = _is_port_available(host, port)
        results.append(
            CheckResult(
                name="HTTP 端口可用",
                ok=port_ok,
                detail=f"{host}:{port}",
                fix=f"换端口：memory-anchor serve --mode http --port {port + 1}"
                if not port_ok
                else None,
            )
        )

    # 6) Claude MCP 配置（尽量提示）
    claude_cfg = Path.home() / ".claude.json"
    if claude_cfg.exists():
        results.append(_check_claude_config(claude_cfg))
    else:
        results.append(
            CheckResult(
                name="Claude MCP 配置(~/.claude.json)",
                ok=True,
                detail="未检测到（跳过）",
            )
        )

    _render_results(results)

    # 失败则非 0 退出，方便脚本化
    if any(not r.ok for r in results):
        raise typer.Exit(2)


def _is_port_available(host: str, port: int) -> bool:
    """检测端口是否可绑定（跨平台，避免依赖 psutil/lsof）。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
        return True
    except OSError:
        return False


def _check_claude_config(path: Path) -> CheckResult:
    """检查 MCP 配置（支持全局 ~/.claude.json 和项目级 .mcp.json）"""
    # 先检查项目级 .mcp.json（优先级更高）
    project_mcp = Path.cwd() / ".mcp.json"
    if project_mcp.exists():
        try:
            data = json.loads(project_mcp.read_text(encoding="utf-8"))
            servers = (data or {}).get("mcpServers") or {}
            if servers.get("memory-anchor"):
                return CheckResult(
                    name="MCP 配置",
                    ok=True,
                    detail=f"已配置 memory-anchor（项目级 .mcp.json）",
                )
        except Exception:
            pass  # 继续检查全局配置

    # 检查全局 ~/.claude.json
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return CheckResult(
            name="MCP 配置",
            ok=False,
            detail=f"无法解析 JSON: {e}",
            fix="修复 ~/.claude.json 的 JSON 格式后重试",
        )

    servers = (data or {}).get("mcpServers") or {}
    server_cfg = servers.get("memory-anchor")
    if not server_cfg:
        return CheckResult(
            name="MCP 配置",
            ok=False,
            detail="未配置 mcpServers.memory-anchor",
            fix='在项目目录创建 .mcp.json 或在 ~/.claude.json 中添加配置',
        )

    args = server_cfg.get("args") or []
    args_text = " ".join(str(a) for a in args)
    if "--mode" in args_text and "http" in args_text:
        return CheckResult(
            name="MCP 配置",
            ok=False,
            detail=f"检测到 --mode http（会导致 MCP 红叉）：{args_text}",
            fix="移除 --mode http（MCP 需要 stdio）；使用：memory-anchor serve（默认 mcp-stdio）",
        )

    return CheckResult(
        name="MCP 配置",
        ok=True,
        detail="已配置 memory-anchor（全局 ~/.claude.json）",
    )


def _render_results(results: list[CheckResult]) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("检查项", style="cyan")
    table.add_column("结果", width=6)
    table.add_column("详情", overflow="fold")
    table.add_column("修复建议", overflow="fold")

    for r in results:
        table.add_row(
            r.name,
            "[green]OK[/green]" if r.ok else "[red]FAIL[/red]",
            r.detail,
            r.fix or "-",
        )

    console.print()
    console.print(table)

