#!/bin/bash
# MCP wrapper script - ensures env vars are set before launching
export QDRANT_URL="http://127.0.0.1:6333"
export NO_PROXY="localhost,127.0.0.1"
export no_proxy="localhost,127.0.0.1"
export MCP_MEMORY_PROJECT_ID="${MCP_MEMORY_PROJECT_ID:-阿默斯海默症}"

# 使用脚本所在目录的相对路径
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
exec uv run python -m backend.mcp_memory "$@"
