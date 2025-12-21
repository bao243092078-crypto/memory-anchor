#!/bin/bash
# MCP wrapper script - ensures env vars are set before launching
export QDRANT_URL="http://127.0.0.1:6333"
export MCP_MEMORY_PROJECT_ID="${MCP_MEMORY_PROJECT_ID:-阿默斯海默症}"

cd /Users/baobao/projects/阿默斯海默症
exec uv run python -m backend.mcp_memory "$@"
