"""
Memory Anchor MCP Server - Tool Description Comparison

精简版工具描述对比（已应用到 mcp_memory.py）

Token 节省估算：
- 原版 14 个工具: ~12,000-15,000 字符 → ~4,000-5,000 tokens
- 精简版 14 个工具: ~1,200 字符 → ~400 tokens
- 节省: ~10,000+ tokens (约 70-80%)
"""

# === 精简后的工具描述（已应用到 mcp_memory.py）===

TOOL_DESCRIPTIONS = {
    "search_memory": "搜索记忆。涉及历史/决策/Bug/上下文时必须先调用。",
    "add_memory": "添加记忆。禁止写入identity_schema层。confidence≥0.9直接存，0.7-0.9待确认，<0.7拒绝。",
    "get_constitution": "获取核心身份(L0层)。会话开始时调用。",
    "delete_memory": "删除记忆(高风险)。confirmation须含'确认删除'。禁止删除L0层。",
    "propose_constitution_change": "提议修改L0层(需三次审批)。仅创建提议，不立即生效。",
    "sync_to_files": "导出记忆到.memos/目录(Markdown备份)。会话结束时调用。",
    "log_event": "记录事件到L2层(带when/where/who时空标记)。",
    "search_events": "搜索L2事件日志。支持时间/地点/人物过滤。",
    "promote_to_fact": "将事件提升为事实(L2→L3)。提升后永久保留。",
    "get_checklist_briefing": "获取清单简报。会话开始时调用。返回(ma:xxx)引用ID。",
    "sync_plan_to_checklist": "同步Plan到清单。解析[x]和@persist标签。会话结束时调用。",
    "create_checklist_item": "创建清单项。priority:1紧急/2高/3普通/4低/5待定。",
    "search_operations": "搜索SOP/Workflow(L4层)。遇到基础设施/流程问题时先调用。",
    "refine_memory": "LLM精炼/压缩记忆。需配置API Key。记忆过多时用于节省token。",
}

# === 精简前后对比示例 ===

BEFORE_AFTER_EXAMPLE = """
### search_operations 对比

**精简前 (~700 字符):**
```
搜索 L4 操作性知识（SOP/Workflow）。

⚠️ **强制调用场景**：遇到以下情况时，必须先调用此工具查找 SOP：

**基础设施问题**：
- Qdrant 未运行、502 Bad Gateway、QDRANT_URL 错误
- MCP 连接失败、记忆系统故障
- 需要启动/重启服务

**开发流程问题**：
- 会话开始时的标准流程
- 记忆同步（pending → Qdrant）
- 上下文恢复

**核心原则**：
- L4 操作性知识 = AI 的"肌肉记忆"
- 遇到已有 SOP 的问题，应该按 SOP 执行，而不是重新思考
- 这符合北极星原则："不依赖 AI 自觉（要有强制机制）"

**输入**：问题关键词（如 "qdrant"、"pending"、"会话开始"）
**输出**：匹配的 SOP 文件路径和简要说明

**示例查询**：
- "qdrant" → 返回 sop-qdrant-startup.md
- "pending" → 返回 sop-memory-sync.md
- "会话开始" → 返回 workflow-session-start.md
```

**精简后 (~55 字符):**
```
搜索SOP/Workflow(L4层)。遇到基础设施/流程问题时先调用。
```

节省: ~92%
"""
