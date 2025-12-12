# 阿默斯海默记忆助手 Skill 说明书

> **版本**: v0.1 草稿
> **作者**: Claude Code
> **日期**: 2025-12-11
> **状态**: 草稿待审核

---

## 1. Skill 概述

### 1.1 定位
**阿默斯海默记忆助手**是一个为阿尔茨海默症患者及其照护者设计的记忆辅助 Skill。它不是存储引擎，而是**记忆行为的抽象层**，负责定义"该怎么想起、怎么记录、怎么治理"。

### 1.2 设计原则
- **极简 > 功能丰富**：只做三件事
- **行为 > 存储**：Skill 不关心底层是 Qdrant、ChromaDB 还是 MemOS
- **可插拔**：底层引擎可随时替换，Skill 代码不变

### 1.3 三层架构
```
┌─────────────────────────────────────────────────────┐
│  Skill 层（行为）                                    │
│  - recall(): 我想起了什么？                          │
│  - log(): 记下这件事                                 │
│  - governance(): 宪法层治理                          │
└─────────────────────┬───────────────────────────────┘
                      │ 调用
┌─────────────────────▼───────────────────────────────┐
│  MCP Tools 层（接口）                                │
│  - search_memory: 语义搜索                           │
│  - add_memory: 添加记忆                              │
│  - get_constitution: 获取宪法层                      │
│  - propose_constitution_change: 提议宪法变更         │
└─────────────────────┬───────────────────────────────┘
                      │ 依赖
┌─────────────────────▼───────────────────────────────┐
│  MemoryBackend 层（引擎）                            │
│  - QdrantMemoryBackend (当前)                        │
│  - McpMemoryServiceBackend (规划)                    │
│  - MemOSBackend (规划)                               │
└─────────────────────────────────────────────────────┘
```

---

## 2. Skill 行为定义

### 2.1 recall() - 回忆

**职责**：根据当前上下文，主动召回相关记忆

**触发场景**：
| 场景 | 示例输入 | 期望行为 |
|------|---------|---------|
| 身份相关 | "我叫什么名字" | 返回宪法层核心身份 |
| 人物相关 | "女儿的电话" | 搜索 person 类别 |
| 事件相关 | "上次去医院" | 搜索 event 类别 |
| 开发相关 | "之前修的 Bug" | 搜索 bugfix 类型记忆 |

**调用链**：
```
recall(query)
  → search_memory(query, include_constitution=True)
    → MemoryBackend.search(SearchRequest)
      → Qdrant/ChromaDB/MemOS
```

**返回格式**：
```json
{
  "constitution": [
    {"content": "患者姓名王明", "category": "person"}
  ],
  "relevant": [
    {"content": "女儿王小红电话13800138000", "score": 0.92, "layer": "fact"}
  ]
}
```

### 2.2 log() - 记录

**职责**：将重要信息写入记忆系统

**触发场景**：
| 场景 | layer | 置信度处理 |
|------|-------|-----------|
| 照护者手动添加 | fact | 直接存入 |
| AI 提取（高置信） | fact | ≥0.9 直接存入 |
| AI 提取（中置信） | pending | 0.7-0.9 待审批 |
| AI 提取（低置信） | rejected | <0.7 拒绝 |
| 临时会话信息 | session | 24h 后归档 |

**调用链**：
```
log(content, layer, confidence)
  → add_memory(content, layer, confidence)
    → MemoryBackend.add(AddRequest)
      → 置信度分级处理
      → Qdrant/ChromaDB/MemOS
```

**返回格式**：
```json
{
  "status": "saved | pending_approval | rejected",
  "id": "uuid",
  "layer": "fact",
  "confidence": 0.85,
  "requires_approval": false
}
```

### 2.3 governance() - 治理

**职责**：管理宪法层变更（需三次审批）

**流程**：
```
1. Skill 调用 propose_constitution_change()
2. 创建 pending 状态的变更提议
3. 照护者审批 3 次
4. approvals_count >= 3 时自动应用
```

**支持的操作**：
| 操作 | change_type | 说明 |
|------|------------|------|
| 新增 | create | 添加新的宪法条目 |
| 修改 | update | 修改现有条目（需 target_id） |
| 删除 | delete | 删除条目（需 target_id） |

**调用链**：
```
governance(change_type, content, reason)
  → propose_constitution_change(change_type, content, reason)
    → 创建待审批记录
    → 等待照护者审批（API: POST /api/v1/constitution/approve/{id}）
```

---

## 3. 三层记忆模型

### 3.1 宪法层（Constitution）
- **特点**：核心身份，始终全量加载
- **修改**：需三次审批，AI 不可直接写入
- **内容**：姓名、家人、住址、用药、过敏

### 3.2 事实层（Fact）
- **特点**：长期记忆，经过验证
- **修改**：AI 可写入（受置信度限制）
- **内容**：历史事件、设计决策、Bug 修复

### 3.3 会话层（Session）
- **特点**：短期记忆，24h 后归档
- **修改**：自由写入
- **内容**：当前对话上下文、临时笔记

---

## 4. 分类枚举（Category）

