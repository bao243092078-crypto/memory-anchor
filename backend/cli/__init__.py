"""
Memory Anchor CLI - 命令行工具

提供主要命令：
- memory-anchor init: 初始化新项目
- memory-anchor serve: 启动 MCP Server
- memory-anchor status: 查看记忆状态
- memory-anchor doctor: 一键自诊断
- memory-anchor sync-north-star: 同步北极星到宪法层
- memory-anchor drift-check: 检查偏离度
- memory-anchor review: 多视角代码审查
- memory-anchor cloud: 云端同步命令（init/push/pull/status）
- memory-anchor web: 启动 Memory Viewer Web 界面
- memory-anchor budget: 查看上下文预算使用情况（v3.0）
"""

import typer

from backend.cli.budget_cmd import budget_command
from backend.cli.cloud_cmd import cloud_app
from backend.cli.doctor_cmd import doctor_command
from backend.cli.drift_cmd import drift_check_command
from backend.cli.init_cmd import init_command
from backend.cli.north_star_cmd import sync_north_star_command
from backend.cli.review_cmd import review_command
from backend.cli.serve_cmd import serve_command
from backend.cli.status_cmd import status_command
from backend.cli.web_cmd import web_command

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
app.command(name="doctor", help="一键自诊断（红叉/端口/依赖/配置）")(doctor_command)
app.command(name="sync-north-star", help="同步北极星到宪法层（L0）")(sync_north_star_command)
app.command(name="drift-check", help="检查当前工作与北极星的偏离度")(drift_check_command)
app.command(name="review", help="多视角代码审查（Security/Performance/Quality/Memory）")(review_command)
app.command(name="web", help="启动 Memory Viewer Web 界面")(web_command)
app.command(name="budget", help="查看上下文预算使用情况（v3.0）")(budget_command)
app.add_typer(cloud_app, name="cloud", help="云端同步命令（push/pull/status）")


def main():
    """CLI 入口点"""
    app()


if __name__ == "__main__":
    main()


__all__ = ["app", "main"]
