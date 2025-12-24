# SOP: 记忆同步（Pending → Qdrant）

**触发条件**：
- `.memos/pending.md` 有待同步内容
- MCP 离线后恢复
- 用户说"同步记忆"、"同步 pending"

**前置条件**：
- Qdrant Server 运行中（参见 `sop-qdrant-startup.md`）
- `QDRANT_URL` 环境变量已设置

**预期结果**：
- Pending 记忆写入 Qdrant
- `.memos/pending.md` 清空

---

## 步骤

### 1. 检查 Pending 内容

```bash
cat ~/.memos/pending.md
```

如果只有模板头（无实际记忆），无需同步。

### 2. 确认 Qdrant 在线

```bash
NO_PROXY=localhost,127.0.0.1 curl -s http://127.0.0.1:6333/collections | head -c 50
```

### 3A. 通过 MCP 同步（推荐）

如果 MCP 在线，直接调用：
```python
mcp__memory-anchor__add_memory(
    content="<pending 中的内容>",
    layer="verified_fact",  # 或 event_log
    category="event",
    confidence=0.9
)
```

### 3B. 通过 Python CLI 同步（MCP 离线时）

```bash
cd /Users/baobao/projects/阿默斯海默症

# 设置环境变量
export QDRANT_URL="http://127.0.0.1:6333"
export MCP_MEMORY_PROJECT_ID="alzheimer"

# Python 直接写入
uv run python -c "
from backend.services.search import SearchService
from backend.core.memory_kernel import MemoryKernel
from backend.models.note import MemoryLayer

search = SearchService()
kernel = MemoryKernel(search_service=search)

note_id = kernel.add_memory(
    content='<记忆内容>',
    layer=MemoryLayer.VERIFIED_FACT,
    category='event',
    confidence=0.9
)
print(f'Written: {note_id}')
"
```

### 4. 清空 Pending

同步成功后，清空 pending.md：

```bash
cat > ~/.memos/pending.md << 'EOF'
# Pending Memories (MCP Offline Fallback)

> 当 Memory Anchor MCP 离线时，记忆暂存于此
> MCP 恢复后，使用 CLI 同步到 Qdrant

---

<!-- No pending memories -->
EOF
```

---

## 常见问题

### Q: MCP 报 QDRANT_URL 错误
A: MCP 在 Qdrant 启动前启动了。使用 Python CLI 直接写入，或重启 Claude Code。

### Q: 如何批量同步多条 pending
A: 逐条调用 `add_memory`，每条独立 ID。

---

## 相关文件
- `.ai/operations/sop-qdrant-startup.md` - Qdrant 启动 SOP
- `~/.memos/pending.md` - Pending 记忆存储位置
