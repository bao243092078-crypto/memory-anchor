# Memory Anchor 多项目配置模板

## 快速复制到其他项目

### 1. 创建项目配置文件

```bash
# 在任意项目根目录执行
PROJECT_NAME=$(basename $(pwd))

mkdir -p .memory-anchor
cat > .memory-anchor/config.yaml <<EOF
# Memory Anchor 项目配置
version: 1

project_name: "$PROJECT_NAME"
project_type: "auto-detect"  # 或具体类型：ai-development, ecommerce, etc.

qdrant:
  url: "http://localhost:6333"

memory:
  min_search_score: 0.3
  session_expire_hours: 24

confidence:
  auto_save: 0.9
  pending_min: 0.7
  reject_below: 0.7

constitution:
  approvals_needed: 3

isolation:
  strict_mode: true
  share_global: false
EOF

echo "✅ 配置文件已创建: .memory-anchor/config.yaml"
```

### 2. 添加 MCP 配置（如果项目有 .mcp.json）

```json
{
  "mcpServers": {
    "memory-anchor": {
      "command": "uv",
      "args": [
        "--directory", "/Users/baobao/projects/阿默斯海默症",
        "run", "memory-anchor", "serve",
        "--project", "YOUR_PROJECT_NAME"
      ],
      "env": {
        "MCP_MEMORY_PROJECT_ID": "YOUR_PROJECT_NAME"
      }
    }
  }
}
```

### 3. 验证隔离

```bash
# 在项目目录运行检查脚本
/Users/baobao/projects/阿默斯海默症/scripts/check_memory_isolation.sh
```

---

## 分层策略建议

### 选项 A: 严格隔离（推荐，避免污染）

```yaml
# 每个项目配置
isolation:
  strict_mode: true
  share_global: false
```

**优点**：完全隔离，零污染
**缺点**：无法共享通用知识

### 选项 B: 分层共享（高级）

```yaml
# 全局共享配置（在 ~/.memory-anchor/config.yaml）
shared_collections:
  - name: "global"
    description: "全公司通用知识"
  - name: "ai-development"
    description: "AI 开发领域知识"
  - name: "ecommerce"
    description: "电商领域知识"

# 项目配置（例如：跨境2）
project_name: "跨境2"
project_type: "ecommerce"
isolation:
  strict_mode: false
  share_collections:
    - "global"          # 共享全局知识
    - "ecommerce"       # 共享电商知识
```

**搜索优先级**：
1. 项目专属 collection
2. 领域共享 collections
3. 全局 collection

---

## 批量初始化脚本

### 为所有项目添加配置

```bash
#!/bin/bash
# 批量初始化 Memory Anchor 配置

PROJECTS_DIR="/Users/baobao/projects"

for PROJECT_DIR in "$PROJECTS_DIR"/*; do
    if [ -d "$PROJECT_DIR" ]; then
        PROJECT_NAME=$(basename "$PROJECT_DIR")

        # 跳过特殊目录
        if [[ "$PROJECT_NAME" == _* ]]; then
            continue
        fi

        echo "🔧 初始化项目: $PROJECT_NAME"

        # 创建配置目录
        mkdir -p "$PROJECT_DIR/.memory-anchor"

        # 创建配置文件
        cat > "$PROJECT_DIR/.memory-anchor/config.yaml" <<EOF
version: 1
project_name: "$PROJECT_NAME"
project_type: "auto-detect"

qdrant:
  url: "http://localhost:6333"

isolation:
  strict_mode: true
  share_global: false
EOF

        echo "  ✅ $PROJECT_NAME/.memory-anchor/config.yaml"
    fi
done

echo ""
echo "✅ 批量初始化完成！"
```

---

## 清理无用 Collections

### 查找空 Collections

```bash
# 列出所有空的 collections
curl -s http://localhost:6333/collections | jq -r '.result.collections[] | select(.points_count == 0) | .name'
```

### 删除空 Collection（谨慎）

```bash
# 删除指定 collection
curl -X DELETE "http://localhost:6333/collections/memory_anchor_notes_COLLECTION_NAME"
```

---

## 项目类型推荐配置

### AI 开发项目
```yaml
project_type: "ai-development"
isolation:
  share_collections: ["global", "ai-development"]
```

### 电商项目
```yaml
project_type: "ecommerce"
isolation:
  share_collections: ["global", "ecommerce"]
```

### 基础设施项目
```yaml
project_type: "infrastructure"
isolation:
  share_collections: ["global"]
```

---

## 常见问题

### Q1: 如何合并两个项目的记忆？

```bash
# 导出项目 A 的记忆
curl -s "http://localhost:6333/collections/memory_anchor_notes_项目A/points/scroll" \
  > projectA_memories.json

# 导入到项目 B
# （需要写脚本处理 JSON 格式）
```

### Q2: 如何迁移记忆到新项目名？

```bash
# 方法 1: 重命名 collection（Qdrant 不支持，需要重建）
# 方法 2: 在代码中设置别名

# 在新项目配置中：
legacy_project_names:
  - "旧项目名1"
  - "旧项目名2"
```

### Q3: 如何备份所有项目记忆？

```bash
# 备份整个 Qdrant 数据库
tar -czf qdrant_backup_$(date +%Y%m%d).tar.gz ~/.qdrant_storage/
```
