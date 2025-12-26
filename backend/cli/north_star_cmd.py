"""
memory-anchor sync-north-star - 同步北极星到宪法层

将项目的 .ai/NORTH_STAR.md 同步到 Memory Anchor 的宪法层（L0），
使其能通过 get_constitution() 自动加载。

特点：
- 北极星是项目配置，不是患者身份，无需三次审批
- 使用 category="north_star" 区分
- 支持幂等更新（重复同步不会重复创建）
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid5

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()

# 北极星的命名空间 UUID（用于生成确定性 ID）
NORTH_STAR_NAMESPACE = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def find_north_star(start_path: Path | None = None) -> tuple[Path | None, str | None]:
    """
    从指定路径向上查找 .ai/NORTH_STAR.md

    Returns:
        (文件路径, 文件内容) 或 (None, None)
    """
    cwd = start_path or Path.cwd()

    for path in [cwd, *cwd.parents]:
        # 优先查找 .ai/ 子目录
        north_star = path / ".ai" / "NORTH_STAR.md"
        if north_star.exists():
            return north_star, north_star.read_text(encoding="utf-8")

        # 也检查根目录
        north_star_root = path / "NORTH_STAR.md"
        if north_star_root.exists():
            return north_star_root, north_star_root.read_text(encoding="utf-8")

        if path == Path.home():
            break

    return None, None


def generate_north_star_id(project_id: str) -> UUID:
    """
    生成北极星的确定性 ID（基于项目 ID）

    这样同一项目的北极星总是使用相同的 ID，实现幂等更新。
    """
    return uuid5(NORTH_STAR_NAMESPACE, f"north-star:{project_id}")


def sync_north_star_command(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="项目名称（默认使用环境变量 MCP_MEMORY_PROJECT_ID 或当前目录名）",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        help="指定 NORTH_STAR.md 的路径（默认自动查找）",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="仅显示将要执行的操作，不实际执行",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="强制同步（即使内容没有变化）",
    ),
):
    """
    将北极星文件同步到 Memory Anchor 宪法层。

    北极星是项目的"初心"，同步后会通过 get_constitution() 自动加载。

    示例：
        ./ma sync-north-star                    # 自动查找并同步
        ./ma sync-north-star --project myproj   # 指定项目
        ./ma sync-north-star --dry-run          # 预览不执行
    """
    # 1. 确定项目 ID
    project_id = project or os.getenv("MCP_MEMORY_PROJECT_ID")
    if not project_id:
        project_id = Path.cwd().name
        console.print(f"[dim]使用当前目录名作为项目 ID: {project_id}[/dim]")

    os.environ["MCP_MEMORY_PROJECT_ID"] = project_id

    # 2. 查找北极星文件
    if path:
        if not path.exists():
            console.print(f"[red]错误：指定的文件不存在: {path}[/red]")
            raise typer.Exit(1)
        north_star_path = path
        north_star_content = path.read_text(encoding="utf-8")
    else:
        found_path, found_content = find_north_star()
        if found_path is None or found_content is None:
            console.print("[yellow]未找到 NORTH_STAR.md 文件[/yellow]")
            console.print("[dim]提示：在项目根目录创建 .ai/NORTH_STAR.md[/dim]")
            raise typer.Exit(1)
        north_star_path = found_path
        north_star_content = found_content

    if not north_star_content:
        console.print("[yellow]未找到 NORTH_STAR.md 文件[/yellow]")
        console.print("[dim]提示：在项目根目录创建 .ai/NORTH_STAR.md[/dim]")
        raise typer.Exit(1)

    console.print(Panel.fit(
        f"[bold blue]北极星同步[/bold blue]\n"
        f"项目: {project_id}\n"
        f"文件: {north_star_path}",
        border_style="blue",
    ))

    # 3. 计算内容哈希（用于检测变化）
    content_hash = hashlib.md5(north_star_content.encode()).hexdigest()[:8]
    note_id = generate_north_star_id(project_id)

    console.print(f"[dim]北极星 ID: {note_id}[/dim]")
    console.print(f"[dim]内容哈希: {content_hash}[/dim]")

    if dry_run:
        console.print("\n[yellow]--dry-run 模式，不执行实际操作[/yellow]")
        console.print("\n[bold]将要同步的内容：[/bold]")
        # 只显示前 500 字符
        preview = north_star_content[:500]
        if len(north_star_content) > 500:
            preview += "\n..."
        console.print(Panel(preview, title="NORTH_STAR.md", border_style="dim"))
        return

    # 4. 执行同步
    from backend.config import reset_config
    from backend.models.note import MemoryLayer
    from backend.services.search import get_search_service

    reset_config()
    search_service = get_search_service()

    # 检查是否已存在
    try:
        existing = search_service.get_note(note_id)
        if existing and not force:
            # 比较内容是否变化
            existing_hash = hashlib.md5(existing.get("content", "").encode()).hexdigest()[:8]
            if existing_hash == content_hash:
                console.print("[green]北极星已是最新，无需同步[/green]")
                return
            console.print(f"[dim]检测到内容变化（{existing_hash} → {content_hash}），更新中...[/dim]")
    except Exception:
        console.print("[dim]首次同步北极星...[/dim]")

    # 删除旧的（如果存在）然后创建新的
    try:
        search_service.delete_note(note_id)
    except Exception:
        pass  # 可能不存在，忽略

    # 创建新的宪法层条目
    # 在内容前添加标记
    marked_content = f"[北极星 | {project_id}]\n\n{north_star_content}"

    search_service.index_note(
        note_id=note_id,
        content=marked_content,
        layer=MemoryLayer.CONSTITUTION.value,
        category="north_star",
        is_active=True,
    )

    console.print("\n[green]✅ 北极星已同步到宪法层[/green]")
    console.print("[dim]下次调用 get_constitution() 时将自动加载[/dim]")


__all__ = ["sync_north_star_command"]
