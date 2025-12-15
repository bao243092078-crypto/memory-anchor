#!/usr/bin/env bash
# ma - Memory Anchor 傻瓜入口脚本
# 版本: 2.0.0 (五层认知记忆模型)
set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

if ! command -v uv >/dev/null 2>&1; then
  echo -e "${RED}uv 未安装。请先安装：curl -LsSf https://astral.sh/uv/install.sh | sh${NC}" >&2
  exit 127
fi

cmd="${1:-}"
shift || true

show_help() {
  cat <<'EOF'
╔═══════════════════════════════════════════════════════════════╗
║           Memory Anchor - AI 的外挂海马体                      ║
╚═══════════════════════════════════════════════════════════════╝

傻瓜 SOP（5 句话）：
  1. Memory Anchor 是 AI 的外挂记忆——像便利贴帮你记住重要的事
  2. 唯一命令入口是 `ma`——不用管端口、进程、配置
  3. 每天开始前运行 `ma doctor`——确认系统健康
  4. 看到红叉就运行 `ma fix`——自动修复
  5. MCP 模式默认零端口——不会和其他服务打架

3 个核心命令：
  ./ma doctor [--project NAME]   # 自诊断（每天第一次用之前）
  ./ma fix    [--project NAME]   # 自动修复（出问题时）
  ./ma init   [--project NAME]   # 初始化项目（首次使用）

其他命令：
  ./ma up     [--project NAME]   # 启动 MCP 服务
  ./ma status [--project NAME]   # 查看记忆状态

决策树（贴显示器）：
              开始
                │
          运行 ma doctor
                │
        ┌───────┴───────┐
        ↓               ↓
     全绿 ✅          有红 ❌
        │               │
     直接用         运行 ma fix
                        │
                ┌───────┴───────┐
                ↓               ↓
           修复成功         修复失败
                │               │
             直接用         找开发者
EOF
}

# fix 命令 - 自动修复
cmd_fix() {
  echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║           Memory Anchor - 自动修复                            ║${NC}"
  echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
  echo ""

  local project_arg=""
  for arg in "$@"; do
    if [[ "$arg" == "--project" || "$arg" == "-p" ]]; then
      project_arg="next"
    elif [[ "$project_arg" == "next" ]]; then
      project_arg="$arg"
    fi
  done

  local fixed=0
  local failed=0
  local config_dir="${HOME}/.memory-anchor"

  # 1. 确保配置目录存在
  echo -e "${BLUE}[1/5]${NC} 检查配置目录..."
  if [[ ! -d "$config_dir" ]]; then
    mkdir -p "$config_dir/projects"
    echo -e "  ${GREEN}✓${NC} 创建 $config_dir"
    ((fixed++))
  else
    echo -e "  ${GREEN}✓${NC} 目录已存在"
  fi

  # 2. 检查 Qdrant（本地或 Server）
  echo -e "${BLUE}[2/5]${NC} 检查 Qdrant..."
  if [[ -n "${QDRANT_URL:-}" ]]; then
    if curl -sf "${QDRANT_URL}/healthz" > /dev/null 2>&1; then
      echo -e "  ${GREEN}✓${NC} Qdrant Server 运行中 (${QDRANT_URL})"
    else
      echo -e "  ${YELLOW}⚠${NC} Qdrant Server 不可达 (${QDRANT_URL})"
      echo -e "  ${YELLOW}→ 启动: docker start qdrant${NC}"
      ((failed++))
    fi
  else
    echo -e "  ${GREEN}✓${NC} 使用本地模式（无需服务）"
  fi

  # 3. 检查项目初始化
  echo -e "${BLUE}[3/5]${NC} 检查项目配置..."
  if [[ -n "$project_arg" && "$project_arg" != "next" ]]; then
    local constitution_file="${config_dir}/projects/${project_arg}/constitution.yaml"
    if [[ ! -f "$constitution_file" ]]; then
      echo -e "  ${YELLOW}→${NC} 项目 '${project_arg}' 未初始化，正在创建..."
      uv run memory-anchor init "$project_arg" --type ai-development --force 2>/dev/null || true
      if [[ -f "$constitution_file" ]]; then
        echo -e "  ${GREEN}✓${NC} 项目已初始化"
        ((fixed++))
      else
        echo -e "  ${RED}✗${NC} 初始化失败，请手动运行: ma init --project $project_arg"
        ((failed++))
      fi
    else
      echo -e "  ${GREEN}✓${NC} 项目已初始化"
    fi
  else
    echo -e "  ${YELLOW}⚠${NC} 未指定项目（用 --project NAME）"
  fi

  # 4. 检查 Claude MCP 配置
  echo -e "${BLUE}[4/5]${NC} 检查 Claude MCP 配置..."
  local claude_config="${HOME}/.claude.json"
  if [[ -f "$claude_config" ]]; then
    if grep -q '"memory-anchor"' "$claude_config" 2>/dev/null; then
      echo -e "  ${GREEN}✓${NC} MCP 已配置"
    else
      echo -e "  ${YELLOW}⚠${NC} MCP 未配置 memory-anchor"
      echo -e "  ${YELLOW}→ 请在 ~/.claude.json 的 mcpServers 中添加:${NC}"
      echo '    "memory-anchor": {"command": "memory-anchor", "args": ["serve", "--project", "YOUR_PROJECT"]}'
      ((failed++))
    fi
  else
    echo -e "  ${YELLOW}⚠${NC} ~/.claude.json 不存在"
  fi

  # 5. 检查端口（仅提示）
  echo -e "${BLUE}[5/5]${NC} 检查端口占用..."
  if command -v lsof >/dev/null 2>&1 && lsof -i :8000 > /dev/null 2>&1; then
    echo -e "  ${YELLOW}⚠${NC} 端口 8000 被占用（HTTP 模式可能冲突）"
  else
    echo -e "  ${GREEN}✓${NC} 端口 8000 可用"
  fi

  # 汇总
  echo ""
  echo "═══════════════════════════════════════════════════════════════"
  if [[ $failed -eq 0 ]]; then
    echo -e "${GREEN}✅ 修复完成！建议运行 ma doctor 确认状态。${NC}"
  else
    echo -e "${YELLOW}⚠️ 有 ${failed} 个问题需要手动处理，请按上述提示操作。${NC}"
  fi
  echo "═══════════════════════════════════════════════════════════════"
}

case "${cmd}" in
  ""|-h|--help|help)
    show_help
    ;;
  init)
    uv run memory-anchor init "$@"
    ;;
  up|start|serve)
    uv run memory-anchor serve "$@"
    ;;
  doctor)
    uv run memory-anchor doctor "$@"
    ;;
  fix)
    cmd_fix "$@"
    ;;
  status)
    uv run memory-anchor status "$@"
    ;;
  *)
    uv run memory-anchor "${cmd}" "$@"
    ;;
esac

