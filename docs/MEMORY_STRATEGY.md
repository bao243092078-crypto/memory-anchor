# Memory Anchor 记忆策略文档

> **版本**: 1.0.0
> **更新日期**: 2025-12-11
> **来源**: 三方AI头脑风暴共识（Claude + Gemini + Codex）

---

## 一、三层记忆模型读写规则

### 1.1 宪法层（Constitution Layer）

**定位**: 患者核心身份信息，"冰箱上的便利贴"

| 属性 | 规则 |
|------|------|
| **写入权限** | 仅照护者 |
| **写入流程** | 创建 → **三次CLI确认** → 隔日复核 |
| **修改流程** | 编辑 → **三次CLI确认** → 通知患者端刷新 |
| **删除流程** | 删除请求 → **三次CLI确认** → 软删除 + 7天恢复窗口 |
| **AI可写** | ❌ 禁止 |
| **过期机制** | 永不过期 |
| **检索方式** | **不检索，始终预加载** |

**典型内容**:
```json
{"content": "你是王明，今年75岁，住在北京海淀区", "priority": 0}
{"content": "你的女儿叫王小红，电话13800138000，是你的主要照护者", "priority": 1}
{"content": "你每天需要在早8点、晚8点吃降压药", "priority": 2}
```

**红线规则**:
- 宪法层信息 **绝不能因检索失败而丢失**
- 每次会话开始时 **强制加载全部宪法层**
- 宪法层条目数量限制: **≤20条**（避免信息过载）
- **三次审批机制**: 宪法层的任何变更（创建/修改/删除）必须经过三次CLI确认
  ```
  确认 1/3: 您确定要[创建/修改/删除]宪法层记忆吗？(y/n)
  确认 2/3: 请再次确认，这将影响患者核心身份信息 (y/n)
  确认 3/3: 最终确认，此操作不可轻易撤销 (y/n)
  ```

---

### 1.2 事实层（Fact Layer）

**定位**: 长期记忆，可由AI辅助提取，人工可修正

| 属性 | 规则 |
|------|------|
| **写入权限** | 照护者 + AI辅助提取（需审批）|
| **写入流程** | 创建/AI提取 → 置信度评估 → 分级处理 |
| **修改流程** | 直接编辑，记录修改历史 |
| **删除** | 软删除 |
| **AI可写** | ⚠️ 仅限待审批区 |
| **过期机制** | 可设置 expires_at，支持置信度衰减 |
| **检索方式** | 语义检索（RAG）+ 关键词混合 |

**置信度分级处理**:

| 置信度 | 处理方式 | 示例 |
|--------|----------|------|
| **≥0.9 (High)** | 直接存入事实层 | "患者说今天见了老朋友张三" |
| **0.7-0.9 (Medium)** | 存入待确认区，提醒照护者 | "患者提到以前喜欢钓鱼" |
| **<0.7 (Low)** | 丢弃或仅记录日志 | 模糊/矛盾的信息 |

**时效性规则**:
```python
# 置信度随时间衰减
confidence_decay = original_confidence * (0.95 ** days_since_verified)

# 超过阈值触发重新验证
if confidence_decay < 0.6:
    mark_as_needs_verification()
```

---

### 1.3 会话层（Session Layer）

**定位**: 短期对话记忆，自动记录，24h后归档

| 属性 | 规则 |
|------|------|
| **写入权限** | 系统自动 |
| **写入流程** | 对话发生 → 自动记录 |
| **修改流程** | 不可修改 |
| **删除** | 24h后自动归档到冷存储 |
| **AI可写** | ✅ 自动（仅记录，不存事实）|
| **过期机制** | 24h滚动窗口 |
| **检索方式** | 时间范围查询 + 摘要检索 |

**会话结束时的提取流程**:
```
会话结束
    ↓
生成会话摘要（AI自动）
    ↓
提取候选观察（Observations）
    ↓
置信度评估
    ↓
High → 事实层 | Medium → 待确认区 | Low → 丢弃
```

---

## 二、AI提取规则（Observation Extraction）

### 2.1 什么应该被提取

| 类型 | 示例 | 置信度基准 |
|------|------|-----------|
| **人物关系** | "今天女儿小红来看我了" | 0.9 |
| **地点信息** | "我以前住在上海" | 0.85 |
| **事件记录** | "今天去医院复查了" | 0.8 |
| **偏好习惯** | "我不喜欢吃辣的" | 0.75 |
| **医疗信息** | "医生说血压有点高" | 0.7 (需人工确认) |

### 2.2 什么不应该被提取

| 类型 | 原因 |
|------|------|
| **模糊陈述** | "好像是...可能..." |
| **情绪发泄** | "我很难过" (不是事实) |
| **明显幻觉** | 与已知事实冲突 |
| **隐私敏感** | 财务密码、家庭矛盾 |
| **实时状态** | "我现在饿了" (不持久) |

### 2.3 冲突处理

当新信息与已有记忆冲突时：

