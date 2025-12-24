# Memory Anchor 记忆策略文档

> **版本**: 2.0.0
> **更新日期**: 2025-12-15
> **来源**: 三方AI头脑风暴共识（Claude Opus + Gemini + Codex）+ 认知科学视角
> **重大变更**: 从三层模型升级为五层认知记忆模型

---

## 核心理念

**把 AI 当作阿尔茨海默症患者**——能力很强，但容易因上下文压缩而"失忆"。

| 阿尔茨海默症患者 | AI（Claude/Codex/Gemini） |
|-----------------|--------------------------|
| 短期记忆受损 | 上下文窗口有限（200K tokens）|
| 长期记忆模糊 | 没有跨会话的持久化记忆 |
| 需要便利贴提醒 | 需要 Memory Anchor |
| 海马体功能退化 | 没有"海马体"（记忆存储器）|

**Memory Anchor = AI 的外挂海马体**

---

## 一、五层认知记忆模型

### 1.0 层级总览

| 层级 | 代码标识 | 存储 | 生命周期 | 认知对应 |
|------|---------|------|---------|---------|
| **L0** | `identity_schema` | YAML + Qdrant | 永久 | 自我概念（Self-concept） |
| **L1** | `active_context` | TTLCache | 会话期间 | 工作记忆（Working Memory） |
| **L2** | `event_log` | Qdrant | 可配置 TTL | 情景记忆（Episodic Memory） |
| **L3** | `verified_fact` | Qdrant | 永久 | 语义记忆（Semantic Memory） |
| **L4** | `operational_knowledge` | .ai/operations/ | Git 版本控制 | 技能图式（Skill Schema） |

### 1.1 术语映射（向后兼容）

| 旧术语 (v1.x) | 新术语 (v2.x) | 说明 |
|--------------|--------------|------|
| `constitution` | `identity_schema` | 核心身份图式 |
| `fact` | `verified_fact` | 验证过的事实 |
| `session` | 拆分为 L1 + L2 | 区分即时状态和事件记录 |
| - | `active_context` | 新增：会话期间的临时状态 |
| - | `event_log` | 新增：带时空标记的事件 |
| - | `operational_knowledge` | 新增：操作性知识 |

---

## 二、各层详细规则

### L0: Identity Schema（身份图式）

> **认知科学对应**：自我概念（Self-concept）——关于"我是谁"的核心信念

**定位**: 项目的核心身份，"冰箱上的便利贴"

| 属性 | 规则 |
|------|------|
| **写入权限** | 仅用户（人类） |
| **写入流程** | 创建 → **三次审批** → 生效 |
| **AI可写** | 禁止（必须通过 `propose_constitution_change`） |
| **过期机制** | 永不过期 |
| **检索方式** | **不检索，始终预加载** |
| **存储来源** | YAML 优先 + Qdrant 动态补充 |

**典型内容**:
```json
{"content": "项目目标：为 AI 提供跨会话持久化记忆系统", "priority": 0}
{"content": "技术栈：Python + FastAPI + Qdrant + MCP", "priority": 1}
{"content": "核心约束：简洁 > 功能丰富，主动提醒 > 被动记录", "priority": 2}
```

**红线规则**:
- 身份信息 **绝不能因检索失败而丢失**
- 每次会话开始时 **强制全量加载**
- 条目数量限制: **≤20条**（避免信息过载）
- **三次审批机制**: 任何变更必须经过三次确认

---

### L1: Active Context（活跃上下文）

> **认知科学对应**：工作记忆（Working Memory）——即时操作的注意力焦点

**定位**: 当前会话的临时状态，会话结束自动清除

| 属性 | 规则 |
|------|------|
| **写入权限** | 系统自动 + AI |
| **存储** | 进程内 TTLCache（不持久化） |
| **过期机制** | 会话结束即清除，或 TTL 1小时 |
| **持久化** | 不写入 Qdrant |

**典型内容**:
```python
# 当前对话的临时变量
active_context.set("current_topic", "优化 search_memory 性能")
active_context.set("task_status", "debugging")
active_context.set("pending_questions", ["是否需要添加缓存？", "索引策略是什么？"])
```

**与 L2 Event Log 的区别**:
- Active Context: "我现在在想什么"（即时，不保存）
- Event Log: "刚才发生了什么"（事件，可保存）

---

### L2: Event Log（事件日志）

> **认知科学对应**：情景记忆（Episodic Memory）——带时空标记的个人经历

**定位**: 记录"发生了什么"，带有 when/where/who 元数据

