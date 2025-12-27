# Memory Anchor 记忆可追溯性增强设计

> 日期：2025-12-27
> 状态：✅ 已完成（2025-12-27）

## 背景

基于 Claude-Mem 竞品调研，用户核心需求：
1. **让 AI 不要失忆** - 记忆能正确存储和检索（已有）
2. **可以找到记忆来源** - 可追溯性（本次增强）

用户强调"技能太多会不纯粹"，因此采用最小改动方案。

## 设计决策

### 优先级排序
1. **related_files**（最高）— 定位相关代码
2. **session_id**（次之）— 时间线追踪
3. ~~source_context~~（不做）— 通过 session_id 追溯即可

### 关键决策
- **related_files 半自动填充**：AI 可选填，不填则从 StateManager 获取
- **session_id 复用现有机制**：StateManager 已有 `YYYYMMDD_HHMMSS` 格式
- **StateManager 自动初始化 + 优雅降级**：没会话时尝试创建，失败则字段为空

## 数据模型变更

### NoteResponse 新增字段

```python
# backend/models/note.py

class NoteResponse(BaseModel):
    # 现有字段...
    id: UUID
    content: str
    layer: MemoryLayer
    category: NoteCategory | None = None
    confidence: float = 1.0
    created_at: datetime

    # 新增可追溯字段（可选，向后兼容）
    session_id: str | None = None          # 记录时的会话 ID
    related_files: list[str] | None = None # 关联的文件列表
```

## 实现逻辑

### add_memory 自动填充

```python
# backend/mcp_memory.py

async def handle_add_memory(arguments: dict) -> str:
    # 1. 获取 StateManager（自动初始化）
    state_manager = get_state_manager()
    session = state_manager.get_current_session()

    # 2. 如果没有会话，尝试自动启动
    if session is None:
        try:
            session = state_manager.start_session()
        except Exception:
            session = None  # 降级

    # 3. 自动填充
    session_id = session.session_id if session else None
    related_files = list(session.source_files) if session else None

    # 4. 存储
    result = await memory_service.add_memory(
        content=arguments["content"],
        layer=arguments.get("layer"),
        category=arguments.get("category"),
        confidence=arguments.get("confidence", 0.8),
        session_id=session_id,
        related_files=related_files,
    )
```

### search_memory 返回结果

```json
{
    "memories": [
        {
            "content": "修复了 search_memory 空查询问题",
            "layer": "verified_fact",
            "created_at": "2025-12-26T10:30:00Z",
            "score": 0.92,
            "session_id": "20251226_103052",
            "related_files": ["backend/services/search.py"]
        }
    ]
}
```

## 改动文件清单

| 文件 | 改动 |
|------|------|
| `backend/models/note.py` | NoteResponse 增加 session_id, related_files |
| `backend/services/memory.py` | MemoryAddRequest 增加新字段 |
| `backend/mcp_memory.py` | add_memory 处理增加自动填充逻辑 |
| `backend/core/memory_kernel.py` | write_memory 支持新字段存入 Qdrant |

## 不做的事

- ❌ 不加 source_context
- ❌ 不新增 MCP 工具
- ❌ 不改 AI 调用方式
- ❌ 不做渐进式披露、自动捕获等复杂功能

## 兼容性

- 旧记忆数据：新字段返回 `null`
- AI 调用方式：完全不变
- MCP 工具数量：保持 14 个
