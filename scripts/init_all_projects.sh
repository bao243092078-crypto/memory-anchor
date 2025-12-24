#!/bin/bash
# Memory Anchor 批量项目初始化脚本
# 用途：为所有项目添加 Memory Anchor 配置，确保记忆隔离

set -e

PROJECTS_DIR="/Users/baobao/projects"
TEMPLATE_PATH="$PROJECTS_DIR/阿默斯海默症/.memory-anchor/config.yaml"

echo "🚀 Memory Anchor 批量项目初始化"
echo "================================"
echo ""
echo "项目目录: $PROJECTS_DIR"
echo ""

# 统计
TOTAL=0
CREATED=0
SKIPPED=0

for PROJECT_DIR in "$PROJECTS_DIR"/*; do
    if [ -d "$PROJECT_DIR" ]; then
        PROJECT_NAME=$(basename "$PROJECT_DIR")
        TOTAL=$((TOTAL + 1))

        # 跳过特殊目录
        if [[ "$PROJECT_NAME" == _* ]]; then
            echo "⏭️  跳过: $PROJECT_NAME (特殊目录)"
            SKIPPED=$((SKIPPED + 1))
            continue
        fi

        # 检查是否已有配置
        if [ -f "$PROJECT_DIR/.memory-anchor/config.yaml" ]; then
            echo "✅ 已存在: $PROJECT_NAME"
            SKIPPED=$((SKIPPED + 1))
            continue
        fi

        echo "🔧 初始化: $PROJECT_NAME"

        # 创建配置目录
        mkdir -p "$PROJECT_DIR/.memory-anchor"

        # 自动检测项目类型
        PROJECT_TYPE="auto-detect"
        if [ -f "$PROJECT_DIR/package.json" ]; then
            PROJECT_TYPE="javascript"
        elif [ -f "$PROJECT_DIR/pyproject.toml" ]; then
            PROJECT_TYPE="python"
        elif [ -f "$PROJECT_DIR/go.mod" ]; then
            PROJECT_TYPE="go"
        fi

        # 检测业务类型
        if echo "$PROJECT_NAME" | grep -qi "ai"; then
            BUSINESS_TYPE="ai-development"
        elif echo "$PROJECT_NAME" | grep -qi "跨境\|电商\|sextool\|zhizhang"; then
            BUSINESS_TYPE="ecommerce"
        elif echo "$PROJECT_NAME" | grep -qi "mcp\|claude\|apikey"; then
            BUSINESS_TYPE="infrastructure"
        else
            BUSINESS_TYPE="general"
        fi

        # 创建配置文件
        cat > "$PROJECT_DIR/.memory-anchor/config.yaml" <<EOF
# Memory Anchor 项目配置
# 自动生成于: $(date +"%Y-%m-%d %H:%M:%S")
version: 1

# 项目信息
project_name: "$PROJECT_NAME"
project_type: "$PROJECT_TYPE"
business_type: "$BUSINESS_TYPE"

# Qdrant 配置
qdrant:
  # 使用 Server 模式（支持并发）
  url: "http://localhost:6333"

# 记忆配置
memory:
  min_search_score: 0.3
  session_expire_hours: 24
  max_constitution_items: 20

# 置信度阈值
confidence:
  auto_save: 0.9      # >= 0.9 直接存入
  pending_min: 0.7    # 0.7-0.9 待审批
  reject_below: 0.7   # < 0.7 拒绝

# 宪法层保护
constitution:
  approvals_needed: 3

# 项目隔离（关键）
isolation:
  # 严格隔离：只使用本项目的 collection
  strict_mode: true
  # 不共享全局记忆（可根据需要调整）
  share_global: false
  # share_collections:
  #   - "global"           # 取消注释以共享全局知识
  #   - "$BUSINESS_TYPE"   # 取消注释以共享领域知识
EOF

        echo "  ✅ 创建配置: $PROJECT_DIR/.memory-anchor/config.yaml"
        echo "     - 项目类型: $PROJECT_TYPE"
        echo "     - 业务类型: $BUSINESS_TYPE"
        CREATED=$((CREATED + 1))
        echo ""
    fi
done

echo ""
echo "================================"
echo "✅ 初始化完成！"
echo ""
echo "📊 统计："
echo "  - 总项目数: $TOTAL"
echo "  - 新创建配置: $CREATED"
echo "  - 已存在/跳过: $SKIPPED"
echo ""
echo "📋 后续步骤："
echo "  1. 检查每个项目的配置是否正确"
echo "  2. 根据需要调整 share_collections"
echo "  3. 运行验证脚本：check_memory_isolation.sh"
echo ""
echo "🔍 验证命令："
echo "  cd $PROJECTS_DIR/阿默斯海默症"
echo "  ./scripts/check_memory_isolation.sh"
