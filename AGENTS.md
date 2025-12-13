# AGENTS.md — 阿默斯海默症（Memory Anchor）

本文件面向 coding agents。

## 项目概览
- Memory Anchor：基于 MCP 的三层 AI 记忆系统（FastAPI + Qdrant）。
- 主要代码在 `backend/`，前端在 `frontend/`（如有）。

## 环境与依赖
- Python `>=3.12`
- 推荐：`uv sync` 或 `pip install -e .[dev]`

## 常用命令
- CLI：`memory-anchor --help`
- 启动 MCP stdio server：`memory-anchor serve`
- 启动 HTTP 模式：`memory-anchor serve --mode http --port 8000`

## 测试
- `pytest`（默认在 `backend/tests`）

## 代码规范/边界
- 三层记忆模型（宪法/事实/会话）是核心协议，改动必须同步 docs。
- 不要在仓库内写入用户真实隐私/密钥。
