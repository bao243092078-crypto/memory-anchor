# Twin Mode - 双模架构快速入门

> **核心理念**：把 AI 当作阿尔茨海默症患者——能力很强，但容易因上下文压缩而"失忆"。

## 项目哲学

### 为什么 AI 是"患者"？

| 阿尔茨海默症患者 | AI（Claude/Codex） |
|-----------------|-------------------|
| 短期记忆受损 | 上下文窗口有限（200K token）|
| 长期记忆模糊 | 没有跨会话的持久化记忆 |
| 需要便利贴提醒 | 需要 Memory Anchor |
| 能力正常但易忘事 | 推理能力强但易"失忆" |
| 海马体功能退化 | 没有"海马体"（记忆存储器）|

### 核心洞察

我们为阿尔茨海默症患者设计的记忆辅助系统，恰好也能解决 AI 的"失忆"问题。

这不是巧合，而是因为**记忆缺失的本质是相同的**：
- 都是高功能个体（患者生活能力正常、AI 推理能力强）
- 都是记忆存储/检索出了问题（患者海马体受损、AI 上下文压缩）
- 都需要外部记忆系统来弥补（便利贴 vs Memory Anchor）

**Memory Anchor = AI 的外挂海马体** 🧠

---

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│              Memory Anchor (外挂记忆系统)                │
│                                                           │
│  ┌────────────────────────────────────────────────────┐ │
│  │         MemoryKernel (核心记忆处理器)               │ │
│  │  • 语义搜索  • 添加记忆  • 宪法管理                 │ │
│  └────────────────────────────────────────────────────┘ │
│           ↑                                ↑              │
│   ┌───────┴────────┐             ┌────────┴──────────┐  │
│   │   Mode A       │             │   Mode B          │  │
│   │  MCP Server    │             │  Native SDK       │  │
│   └───────┬────────┘             └────────┬──────────┘  │
└───────────┼──────────────────────────────┼──────────────┘
            ↓                               ↓
      ┌─────────┐                     ┌─────────┐
      │ Claude  │                     │ Codex   │
      │ "患者1" │                     │ "患者2" │
      └─────────┘                     └─────────┘
```

---

## 快速开始

### 1. 启动 Qdrant Server（必需）

```bash
# 启动 Qdrant Server（支持并发访问）
# 数据存储在 ~/.qdrant_storage/（全局共享）
docker run -d \
  -p 6333:6333 \
  -v ~/.qdrant_storage:/qdrant/storage:z \
  --name qdrant \
  qdrant/qdrant

# 告诉 Memory Anchor 使用 Server 模式（否则默认走本地模式）
export QDRANT_URL=http://localhost:6333

# 验证启动
curl http://localhost:6333/readyz
# 应返回 "all shards are ready"
```

### 2. Claude 使用（Mode A: MCP）

Claude Code 通过 MCP 协议访问（已配置在 `.claude.json`）：

```python
# Claude 调用示例（无需手动操作，自动可用）
mcp__memory-anchor__search_memory(query="女儿电话")
# 返回：[{"content": "女儿王小红，电话13800138000", ...}]

mcp__memory-anchor__get_constitution()
# 返回：全部宪法层记忆
```

### 3. Codex 使用（Mode B: Native SDK）

#### 方式 1：包装脚本（推荐）

```bash
# 使用带记忆的 Codex
python ~/.claude/skills/codex/scripts/codex_with_memory.py "分析患者最近的服药记录"

# 脚本会自动：
# 1. 查询 Memory Anchor 获取相关记忆
# 2. 将记忆注入到 Codex prompt
# 3. 调用 Codex 执行任务
```

#### 方式 2：Python SDK（直接调用）

```python
# 在任何 Python 脚本中使用
import sys
sys.path.insert(0, "/Users/baobao/projects/阿默斯海默症")

from backend.sdk import MemoryClient

# 创建客户端
client = MemoryClient(agent_id="codex")

# 搜索记忆
results = client.search_memory("女儿电话")
for r in results:
    print(f"[{r['layer']}] {r['content']}")

# 获取宪法层
constitution = client.get_constitution()

# 添加观察记录
client.add_observation(
    content="患者提到明天要去看医生",
    layer="fact",
    confidence=0.85
)
```

---

## 记忆层级和共享策略

| 层级 | 是否共享 | 说明 | 示例 |
|------|---------|------|------|
| **宪法层** | ✅ 完全共享 | 核心身份，所有 AI 看到一致 | 患者姓名、家人、用药 |
| **事实层** | ✅ 完全共享 | 长期记忆，验证过的事实 | 历史事件、设计决策 |
| **会话层** | ❌ 逻辑隔离 | 各自的对话上下文 | Claude 的对话、Codex 的分析 |

**隔离机制**：
- 通过 `agent_id` 字段区分不同 AI 的会话
- Claude: `agent_id="claude"`
- Codex: `agent_id="codex"`
- 搜索时自动过滤（只看自己的会话层记忆）

---

## 并发安全保证

**Qdrant Server 模式**：
- ✅ 支持多客户端并发访问
- ✅ 内置锁机制，无需担心冲突
- ✅ HTTP API，网络层天然隔离

**写入策略**：
- **Codex 默认只读**（搜索记忆）
- 如需写入，通过 `add_observation()` 添加
- 置信度 < 0.9 的记录进入待审批区（需 Claude 确认）

---

## 测试验证

### 运行集成测试

```bash
cd ~/projects/阿默斯海默症