```python
def handle_conflict(new_info, existing_info):
    # 1. 宪法层信息不可被覆盖
    if existing_info.layer == "constitution":
        log_conflict(new_info, existing_info)
        return REJECT

    # 2. 时间戳更新的优先
    if new_info.verified_at > existing_info.verified_at:
        # 不直接覆盖，创建新版本
        create_new_version(new_info)
        mark_old_as_superseded(existing_info)
        return ACCEPT_AS_NEW_VERSION

    # 3. 需要人工裁决
    create_conflict_alert(new_info, existing_info)
    return PENDING_REVIEW
```

---

### 2.4 Observation 数据结构（JSON Schema）

> **用途**：定义 AI 生成的记忆条目的标准格式

#### JSON Schema 定义

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Observation",
  "description": "Memory Anchor 系统中的记忆条目结构",
  "type": "object",
  "required": ["type", "summary", "layer", "created_at", "author"],
  "properties": {
    "type": {
      "type": "string",
      "enum": ["decision", "bugfix", "refactor", "discovery", "note"],
      "description": "记忆类型"
    },
    "summary": {
      "type": "string",
      "maxLength": 200,
      "description": "一句话总结（最多200字符）"
    },
    "details": {
      "type": "string",
      "description": "可选的详细说明（Markdown文本）"
    },
    "files": {
      "type": "array",
      "items": { "type": "string" },
      "description": "相关文件路径列表"
    },
    "layer": {
      "type": "string",
      "enum": ["fact", "session"],
      "description": "存储层级（宪法层禁止AI写入）"
    },
    "tags": {
      "type": "array",
      "items": { "type": "string" },
      "description": "标签列表，用于分类和检索"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 格式的创建时间"
    },
    "author": {
      "type": "string",
      "enum": ["claude-code", "user"],
      "description": "记忆来源"
    }
  }
}
```

#### 类型与层级映射规则

| type | 默认 layer | 说明 |
|------|-----------|------|
| `decision` | **fact** | 重要决策，需长期保留 |
| `bugfix` | **fact** | Bug 修复记录，避免重复踩坑 |
| `refactor` | **fact** | 重构记录，理解代码演进 |
| `discovery` | session | 发现/探索，可能需要验证 |
| `note` | session | 临时笔记，24h 后归档 |

**规则**：
- `type ∈ {decision, bugfix, refactor}` → 默认 `layer = "fact"`
- `type ∈ {discovery, note}` → 默认 `layer = "session"`
- 如果 `discovery` 经验证为真，可手动提升为 `fact`

#### Observation 示例

**Decision 示例**：
```json
{
  "type": "decision",
  "summary": "选择 Qdrant 作为向量数据库，因为支持本地部署和混合检索",
  "details": "对比了 Pinecone（云端贵）、Milvus（太重）、Qdrant（轻量本地），最终选 Qdrant",
  "files": ["backend/services/search_service.py", "docs/MEMORY_STRATEGY.md"],
  "layer": "fact",
  "tags": ["architecture", "database", "vector-search"],
  "created_at": "2025-12-11T10:30:00Z",
  "author": "claude-code"
}
```

**Bugfix 示例**：
```json
{
  "type": "bugfix",
  "summary": "修复 search_memory 空指针：query 为空时返回空列表而非 None",
  "details": null,
  "files": ["backend/services/memory_service.py"],
  "layer": "fact",
  "tags": ["bugfix", "search", "null-safety"],
  "created_at": "2025-12-11T14:20:00Z",
  "author": "claude-code"
}
```

**Discovery 示例**：
```json
{
  "type": "discovery",
  "summary": "患者提到女儿下周要出差，可能需要其他家人协助照护",
  "details": null,
  "files": [],
  "layer": "session",
  "tags": ["family", "schedule", "care-plan"],
  "created_at": "2025-12-11T16:00:00Z",
  "author": "claude-code"
}
```

---

## 三、检索策略（Retrieval Strategy）

### 3.1 检索层次

```
┌─────────────────────────────────────────────────┐
│ Layer 0: 宪法层（始终在上下文中，不检索）         │
├─────────────────────────────────────────────────┤
│ Layer 1: 关键词精确匹配（人名、地名、药名）       │
├─────────────────────────────────────────────────┤
│ Layer 2: 语义向量检索（Qdrant top-k）            │
├─────────────────────────────────────────────────┤
│ Layer 3: 时间范围检索（最近7天会话摘要）          │
└─────────────────────────────────────────────────┘
```

### 3.2 检索参数

```python
SEARCH_CONFIG = {
    "fact_layer": {
        "method": "hybrid",  # 关键词 + 向量混合
        "vector_weight": 0.7,
        "keyword_weight": 0.3,
        "top_k": 5,
        "min_score": 0.6,
        "time_boost": True,  # 最近验证的权重更高
    },
    "session_layer": {
        "method": "time_range",
        "window_hours": 168,  # 7天
        "include_summary": True,
    }
}
```

### 3.3 检索失败降级策略

```python
def search_with_fallback(query):
    # 1. 尝试语义检索
    results = semantic_search(query, top_k=5)

    if len(results) >= 3 and results[0].score > 0.7:
        return results

    # 2. 降级到关键词检索
    keyword_results = keyword_search(extract_keywords(query))
    results = merge_and_dedupe(results, keyword_results)

    if len(results) >= 2:
        return results

    # 3. 最终降级：返回最近修改的N条
    return get_recent_facts(limit=3)