| 属性 | 规则 |
|------|------|
| **写入权限** | 系统自动 + AI + 用户 |
| **存储** | Qdrant（layer=event_log） |
| **过期机制** | 可配置 TTL（7天/30天/永久） |
| **检索方式** | 时间范围 + 语义检索 |

**数据结构**:
```python
class EventLog:
    id: UUID
    content: str          # 事件描述
    when: datetime        # 何时（必填）
    where: Optional[str]  # 何地
    who: List[str]        # 涉及谁
    source: str           # ai | user | system
    ttl_days: Optional[int]  # 保留天数，None=永久
```

**典型内容**:
```json
{
  "content": "修复了 search_memory 空查询返回 None 的 Bug",
  "when": "2025-12-15T14:30:00Z",
  "where": "backend/services/memory.py",
  "who": ["claude-code"],
  "ttl_days": 30
}
```

**提升规则**:
- Event Log 经过验证后可**提升为 Verified Fact**
- 提升后 `promote_to_fact = true`，原事件保留作为来源追溯

---

### L3: Verified Fact（验证事实）

> **认知科学对应**：语义记忆（Semantic Memory）——去情境化的事实和概念

**定位**: 长期记忆，经过验证的持久事实

| 属性 | 规则 |
|------|------|
| **写入权限** | 用户 + AI（需置信度评估） |
| **存储** | Qdrant（layer=verified_fact） |
| **过期机制** | 永久，支持置信度衰减 |
| **检索方式** | 语义向量检索 + 关键词混合 |

**置信度分级处理**:

| 置信度 | 处理方式 | 示例 |
|--------|----------|------|
| **≥0.9** | 直接存入 | "用户确认使用 Qdrant 作为向量数据库" |
| **0.7-0.9** | 待审批区 | "AI 推断项目需要缓存优化" |
| **<0.7** | 拒绝存储 | 模糊/矛盾的信息 |

**与 L2 Event Log 的区别**:
- Event Log: "2025-12-15 修复了空指针 Bug"（具体事件）
- Verified Fact: "空查询应返回空列表而非 None"（泛化的规则）

---

### L4: Operational Knowledge（操作性知识）

> **认知科学对应**：技能图式（Skill Schema）——显性的"如何做"知识
> **注意**：这**不是**程序性记忆（Procedural Memory），因为 AI 的技能是显性的、声明式的

**定位**: 任务模板、工作流、规则——AI "如何做事"的知识

| 属性 | 规则 |
|------|------|
| **写入权限** | 开发者 |
| **存储** | `.ai/operations/` 目录（Markdown/YAML） |
| **版本控制** | Git |
| **检索方式** | 文件名匹配 + RAG |

**目录结构**:
```
.ai/operations/
├── README.md                # 索引
├── memory_sop.md           # 记忆操作 SOP
├── constitution_approval.md # 身份层审批流程
├── error_handling.md       # 错误处理规则
└── templates/
    └── observation.json    # Observation 模板
```

**与 CLAUDE.md 的关系**:
- CLAUDE.md: 项目整体规则（what）
- Operational Knowledge: 具体操作步骤（how）

---

## 三、层间流动规则

### 3.1 记忆提升路径

```
L1 Active Context → [会话结束] → L2 Event Log
                                      ↓
                               [验证 + 泛化]
                                      ↓
                               L3 Verified Fact
                                      ↓
                              [用户审批 ×3]
                                      ↓
                               L0 Identity Schema
```

### 3.2 反向流动（检索加载）

```
L0 Identity Schema → [始终预加载] → 上下文
L3 Verified Fact   → [语义检索]   → 上下文
L2 Event Log       → [时间范围]   → 上下文
L4 Operational     → [任务匹配]   → 上下文
```

### 3.3 提升 API

```python
# Event Log → Verified Fact
promote_event_to_fact(event_id: UUID, confidence: float = 0.9)

# Verified Fact → Identity Schema（需三次审批）
propose_constitution_change(content: str, reason: str)
```

---

## 四、Observation 数据结构

