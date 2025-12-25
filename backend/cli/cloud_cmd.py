"""
Cloud Sync CLI Commands - 云端同步命令

提供：
- cloud init: 初始化云端配置
- cloud push: 推送到云端
- cloud pull: 从云端拉取
- cloud status: 查看同步状态
"""

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from backend.config import DEFAULT_GLOBAL_CONFIG_DIR, load_config

console = Console()

# 创建子命令组
cloud_app = typer.Typer(
    name="cloud",
    help="云端同步命令",
    add_completion=False,
)


@cloud_app.command(name="init")
def cloud_init_command(
    provider: str = typer.Option(
        "s3",
        "--provider",
        "-p",
        help="存储提供商 (s3/r2/minio)",
    ),
    bucket: str = typer.Option(
        ...,
        "--bucket",
        "-b",
        help="存储桶名称",
    ),
    region: str = typer.Option(
        "us-east-1",
        "--region",
        "-r",
        help="AWS 区域（S3 用）",
    ),
    endpoint: Optional[str] = typer.Option(
        None,
        "--endpoint",
        "-e",
        help="自定义端点 URL（R2/MinIO 用）",
    ),
    encrypt: bool = typer.Option(
        True,
        "--encrypt/--no-encrypt",
        help="是否启用加密",
    ),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        help="项目名称（默认使用当前目录名）",
    ),
):
    """初始化云端同步配置"""
    from backend.services.data_encryptor import DataEncryptor

    project_id = project or Path.cwd().name

    console.print(Panel(f"[bold blue]初始化云端同步[/bold blue]\n项目: {project_id}"))

    # 检查 provider 和 endpoint
    if provider == "r2" and not endpoint:
        console.print("[red]❌ R2 需要指定 --endpoint (格式: https://<account_id>.r2.cloudflarestorage.com)[/red]")
        raise typer.Exit(1)

    # 显示配置
    table = Table(title="云端配置")
    table.add_column("配置项", style="cyan")
    table.add_column("值", style="green")

    table.add_row("Provider", provider)
    table.add_row("Bucket", bucket)
    table.add_row("Region", region)
    table.add_row("Endpoint", endpoint or "(默认)")
    table.add_row("加密", "✅ 启用" if encrypt else "❌ 禁用")

    console.print(table)

    # 生成加密密钥
    if encrypt:
        key_path = DEFAULT_GLOBAL_CONFIG_DIR / "encryption.key"
        if key_path.exists():
            console.print(f"\n[yellow]⚠️ 加密密钥已存在: {key_path}[/yellow]")
            if not typer.confirm("是否覆盖？"):
                console.print("[dim]保留现有密钥[/dim]")
            else:
                DataEncryptor.initialize_key(key_path, force=True)
                console.print(f"[green]✅ 新密钥已生成: {key_path}[/green]")
                console.print("[bold red]⚠️ 请立即备份此密钥！密钥丢失 = 数据丢失[/bold red]")
        else:
            DataEncryptor.initialize_key(key_path)
            console.print(f"[green]✅ 加密密钥已生成: {key_path}[/green]")
            console.print("[bold red]⚠️ 请立即备份此密钥！密钥丢失 = 数据丢失[/bold red]")

    # 提示设置环境变量
    console.print("\n[bold]下一步：设置环境变量[/bold]")
    console.print(f"""
[dim]# 添加到 ~/.zshrc 或 ~/.bashrc[/dim]
export MA_CLOUD_ENABLED=true
export MA_CLOUD_PROVIDER={provider}
export MA_CLOUD_BUCKET={bucket}
export MA_CLOUD_REGION={region}
{f'export MA_CLOUD_ENDPOINT_URL={endpoint}' if endpoint else ''}

[dim]# AWS 凭证（如果未配置 AWS CLI）[/dim]
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
""")

    console.print("[green]✅ 云端同步初始化完成[/green]")


@cloud_app.command(name="push")
def cloud_push_command(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        help="项目名称（默认使用当前目录名）",
    ),
    encrypt: bool = typer.Option(
        True,
        "--encrypt/--no-encrypt",
        help="是否加密数据",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="强制推送（覆盖远端）",
    ),
):
    """推送记忆到云端"""
    from backend.services.cloud_sync import CloudSyncService

    project_id = project or os.getenv("MCP_MEMORY_PROJECT_ID") or Path.cwd().name
    config = load_config()

    if not config.cloud.enabled:
        console.print("[red]❌ 云端同步未启用，请先运行 `ma cloud init`[/red]")
        raise typer.Exit(1)

    if not config.cloud.bucket:
        console.print("[red]❌ 未配置存储桶，请设置 MA_CLOUD_BUCKET[/red]")
        raise typer.Exit(1)

    console.print(Panel(f"[bold blue]推送到云端[/bold blue]\n项目: {project_id}"))

    try:
        sync_service = CloudSyncService(project_id, config.cloud)

        # 检查远端状态
        if not force:
            remote_manifest = sync_service.status()
            if remote_manifest:
                console.print(f"\n[yellow]远端已有数据（{remote_manifest.memories_count} 条记忆）[/yellow]")
                console.print(f"最后同步: {remote_manifest.last_sync}")
                if not typer.confirm("是否覆盖？"):
                    console.print("[dim]推送已取消[/dim]")
                    raise typer.Exit(0)

        with console.status("[bold green]正在推送..."):
            manifest = sync_service.push(encrypt=encrypt)

        # 显示结果
        table = Table(title="推送结果")
        table.add_column("项目", style="cyan")
        table.add_column("值", style="green")

        table.add_row("记忆数量", str(manifest.memories_count))
        table.add_row("加密", "✅" if manifest.encrypted else "❌")
        table.add_row("同步时间", manifest.last_sync)
        table.add_row("校验和", manifest.memories_checksum[:16] + "...")

        console.print(table)
        console.print("\n[green]✅ 推送完成[/green]")

    except Exception as e:
        console.print(f"[red]❌ 推送失败: {e}[/red]")
        raise typer.Exit(1)