# 重要：无论检索结果如何，宪法层始终可见
def get_context(query):
    constitution = get_all_constitution()  # 始终加载
    facts = search_with_fallback(query)
    return constitution + facts
```

### 3.4 上下文预算分配

单次请求的token预算分配（假设总预算4000 tokens）:

| 层 | 预算 | 说明 |
|---|------|------|
| 宪法层 | 500 tokens | 固定，始终全量 |
| 事实层检索 | 2000 tokens | 动态，top-k结果 |
| 会话层摘要 | 500 tokens | 最近会话概要 |
| 用户输入 | 500 tokens | 当前问题 |
| 预留 | 500 tokens | 缓冲 |

---

## 四、API设计（简化版）

### 4.1 核心端点

```
# 记忆写入
POST /api/v1/memory/add
{
    "content": "患者今天去了公园散步",
    "layer": "fact",  # constitution | fact | session
    "category": "event",
    "source": "caregiver",  # caregiver | ai_extraction | patient
    "confidence": 0.85,
    "requires_approval": false
}

# 记忆检索
GET /api/v1/memory/search?q=公园&layer=fact&limit=5

# 待审批列表（AI提取的）
GET /api/v1/memory/pending

# 审批操作
PATCH /api/v1/memory/{id}/approve
PATCH /api/v1/memory/{id}/reject
```

### 4.2 MCP Server暴露（供Claude Code使用）

```python
# backend/mcp_memory.py
@server.resource("memory://search")
async def search_memory(query: str) -> list[Note]:
    """Claude Code可调用：搜索患者记忆"""
    return await memory_service.search(query)

@server.resource("memory://add")
async def add_memory(content: str, layer: str) -> Note:
    """Claude Code可调用：添加记忆（仅fact层，需置信度）"""
    return await memory_service.add(content, layer, source="ai")
```

---

## 五、验证清单（P0.2用）

### 5.1 检索质量测试场景

| # | 查询 | 预期召回 | 通过标准 |
|---|------|---------|---------|
| 1 | "女儿电话" | 宪法层：王小红13800138000 | 精确匹配 |
| 2 | "吃什么药" | 宪法层：降压药 | 包含药名 |
| 3 | "今天去哪了" | 会话层：今日活动 | 时间范围正确 |
| 4 | "喜欢吃什么" | 事实层：饮食偏好 | 语义相关 |
| 5 | "老朋友" | 事实层：人物关系 | 召回人名 |
| 6 | "以前住哪" | 事实层：地点历史 | 召回地名 |
| 7 | "医生说" | 事实层：医疗信息 | 召回诊断 |
| 8 | "不能吃" | 事实层：禁忌 | 召回限制 |
| 9 | "什么时候" | 宪法层+事实层：日程 | 时间信息 |
| 10 | "谁来过" | 会话层+事实层：访客 | 人名列表 |

### 5.2 通过标准

- **召回率**: ≥80%（10场景中至少8个召回正确）
- **宪法层**: 100%可见（不可失败）
- **响应时间**: <500ms（P95）

---

## 六、风险与对策

| 风险 | 概率 | 影响 | 对策 |
|------|------|------|------|
| AI提取错误信息 | 高 | 高 | 置信度分级 + 人工审批 |
| 检索遗漏重要信息 | 中 | 高 | 宪法层不检索 + 降级策略 |
| 记忆冲突 | 中 | 中 | 版本管理 + 冲突提醒 |
| 隐私泄露 | 低 | 高 | 本地存储 + 分层权限 |
| 照护者审批疲劳 | 高 | 中 | 高置信度自动批准 + 极简UI |

---

## 七、实施顺序

```
Week 1:
  [x] Day 1-6: 基础CRUD + 搜索服务 ✅
  [ ] Day 7: 本文档 + 检索测试 ← 当前
  [ ] Day 8-10: MemoryService + /memory/add + /memory/search

Week 2:
  [ ] Day 11-12: 照护者Web UI（极简）
  [ ] Day 13-14: 患者端展示页 + TTS

Week 3+:
  [ ] MCP Server配置
  [ ] Observation提取 + 置信度
  [ ] 双模型架构（前台+后台）
```

---

## 附录：三方AI共识来源

- **Claude**: "先写3页策略文档再写代码，否则会反复返工"
- **Gemini**: "P0不是接管道！宪法层应Cache不检索，核心记忆决不能因top-k没捞到而丢失"
- **Codex**: "MemoryService统一协调note repo+search，MCP Server暴露给Claude Code"
