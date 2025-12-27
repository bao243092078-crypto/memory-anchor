# Twin Mode Architecture - 双模架构设计

> **核心洞见**：把 AI 当作阿尔茨海默症患者——能力很强，但容易因上下文压缩而"失忆"。
> Memory Anchor 是 AI 的外挂海马体。

## 架构哲学

### 为什么把 AI 当作"患者"？

| 阿尔茨海默症患者 | AI（Claude/Codex/Gemini） |
|-----------------|--------------------------|
| 短期记忆受损 | 上下文窗口有限 |
| 长期记忆模糊 | 没有跨会话的持久化记忆 |
| 需要便利贴提醒 | 需要 Memory Anchor |
| 能力正常但易忘事 | 推理能力强但易"失忆" |
| 海马体功能退化 | 没有"海马体"（记忆存储器）|

### 问题

- Claude 受限于上下文窗口（200K tokens）
- Codex 同样有上下文限制
- Gemini 虽有 2M 上下文，但仍会"遗忘"早期信息
- 多个 AI 协同工作时，各自的"记忆"不同步

### 解决方案

- Memory Anchor 作为**外部记忆系统**（External Memory System）= AI 的外挂海马体
- 类比：人类的记忆分为短期记忆（工作记忆）和长期记忆（海马体存储）
- AI 的上下文 = 短期记忆（易失）
- Memory Anchor = 长期记忆（持久化）

**关键洞察**：我们为阿尔茨海默症患者设计的记忆辅助系统，恰好也能解决 AI 的"失忆"问题。这不是巧合——记忆缺失的本质是相同的。

---

## 架构层次

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Storage (存储层)                                    │
│   • Qdrant Server (~/.qdrant_storage/) - 记忆内容 + 向量     │
│   • SQLite (.memos/) - 宪法层变更审批记录                    │
└─────────────────────────────────────────────────────────────┘
                            ↑
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Kernel (核心层)                                     │
│   • MemoryKernel: 同步接口，纯 Python 类                    │
│   • 负责：搜索、添加、宪法管理                                │
│   • 无 async，无外部框架依赖                                 │
└─────────────────────────────────────────────────────────────┘
                   ↑                    ↑
        ┌──────────┴────────┐ ┌────────┴──────────┐
        │  Layer 3a: Mode A │ │ Layer 3b: Mode B  │
        │  MCP Server       │ │ Native SDK        │
        │  AsyncWrapper     │ │ MemoryClient      │
        └──────────┬────────┘ └────────┬──────────┘
                   ↓                    ↓
            [Claude Code]          [Codex CLI]
```

---

## Mode A: MCP Server (for Claude)

**设计**：
- 保持现有 `mcp_memory.py` 的接口不变
- 内部重构为调用 `MemoryKernel`
- async wrapper 包装同步 Kernel

**调用流程**：
```python
# Claude 调用
mcp__memory-anchor__search_memory(query="女儿电话")
    ↓
# MCP Server (async)
@server.call_tool()
async def call_tool(name, args):
    kernel = get_kernel()
    # 在 executor 中运行同步代码
    result = await asyncio.to_thread(kernel.search_memory, args)
    return format_result(result)
```

**优势**：
- Claude Code 无需任何改动
- 向后兼容现有配置
- 继续享受 MCP 协议的安全性和审计

---

## Mode B: Native SDK (for Codex)

**设计**：
- 新建 `backend/sdk/memory_client.py`
- 直接实例化 `MemoryKernel`
- 提供同步 API，无需 asyncio

**调用流程**：
```python
# Codex 调用
from memory_anchor.sdk import MemoryClient

client = MemoryClient(db_path=".memos/patient_1.db")
results = client.search_memory(query="女儿电话")
# 返回 List[dict]，直接可用
```

**优势**：
- 零网络开销（函数直调）
- 同步接口，Codex 脚本易用
- 共享同一个 Qdrant Server（并发安全）

---

## MemoryKernel 设计

**核心类**：
```python
class MemoryKernel:
    """
    Memory Anchor 核心引擎（同步版本）

    职责：
    - 搜索记忆（三层语义检索）
    - 添加记忆（置信度分级）
    - 管理宪法层（三次审批）

    设计原则：
    - 纯 Python，无 async
    - 依赖注入（search_service, note_repo）
    - 无状态（所有状态在存储层）
    """

    def __init__(self, search_service, note_repo=None):
        self.search = search_service
        self.notes = note_repo

    def search_memory(
        self,
        query: str,
        layer: Optional[str] = None,
        limit: int = 5
    ) -> List[dict]:
        """语义搜索记忆"""
        # 实现逻辑...

    def add_memory(
        self,
        content: str,
        layer: str = "fact",
        confidence: float = 0.9
    ) -> dict:
        """添加新记忆"""
        # 实现逻辑...

    def get_constitution(self) -> List[dict]:
        """获取全部宪法层"""
        # 实现逻辑...
```

**关键点**：
1. **同步接口**：Codex 直接调用，无需 `await`
2. **依赖注入**：方便测试和替换存储后端
3. **无状态**：所有状态在 Qdrant + SQLite
4. **线程安全**：使用 Qdrant Server 模式，支持并发

---

## 会话隔离 vs 共享

| 层级 | 是否共享 | 隔离方式 | 说明 |
|------|---------|---------|------|
| **宪法层** | ✅ 完全共享 | 无隔离 | 核心身份，所有 AI 看到一致的信息 |
| **事实层** | ✅ 完全共享 | 无隔离 | 长期记忆，验证过的事实 |
| **会话层** | ❌ 逻辑隔离 | `agent_id` 字段 | 各自的对话上下文 |

**实现**：
```python
# 搜索时过滤
def search_memory(self, query, agent_id=None):
    if agent_id:
        # 会话层：只看自己的
        session_results = search(
            query,
            layer="session",
            filter={"agent_id": agent_id}
        )
    # 宪法层 + 事实层：所有 AI 共享
    shared_results = search(query, layer=["constitution", "fact"])
    return shared_results + session_results