# 运行双模集成测试
uv run pytest backend/tests/test_twin_mode_integration.py -v

# 测试场景：
# 1. SDK → MCP 一致性
# 2. MCP → SDK 一致性
# 3. 宪法层一致性
# 4. 并发访问
# 5. 会话层隔离
```

### 手动验证

```bash
# 1. 通过 Codex SDK 添加测试记忆
python3 -c "
import sys; sys.path.insert(0, '~/projects/阿默斯海默症')
from backend.sdk import MemoryClient
client = MemoryClient()
client.add_observation('测试记忆-Codex', layer='fact', confidence=0.95)
"

# 2. 通过 Claude 查询（在 Claude Code 中执行）
# mcp__memory-anchor__search_memory(query="测试记忆")
# 应该能查到 "测试记忆-Codex"
```

---

## 数据存储位置

### 记忆数据（Qdrant）

所有记忆内容和向量存储在 Qdrant：

```
~/.qdrant_storage/
└── collections/
    └── memory_anchor_notes/      # 默认 collection
        └── 0/segments/           # 数据段
            ├── */payload_storage/  # 记忆内容（JSON）
            └── */vector_storage/   # 384维语义向量
```

- **Collection**: `memory_anchor_notes`（当前 19 条记忆）
- **向量维度**: 384 (MiniLM-L12-v2)
- **访问方式**: http://localhost:6333

### 元数据（SQLite）

```
~/projects/阿默斯海默症/.memos/
├── constitution_changes.db   # 宪法层变更审批记录
└── memos_users.db            # MOS 用户元数据（未使用）
```

### 查看记忆统计

```bash
# 查看 collection 信息
curl http://localhost:6333/collections/memory_anchor_notes

# 查看记忆条数
curl -s http://localhost:6333/collections/memory_anchor_notes | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['points_count'])"
```

---

## 环境变量

```bash
# 项目隔离（不同项目使用不同 collection）
export MCP_MEMORY_PROJECT_ID=alzheimer

# Qdrant 连接
export QDRANT_URL=http://localhost:6333
```

---

## 故障排查

### Qdrant Server 未启动

**症状**：
```
ConnectionError: [Errno 61] Connection refused
```

**解决**：
```bash
# 检查 Qdrant 是否运行
curl http://localhost:6333/readyz

# 如果未运行，启动
docker start qdrant

# 如果不存在容器，创建
docker run -d -p 6333:6333 --name qdrant qdrant/qdrant
```

### 导入 SDK 失败

**症状**：
```
ImportError: No module named 'backend.sdk'
```

**解决**：
```python
# 确保添加项目路径
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "projects" / "阿默斯海默症"))
```

### 记忆不一致

**症状**：Claude 能查到，Codex 查不到（或反之）

**原因**：
1. 索引延迟（添加后立即查询）
2. 会话层隔离（检查 `agent_id`）
3. Qdrant collection 不同（检查 `MCP_MEMORY_PROJECT_ID`）

**解决**：
```python
# 1. 添加延迟
import time
client.add_observation(...)
time.sleep(0.5)  # 等待索引完成

# 2. 检查环境变量
import os
print(os.getenv("MCP_MEMORY_PROJECT_ID"))  # 应为 "alzheimer"

# 3. 检查 collection
from backend.services.search import get_search_service
service = get_search_service()
print(service.get_stats())
```

---

## 下一步

### Phase 1: 验证基础功能（本周）
- [ ] 运行集成测试，确保 Claude 和 Codex 能看到一致的记忆
- [ ] 在真实场景测试（让 Codex 帮助分析项目历史）

### Phase 2: 多模态扩展（下周）
- [ ] 图片 embedding（家人照片识别）
- [ ] 音频特征（情绪检测）
- [ ] 长上下文分析（认知衰退检测）

### Phase 3: 生产优化（未来）
- [ ] 记忆压缩（超过 10000 条时）
- [ ] 自动归档（会话层 → 事实层）
- [ ] 多项目隔离（不同患者的记忆分离）

---

## 参考文档

- 架构设计：`docs/TWIN_MODE_ARCHITECTURE.md`
- 记忆策略：`docs/MEMORY_STRATEGY.md`
- API 文档：`backend/sdk/memory_client.py` (docstrings)
- 集成测试：`backend/tests/test_twin_mode_integration.py`

---

## 总结

双模架构让 Memory Anchor 成为真正的"多 AI 共享记忆系统"：

- **MemoryKernel**：纯净的核心引擎，无框架依赖
- **Mode A (MCP)**：Claude 的标准接入方式，安全可审计
- **Mode B (SDK)**：Codex 的高性能接入方式，零网络开销
- **共享存储**：Qdrant Server（~/.qdrant_storage/），支持并发

**核心哲学**：把 AI 当作阿尔茨海默症患者——能力强但易失忆，Memory Anchor 是它们的外挂海马体。
