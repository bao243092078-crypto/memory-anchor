#!/bin/bash
# MCP wrapper script - ensures env vars are set before launching

# 使用脚本所在目录的相对路径
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# 使用 env 命令显式传递环境变量（解决 uv run 环境变量继承问题）
exec env \
    QDRANT_URL="http://127.0.0.1:6333" \
    NO_PROXY="localhost,127.0.0.1" \
    no_proxy="localhost,127.0.0.1" \
    MCP_MEMORY_PROJECT_ID="${MCP_MEMORY_PROJECT_ID:-global}" \
    uv run python -m backend.mcp_memory "$@"