```

---

## 并发一致性保证

**问题**：Claude 和 Codex 同时写入怎么办？

**解决方案**：

1. **Qdrant Server 模式**：
   - 使用 HTTP API（内置并发控制）
   - 支持多客户端同时连接

2. **SQLite WAL 模式**：
   - 写者不阻塞读者
   - 行级锁（row-level locking）

3. **写入策略**：
   - **Codex 只读**（默认）
   - 写入由 Claude 统一管理
   - 如果 Codex 需要写，通过 `propose_memory()` 提议，Claude 审批

**配置示例**：
```python
# SQLite WAL 模式
import sqlite3
conn = sqlite3.connect(".memos/metadata.db")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
```

---

## 安全和隐私

**红线**：
1. **Codex 不能写宪法层**（保护核心身份）
2. **医疗信息不传给外部 AI**（隐私合规）
3. **三次审批不可绕过**（宪法层修改）

**实现**：
```python
class MemoryKernel:
    def add_memory(self, content, layer, source="unknown"):
        # 宪法层保护
        if layer == "constitution" and source != "caregiver":
            raise PermissionError("宪法层只能由照护者修改")

        # 敏感信息过滤（传给 Codex 时）
        if source == "external_ai":
            content = filter_sensitive_info(content)

        # 继续处理...
```

---

## 部署和配置

**启动 Qdrant Server**：
```bash
docker run -d \
  -p 6333:6333 \
  -v $(pwd)/.qdrant_data:/qdrant/storage:z \
  --name qdrant \
  qdrant/qdrant
```

**环境变量**：
```bash
# 项目隔离（不同项目使用不同 collection）
export MCP_MEMORY_PROJECT_ID=alzheimer

# Qdrant 连接
export QDRANT_URL=http://localhost:6333

# SQLite 数据库
export MEMORY_DB_PATH=.memos/metadata.db
```

**Claude Code 配置** (`.claude.json`):
```json
{
  "mcpServers": {
    "memory-anchor": {
      "command": "uv",
      "args": ["run", "backend/mcp_memory.py"],
      "env": {
        "MCP_MEMORY_PROJECT_ID": "alzheimer"
      }
    }
  }
}
```

**Codex Skill 配置**：
```python
# ~/.claude/skills/codex/scripts/codex_with_memory.py
import os
os.environ["MCP_MEMORY_PROJECT_ID"] = "alzheimer"

from memory_anchor.sdk import MemoryClient
client = MemoryClient()
```

---

## 实施路径

**Phase 1: MemoryKernel 抽离（本周）**
- [ ] 创建 `backend/core/memory_kernel.py`
- [ ] 迁移核心逻辑（同步版本）
- [ ] 单元测试

**Phase 2: Mode B SDK（本周）**
- [ ] 创建 `backend/sdk/memory_client.py`
- [ ] Codex 包装脚本
- [ ] 集成测试（Claude + Codex 同时访问）

**Phase 3: Mode A 重构（下周）**
- [ ] 重构 `mcp_memory.py` 使用 Kernel
- [ ] 向后兼容测试

**Phase 4: 多模态扩展（未来）**
- [ ] 图片 embedding（家人照片识别）
- [ ] 音频特征（情绪检测）
- [ ] 长上下文分析（认知衰退检测）

---

## 测试策略

**单元测试**：
```python
# 测试 MemoryKernel
def test_search_memory():
    kernel = MemoryKernel(mock_search, mock_repo)
    results = kernel.search_memory("女儿电话")
    assert len(results) > 0
```

**集成测试**：
```python
# 测试 Claude + Codex 并发访问
async def test_concurrent_access():
    # Claude 通过 MCP
    claude_results = await mcp_client.call_tool("search_memory", {"query": "test"})

    # Codex 通过 SDK（在线程中运行）
    codex_results = await asyncio.to_thread(
        lambda: MemoryClient().search_memory("test")
    )

    # 验证结果一致
    assert claude_results == codex_results
```

---

## FAQ

**Q: 为什么不让 Codex 也用 MCP 协议？**
A: Codex 是 Python 脚本，直接函数调用比网络协议更高效。MCP 设计为 stdio 单连接，不适合多客户端。

**Q: 如果 Qdrant Server 挂了怎么办？**
A: 当前为 fail-fast，不会自动降级。本地模式仅用于测试，需显式配置 `QDRANT_PATH` 或通过构造参数传入 `path`。

**Q: 会话层是否需要物理隔离？**
A: 不需要。使用逻辑隔离（`agent_id` 字段过滤）即可。物理隔离（多个 collection）会增加复杂度。

**Q: 如何防止记忆冲突？**
A:
1. Codex 默认只读，写入由 Claude 管理
2. 如需 Codex 写入，通过 `confidence < 0.9` 标记为待审批
3. 使用版本号（未来）实现乐观锁

---

## 总结

双模架构让 Memory Anchor 成为真正的"多 AI 共享记忆系统"：

- **MemoryKernel**：纯净的核心引擎，无框架依赖
- **Mode A (MCP)**：Claude 的标准接入方式，安全可审计
- **Mode B (SDK)**：Codex 的高性能接入方式，零网络开销
- **共享存储**：Qdrant Server + SQLite WAL，并发安全

就像阿尔茨海默症患者需要便利贴来弥补失忆，AI 需要 Memory Anchor 来克服上下文限制。