### 4.1 JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Observation",
  "type": "object",
  "required": ["type", "summary", "layer", "created_at", "author"],
  "properties": {
    "type": {
      "type": "string",
      "enum": ["decision", "bugfix", "refactor", "discovery", "note", "event"]
    },
    "summary": {
      "type": "string",
      "maxLength": 200
    },
    "details": { "type": "string" },
    "files": { "type": "array", "items": { "type": "string" } },
    "layer": {
      "type": "string",
      "enum": ["identity_schema", "event_log", "verified_fact"]
    },
    "when": { "type": "string", "format": "date-time" },
    "where": { "type": "string" },
    "who": { "type": "array", "items": { "type": "string" } },
    "tags": { "type": "array", "items": { "type": "string" } },
    "created_at": { "type": "string", "format": "date-time" },
    "author": { "type": "string" }
  }
}
```

### 4.2 类型与层级映射

| type | 默认 layer | 说明 |
|------|-----------|------|
| `decision` | verified_fact | 重要决策 |
| `bugfix` | verified_fact | Bug 修复记录 |
| `refactor` | verified_fact | 重构记录 |
| `event` | event_log | 带时空标记的事件 |
| `discovery` | event_log | 发现/探索 |
| `note` | event_log | 临时笔记 |

---

## 五、检索策略

### 5.1 检索层次

```
┌─────────────────────────────────────────────────┐
│ L0: Identity Schema（始终预加载，不检索）         │
├─────────────────────────────────────────────────┤
│ L1: Active Context（进程内查询，不检索 Qdrant）   │
├─────────────────────────────────────────────────┤
│ L2: Event Log（时间范围 + 语义检索）              │
├─────────────────────────────────────────────────┤
│ L3: Verified Fact（语义检索 + 关键词混合）        │
├─────────────────────────────────────────────────┤
│ L4: Operational Knowledge（文件匹配 + RAG）       │
└─────────────────────────────────────────────────┘
```

### 5.2 上下文预算分配

| 层 | 预算 | 说明 |
|---|------|------|
| L0 Identity Schema | 500 tokens | 固定，始终全量 |
| L2 Event Log | 500 tokens | 最近事件 |
| L3 Verified Fact | 2000 tokens | 语义检索 top-k |
| 用户输入 | 500 tokens | 当前问题 |
| 预留 | 500 tokens | 缓冲 |

---

## 六、MCP 工具清单

### 6.1 现有工具（v1.x）

| 工具 | 功能 |
|------|------|
| `get_constitution` | 获取 L0 身份图式 |
| `search_memory` | 搜索 L2/L3 |
| `add_memory` | 添加到 L2/L3 |
| `propose_constitution_change` | 提议修改 L0 |

### 6.2 新增工具（v2.x）

| 工具 | 功能 |
|------|------|
| `log_event` | 记录事件到 L2（带 when/where/who） |
| `search_events` | 按时间范围搜索 L2 |
| `promote_to_fact` | L2 → L3 提升 |
| `get_active_context` | 获取 L1 当前状态 |
| `set_active_context` | 设置 L1 临时变量 |

---

## 七、验证清单

### 7.1 检索质量测试

| # | 查询 | 预期层级 | 预期召回 |
|---|------|---------|---------|
| 1 | "项目目标" | L0 | 为 AI 提供跨会话持久化记忆 |
| 2 | "技术栈" | L0 | Python + FastAPI + Qdrant |
| 3 | "今天修复了什么" | L2 | 今日 Bug 修复事件 |
| 4 | "为什么用 Qdrant" | L3 | 技术选型决策 |
| 5 | "上周完成了什么" | L2 | 开发事件列表 |

### 7.2 通过标准

- **L0 召回率**: 100%（身份信息不可失败）
- **L2/L3 召回率**: ≥80%
- **响应时间**: <500ms（P95）

---

## 八、风险与对策

| 风险 | 对策 |
|------|------|
| 术语混乱（旧新并存） | 保留向后兼容别名 |
| Active Context 重启丢失 | 预期行为，不需要持久化 |
| Event Log 无限增长 | TTL 自动清理 + 归档 |
| 层级边界模糊 | 严格的 type→layer 映射 |

---

## 附录：认知科学参考

### A.1 人类记忆系统

| 记忆类型 | 特征 | Memory Anchor 对应 |
|---------|------|-------------------|
| 工作记忆 | 容量有限，秒级 | L1 Active Context |
| 情景记忆 | 时空标记的经历 | L2 Event Log |
| 语义记忆 | 去情境化的事实 | L3 Verified Fact |
| 程序性记忆 | 隐性的技能 | **不适用**（AI 技能是显性的）|

### A.2 为什么不叫"Procedural Memory"

人类的程序性记忆是**隐性的**（你不能"说出"怎么骑自行车）。
AI 的"技能"是**显性的**（CLAUDE.md 里写得清清楚楚）。

因此我们使用 **Operational Knowledge**（操作性知识）而非 Procedural Memory。

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2025-12-11 | 初版三层模型 |
| 2.0.0 | 2025-12-15 | 升级为五层认知记忆模型 |