| Category | 说明 | 示例 |
|----------|------|------|
| person | 人物 | 女儿王小红 |
| place | 地点 | 北京协和医院 |
| event | 事件 | 上周去公园 |
| item | 物品 | 红色毛衣 |
| routine | 习惯 | 每天早上吃药 |
| decision | 决策（开发） | 选用 Qdrant |
| bugfix | Bug 修复（开发） | 修复空指针 |
| context | 上下文 | 项目背景 |

---

## 5. MCP 工具映射

| Skill 行为 | MCP Tool | 说明 |
|-----------|----------|------|
| recall() | search_memory | 语义搜索 |
| recall() | get_constitution | 获取核心身份 |
| log() | add_memory | 添加记忆 |
| governance() | propose_constitution_change | 宪法变更提议 |

---

## 6. 可插拔后端接口

### 6.1 MemoryBackend Protocol

```python
class MemoryBackend(Protocol):
    async def search(self, request: SearchRequest) -> list[MemoryItem]: ...
    async def add(self, request: AddRequest) -> AddResult: ...
    async def get_constitution(self) -> list[MemoryItem]: ...
    async def get_by_id(self, memory_id: UUID) -> Optional[MemoryItem]: ...
    async def delete(self, memory_id: UUID) -> bool: ...
    async def get_timeline(self, since: Optional[datetime], limit: int) -> list[MemoryItem]: ...
```

### 6.2 当前实现

| 后端 | 状态 | 说明 |
|------|------|------|
| QdrantMemoryBackend | ✅ 已实现 | 基于 Qdrant 向量数据库 |
| McpMemoryServiceBackend | 🔜 规划 | 基于 mcp-memory-service |
| MemOSBackend | 🔜 规划 | 基于 MemOS |

---

## 7. 使用示例

### 7.1 照护场景

```python
# 场景：患者问女儿电话
query = "女儿电话"
memories = await skill.recall(query)
# → 返回: [宪法层] 女儿王小红，电话13800138000

# 场景：记录今天的事件
await skill.log(
    content="今天女儿来看望了患者，带了苹果",
    layer="fact",
    category="event",
    confidence=0.9
)

# 场景：修改联系方式
await skill.governance(
    change_type="update",
    content="女儿新电话：13900139000",
    reason="女儿换了号码",
    target_id="原条目UUID"
)
```

### 7.2 开发场景

```python
# 场景：查询之前的设计决策
query = "为什么用 Qdrant"
memories = await skill.recall(query)
# → 返回: [fact] 选择 Qdrant 因为支持 Server 模式，解决并发锁问题

# 场景：记录 Bug 修复
await skill.log(
    content="修复 search_memory 空查询返回 None 导致空指针",
    layer="fact",
    category="bugfix",
    confidence=0.95
)
```

---

## 8. 注册为 Claude Skill

### 8.1 Skill 目录结构

```
~/.claude/skills/memory-anchor/
├── skill.md          # Skill 说明（本文件精简版）
├── prompts/
│   ├── recall.md     # recall 行为的 prompt
│   ├── log.md        # log 行为的 prompt
│   └── governance.md # governance 行为的 prompt
└── scripts/          # 可选的辅助脚本
```

### 8.2 skill.md 模板

```markdown
# Memory Anchor Skill

为阿尔茨海默症患者提供记忆辅助。

## 触发词
- "查记忆"、"想起"、"回忆" → recall()
- "记下"、"记录"、"保存" → log()
- "修改宪法"、"更新核心信息" → governance()

## 依赖
- MCP Server: memory-anchor

## 行为
1. **recall**: 搜索相关记忆，宪法层始终返回
2. **log**: 记录新记忆，按置信度分级
3. **governance**: 宪法层变更，需三次审批
```

---

## 9. 安全考虑

### 9.1 红线禁止
- ❌ AI 直接写入宪法层
- ❌ 绕过三次审批机制
- ❌ 在日志中记录便利贴内容
- ❌ 未经确认覆盖已有记忆

### 9.2 数据保护
- `.memos/` 目录受保护，不可手动修改
- 敏感信息（用药、过敏）仅宪法层存储
- 患者端 UI 不显示原始 ID

---

## 10. 下一步计划

### 10.1 短期（Step 3-4）
- [ ] 注册 Skill 到 Claude
- [ ] 集成 mcp-memory-service 作为可选后端

### 10.2 中期（Step 5）
- [ ] 实现 MemOSBackend
- [ ] 添加记忆迁移工具（Qdrant → MemOS）

### 10.3 长期
- [ ] 多患者支持
- [ ] 记忆同步（跨设备）
- [ ] 记忆可视化（时间线视图）

---

## 附录

### A. 文件清单

| 文件 | 说明 |
|------|------|
| `backend/services/memory_backend.py` | 抽象接口定义 |
| `backend/services/backends/qdrant_backend.py` | Qdrant 实现 |
| `backend/mcp_memory.py` | MCP Server |
| `docs/SKILL_SPEC.md` | 本文件 |
| `docs/MEMORY_STRATEGY.md` | 记忆策略文档 |

### B. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.1 | 2025-12-11 | 初稿，定义三层架构和行为 |