@cloud_app.command(name="pull")
def cloud_pull_command(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        help="项目名称（默认使用当前目录名）",
    ),
    strategy: str = typer.Option(
        "lww",
        "--strategy",
        "-s",
        help="冲突策略 (lww: 最后写入者胜, skip: 跳过冲突, merge: 手动合并)",
    ),
):
    """从云端拉取记忆"""
    from backend.services.cloud_sync import CloudSyncService

    project_id = project or os.getenv("MCP_MEMORY_PROJECT_ID") or Path.cwd().name
    config = load_config()

    if not config.cloud.enabled:
        console.print("[red]❌ 云端同步未启用，请先运行 `ma cloud init`[/red]")
        raise typer.Exit(1)

    console.print(Panel(f"[bold blue]从云端拉取[/bold blue]\n项目: {project_id}\n策略: {strategy}"))

    try:
        sync_service = CloudSyncService(project_id, config.cloud)

        # 检查远端状态
        remote_manifest = sync_service.status()
        if not remote_manifest:
            console.print("[yellow]远端没有数据[/yellow]")
            raise typer.Exit(0)

        console.print(f"远端记忆: {remote_manifest.memories_count} 条")
        console.print(f"最后同步: {remote_manifest.last_sync}")

        if not typer.confirm("确认拉取？"):
            console.print("[dim]拉取已取消[/dim]")
            raise typer.Exit(0)

        with console.status("[bold green]正在拉取..."):
            imported, skipped, conflicts = sync_service.pull(strategy=strategy)

        # 显示结果
        table = Table(title="拉取结果")
        table.add_column("统计", style="cyan")
        table.add_column("数量", style="green")

        table.add_row("导入", str(imported))
        table.add_row("跳过", str(skipped))
        table.add_row("冲突", str(conflicts))

        console.print(table)
        console.print("\n[green]✅ 拉取完成[/green]")

    except Exception as e:
        console.print(f"[red]❌ 拉取失败: {e}[/red]")
        raise typer.Exit(1)


@cloud_app.command(name="status")
def cloud_status_command(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        help="项目名称（默认使用当前目录名）",
    ),
):
    """查看云端同步状态"""
    from backend.services.cloud_sync import CloudSyncService

    project_id = project or os.getenv("MCP_MEMORY_PROJECT_ID") or Path.cwd().name
    config = load_config()

    console.print(Panel(f"[bold blue]云端同步状态[/bold blue]\n项目: {project_id}"))

    # 本地配置
    table = Table(title="本地配置")
    table.add_column("配置", style="cyan")
    table.add_column("值", style="green")

    table.add_row("启用", "✅" if config.cloud.enabled else "❌")
    table.add_row("Provider", config.cloud.provider)
    table.add_row("Bucket", config.cloud.bucket or "(未配置)")
    table.add_row("Region", config.cloud.region)
    table.add_row("加密", "✅" if config.cloud.encryption_enabled else "❌")

    console.print(table)

    if not config.cloud.enabled or not config.cloud.bucket:
        console.print("\n[dim]云端同步未配置，运行 `ma cloud init` 开始[/dim]")
        return

    # 远端状态
    try:
        sync_service = CloudSyncService(project_id, config.cloud)
        manifest = sync_service.status()

        if manifest:
            remote_table = Table(title="远端状态")
            remote_table.add_column("项目", style="cyan")
            remote_table.add_column("值", style="green")

            remote_table.add_row("记忆数量", str(manifest.memories_count))
            remote_table.add_row("最后同步", manifest.last_sync)
            remote_table.add_row("加密", "✅" if manifest.encrypted else "❌")
            remote_table.add_row("校验和", manifest.memories_checksum[:16] + "...")

            console.print(remote_table)
        else:
            console.print("\n[yellow]远端没有数据[/yellow]")

    except Exception as e:
        console.print(f"\n[red]❌ 无法获取远端状态: {e}[/red]")


# 导出命令函数供主 CLI 使用
def cloud_command():
    """云端同步命令入口"""
    cloud_app()


__all__ = ["cloud_app", "cloud_command"]
