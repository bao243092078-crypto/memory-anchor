# Workflow: 会话开始标准流程

**触发条件**：
- 新会话开始
- 用户说"开始工作"、"恢复上下文"
- 上下文压缩后恢复

**预期结果**：
- 加载项目核心身份（L0）
- 恢复相关记忆（L3）
- 准备好工作上下文

---

## 流程图

```
┌─────────────────────────────────────────┐
│  Step 1: 检查基础设施                    │
│    - Qdrant Server 运行？               │
│    - MCP 连接正常？                      │
│    ↓                                    │
│  Step 2: 加载 L0 身份图式                │
│    get_constitution()                   │
│    ↓                                    │
│  Step 3: 搜索相关 L3 记忆                │
│    search_memory(task_keywords)         │
│    ↓                                    │
│  Step 4: 检查 L4 操作知识                │
│    是否有相关 SOP？                      │
│    ↓                                    │
│  Step 5: 开始工作                        │
└─────────────────────────────────────────┘
```

---

## 详细步骤

### Step 1: 检查基础设施

SessionStart hook 会自动执行此检查：
- 输出 `[Memory Anchor] Qdrant OK` = 正常
- 输出 `[Memory Anchor] Qdrant offline` = 需要启动

如果 Qdrant 离线，参见 `sop-qdrant-startup.md`。

### Step 2: 加载 L0 身份图式

```python
constitution = mcp__memory-anchor__get_constitution()
# 宪法层始终全量加载，不依赖检索
```

核心身份包括：
- 项目名称和目标
- 核心隐喻（AI = 阿尔茨海默症患者）
- 绝对不做的事情

### Step 3: 搜索相关 L3 记忆

```python
# 根据用户任务生成 query
query = "用户任务的关键词"

memories = mcp__memory-anchor__search_memory(
    query=query,
    limit=5
)
```

### Step 4: 检查 L4 操作知识

```python
# 检查是否有相关 SOP
Read(".ai/operations/index.yaml")

# 如果任务匹配某个 SOP，加载它
# 例如：任务涉及 "qdrant" → 加载 sop-qdrant-startup.md
```

### Step 5: 开始工作

上下文准备完成，可以开始处理用户任务。

---

## 快速参考

```bash
# 一键检查（终端）
curl -s http://127.0.0.1:6333/collections | head -c 50

# MCP 调用顺序
1. get_constitution()
2. search_memory(query)
3. Read(".ai/operations/index.yaml")  # 可选
```

---

## 相关文件
- `.ai/NORTH_STAR.md` - 项目北极星
- `.ai/PLAN.md` - 当前计划
- `~/.claude/rules-lite/12-memory-anchor.md` - 全局记忆规则
