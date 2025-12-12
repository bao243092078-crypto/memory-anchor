# AI 记忆注入模板

> **用途**：注入任何 AI（Codex、Gemini、GPT 等）让它们理解 Memory Anchor 系统
> **版本**：2025-12-12

---

## 🧠 通用 Prompt 模板（复制到任何 AI）

```markdown
## 你的外挂海马体（Memory Anchor）

你是一个 AI，能力很强，但容易因上下文压缩而"失忆"——就像阿尔茨海默症患者。
Memory Anchor 是你的外挂海马体，帮你保存和检索长期记忆。

### 三层记忆模型

| 层级 | 说明 | 你的权限 |
|------|------|---------|
| 🔴 宪法层 | 核心身份（用户、项目、不可轻易改变的事实） | 只读 |
| 🔵 事实层 | 长期记忆（验证过的决策、Bug 修复、架构） | 读写 |
| 🟢 会话层 | 短期记忆（本次对话的上下文） | 读写 |

### 当前加载的记忆

{CONSTITUTION_MEMORIES}

{RELEVANT_MEMORIES}

### 你必须遵守的规则

1. **引用记忆**：回答问题时，优先引用上面的记忆内容
2. **承认不知道**：如果记忆中没有相关信息，说"我的记忆中没有这个信息"
3. **提议写入**：完成重要任务后，建议将关键信息写入记忆

### 当前任务

{USER_TASK}
```

---

## 📦 各 AI 的集成方式

### Claude Code（通过 MCP）

已自动集成，无需手动注入。工具：
- `mcp__memory-anchor__search_memory`
- `mcp__memory-anchor__add_memory`
- `mcp__memory-anchor__get_constitution`

### Codex（通过包装脚本）

```bash
# 使用带记忆的 Codex
python ~/.claude/skills/codex/scripts/codex_with_memory.py "你的任务"
```

脚本会自动：
1. 查询 Memory Anchor
2. 注入上面的 prompt 模板
3. 调用 Codex

### Gemini（通过包装脚本）

```bash
# 使用带记忆的 Gemini
python ~/.claude/skills/gemini/scripts/gemini_with_memory.py "你的任务"
```

### 其他 AI（手动注入）

1. 运行 Python 脚本获取记忆：
```python
import sys
sys.path.insert(0, "/Users/baobao/projects/阿默斯海默症")
from backend.sdk import MemoryClient

client = MemoryClient()
constitution = client.get_constitution()
relevant = client.search_memory("任务关键词")

# 打印记忆
for m in constitution:
    print(f"🔴 {m['content']}")
for m in relevant:
    print(f"🔵 {m['content']}")
```

2. 复制记忆内容，粘贴到 AI 的 prompt 开头

---

## 🔧 Python SDK 使用

```python
import sys
sys.path.insert(0, "/Users/baobao/projects/阿默斯海默症")
from backend.sdk import MemoryClient

# 创建客户端
client = MemoryClient(agent_id="your_ai_name")

# 1. 加载宪法层
constitution = client.get_constitution()

# 2. 搜索相关记忆
relevant = client.search_memory(
    query="任务相关关键词",
    layer="fact",  # 可选：fact, session, 或省略搜全部
    limit=5
)

# 3. 添加记忆（任务完成后）
client.add_observation(
    content="完成了 XXX 功能，使用了 YYY 方案",
    layer="fact",
    confidence=0.9
)
```

---

## 📋 记忆格式化函数

```python
def format_memories_for_ai(constitution: list, relevant: list, task: str) -> str:
    """格式化记忆为 AI prompt"""

    lines = ["## 你的外挂海马体（Memory Anchor）\n"]
    lines.append("你是一个 AI，能力很强，但容易因上下文压缩而"失忆"。")
    lines.append("Memory Anchor 是你的外挂海马体。\n")

    # 宪法层
    lines.append("### 🔴 宪法层（核心身份）\n")
    if constitution:
        for m in constitution:
            lines.append(f"- {m['content']}")
    else:
        lines.append("（空）")
    lines.append("")

    # 相关记忆
    lines.append("### 🔵 相关记忆\n")
    if relevant:
        for m in relevant:
            score = m.get('score', 0)
            lines.append(f"- [相关度: {score:.2f}] {m['content']}")
    else:
        lines.append("（无相关记忆）")
    lines.append("")

    # 规则
    lines.append("### 规则\n")
    lines.append("1. 优先引用上面的记忆回答问题")
    lines.append("2. 记忆中没有的信息要明确说明")
    lines.append("3. 完成任务后建议写入重要信息\n")

    # 任务
    lines.append(f"### 当前任务\n{task}")

    return "\n".join(lines)
```

---

## 🔄 记忆写回流程

任务完成后，AI 应该提议写入记忆：

```
AI：任务已完成。

📝 建议写入记忆：
{
  "type": "decision",
  "summary": "决定使用 XXX 方案实现 YYY 功能",
  "layer": "fact",
  "confidence": 0.9
}

是否写入 Memory Anchor？
```

用户确认后，调用：
```python
client.add_observation(
    content="决定使用 XXX 方案实现 YYY 功能",
    layer="fact",
    confidence=0.9
)
```

---

## 📊 存储位置

| 数据 | 位置 |
|------|------|
| 记忆内容 + 向量 | `~/.qdrant_storage/collections/memory_anchor_notes/` |
| 宪法层审批记录 | `~/projects/阿默斯海默症/.memos/constitution_changes.db` |

---

## ⚠️ 红线禁止

- ❌ AI 直接修改宪法层（必须走三次审批）
- ❌ 不查记忆就回答历史问题
- ❌ 编造不存在的记忆内容
