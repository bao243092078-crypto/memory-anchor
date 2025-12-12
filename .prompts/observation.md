# Observation 生成模板（Claude 行为规范）

> **触发词**：当用户说"这一步做完了"、"这一轮 debug 结束了"、"总结一下"、"存个记忆"时自动触发

---

## 触发条件

当用户明确表示某个工作阶段结束时，执行以下流程：

```
用户："这一步做完了" / "debug 结束" / "总结一下" / "存个记忆"
         ↓
Claude 自动执行 Observation 生成流程
```

---

## 执行流程

### Step 1: 复述关键进展

用自己的话复述刚才的工作，包括：
- 做了什么
- 为什么这样做
- 结果如何

**示例输出**：
```
刚才完成了：
- 在 MEMORY_STRATEGY.md 中添加了 Observation JSON Schema
- 定义了 5 种类型：decision/bugfix/refactor/discovery/note
- 制定了类型到 layer 的映射规则
```

---

### Step 2: 构造候选 Observation

按照 JSON Schema 构造一条记忆：

```json
{
  "type": "<decision|bugfix|refactor|discovery|note>",
  "summary": "<一句话总结，最多200字符>",
  "details": "<可选的详细说明>",
  "files": ["<相关文件路径>"],
  "layer": "<fact|session>",
  "tags": ["<标签1>", "<标签2>"],
  "created_at": "<ISO时间>",
  "author": "claude-code"
}
```

**类型选择规则**：
| 工作类型 | type | layer |
|---------|------|-------|
| 架构/技术决策 | decision | fact |
| 修复 Bug | bugfix | fact |
| 代码重构 | refactor | fact |
| 发现新信息 | discovery | session |
| 临时笔记 | note | session |

---

### Step 3: 请求用户确认

输出以下格式，等待用户确认：

```
---
**候选 Observation**：

{完整的 JSON}

---
是否存入记忆？
- 输入 `y` 或 `存` → 我将调用 `mcp__memory-anchor__add_memory`
- 输入 `n` 或 `不存` → 跳过
- 输入修改建议 → 我会调整后再确认
```

---

## 完整示例

**场景**：用户说"这一轮 debug 结束了"

**Claude 输出**：

```
刚才完成了：
- 修复了 search_memory 函数的空指针问题
- 原因是 query 为空时直接调用 .split()
- 现在添加了空值检查，返回空列表

---
**候选 Observation**：

{
  "type": "bugfix",
  "summary": "修复 search_memory 空指针：query 为空时返回空列表而非 None",
  "details": "在 memory_service.py 第 42 行添加 `if not query: return []`",
  "files": ["backend/services/memory_service.py"],
  "layer": "fact",
  "tags": ["bugfix", "search", "null-safety"],
  "created_at": "2025-12-11T14:20:00Z",
  "author": "claude-code"
}

---
是否存入记忆？(y/n/修改建议)
```

---

## 注意事项

1. **保留人工确认**：刚开始阶段，所有 Observation 都需要用户确认才存入，避免垃圾记忆
2. **summary 要精炼**：最多 200 字符，一句话说清楚
3. **tags 要有用**：选择能帮助未来检索的关键词
4. **files 要准确**：只列真正修改/涉及的文件
5. **禁止写宪法层**：layer 只能是 `fact` 或 `session`

---

## 快捷触发词

| 用户说 | Claude 行为 |
|-------|------------|
| "做完了" | 生成 Observation |
| "debug 结束" | 生成 bugfix 类型 Observation |
| "总结一下" | 生成 note 类型 Observation |
| "存个记忆" | 直接进入 Step 2 |
| "这个决定很重要" | 生成 decision 类型 Observation |
