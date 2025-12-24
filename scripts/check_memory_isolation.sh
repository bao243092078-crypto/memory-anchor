#!/bin/bash
# Memory Anchor 项目隔离检查脚本
# 用途：检查多个项目的记忆是否正确隔离

set -e

echo "🔍 Memory Anchor 项目隔离检查"
echo "================================"
echo ""

# 1. 检查 Qdrant Server
echo "1️⃣ 检查 Qdrant Server..."
if curl -sf http://localhost:6333/collections > /dev/null; then
    echo "✅ Qdrant Server 运行正常"

    # 统计 collections 数量
    COLLECTION_COUNT=$(curl -s http://localhost:6333/collections | jq -r '.result.collections | length')
    echo "📊 总共有 $COLLECTION_COUNT 个 collections"
else
    echo "❌ Qdrant Server 未运行"
    exit 1
fi
echo ""

# 2. 列出所有项目 collections
echo "2️⃣ 项目 Collections 列表："
curl -s http://localhost:6333/collections | jq -r '.result.collections[].name' | grep "memory_anchor_notes_" | while read -r collection; do
    PROJECT_NAME=${collection#memory_anchor_notes_}

    # 获取记录数
    POINT_COUNT=$(curl -s "http://localhost:6333/collections/$collection" | jq -r '.result.points_count // 0')

    echo "  - $PROJECT_NAME: $POINT_COUNT 条记忆"
done
echo ""

# 3. 检查当前项目配置
echo "3️⃣ 当前项目配置检查："
if [ -f ".memory-anchor/config.yaml" ]; then
    echo "✅ 项目配置文件存在"
    PROJECT_NAME=$(grep "project_name:" .memory-anchor/config.yaml | awk '{print $2}' | tr -d '"')
    echo "📝 项目名称: $PROJECT_NAME"
else
    echo "⚠️  项目配置文件不存在（将使用全局配置或默认值）"
fi
echo ""

# 4. 检查环境变量
echo "4️⃣ 环境变量检查："
if [ -n "$MCP_MEMORY_PROJECT_ID" ]; then
    echo "✅ MCP_MEMORY_PROJECT_ID = $MCP_MEMORY_PROJECT_ID"
else
    echo "⚠️  MCP_MEMORY_PROJECT_ID 未设置"
fi

if [ -n "$QDRANT_URL" ]; then
    echo "✅ QDRANT_URL = $QDRANT_URL"
else
    echo "⚠️  QDRANT_URL 未设置（将使用本地模式）"
fi
echo ""

# 5. 检查 .mcp.json
echo "5️⃣ MCP 配置检查："
if [ -f ".mcp.json" ]; then
    echo "✅ .mcp.json 存在"

    # 检查是否设置了项目 ID
    if grep -q "MCP_MEMORY_PROJECT_ID" .mcp.json; then
        PROJECT_ID=$(jq -r '.mcpServers["memory-anchor"].env.MCP_MEMORY_PROJECT_ID // empty' .mcp.json)
        if [ -n "$PROJECT_ID" ]; then
            echo "✅ MCP 配置中设置了项目 ID: $PROJECT_ID"
        else
            echo "⚠️  MCP 配置中未设置 MCP_MEMORY_PROJECT_ID"
        fi
    else
        echo "⚠️  MCP 配置中未设置项目隔离"
    fi
else
    echo "⚠️  .mcp.json 不存在（使用全局 MCP 配置）"
fi
echo ""

# 6. 推荐配置
echo "📋 推荐配置："
echo ""
echo "方式 1: 项目级配置（.memory-anchor/config.yaml）"
echo "----------------------------------------"
echo "project_name: \"$(basename $(pwd))\""
echo "project_type: \"ai-development\""
echo ""
echo "方式 2: MCP 配置（.mcp.json）"
echo "----------------------------------------"
echo '{'
echo '  "mcpServers": {'
echo '    "memory-anchor": {'
echo '      "command": "uv",'
echo '      "args": ["--directory", "'$(pwd)'", "run", "memory-anchor", "serve"],'
echo '      "env": {'
echo '        "MCP_MEMORY_PROJECT_ID": "'$(basename $(pwd))'"'
echo '      }'
echo '    }'
echo '  }'
echo '}'
echo ""

# 7. 总结
echo "✅ 检查完成！"
echo ""
echo "🔒 隔离建议："
echo "  1. 确保每个项目设置 MCP_MEMORY_PROJECT_ID"
echo "  2. 验证不同项目的 collection 名称不同"
echo "  3. 定期清理无用的 collections"
