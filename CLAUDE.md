# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🎯 北极星 + 计划系统（强制）

**每次对话开始时，Hook 会自动注入：**
- `.ai/NORTH_STAR.md` - 项目初心（为什么做）
- `.ai/PLAN.md` - 当前计划（做什么）

**AI 必须遵守的规则：**

1. **接收新需求时** → 拆解成任务，更新 `.ai/PLAN.md` 的"正在做"
2. **完成任务后** → 在 PLAN.md 中打勾 `[x]`，移动到"已完成"
3. **发现新任务** → 添加到 PLAN.md
4. **做任何事之前** → 检查是否符合 NORTH_STAR.md 的"绝对不做"

**更新 PLAN.md 的命令格式：**
```bash
# AI 完成任务后执行
Edit .ai/PLAN.md: 把 "- [ ] 任务" 改成 "- [x] 任务"
```

---

## Project Overview

Memory Anchor is an MCP-based persistent memory system for AI assistants. Core metaphor: **treat AI as an Alzheimer's patient—capable but forgetful**. Memory Anchor is the AI's external hippocampus.

**Core principle**: Simplicity > Feature-rich, Proactive reminders > Passive recording

## Quick Reference

**Common Issues**:
- **MCP not connecting**: Check Qdrant Server is running (`curl http://127.0.0.1:6333/collections`)
- **Storage lock error**: Switch to Qdrant Server mode instead of local file mode
- **Tests failing**: Ensure `MEMORY_ANCHOR_COLLECTION=memory_anchor_test_notes` is set
- **Empty search results**: Check `MCP_MEMORY_PROJECT_ID` matches your project name

**Key Files**:
- `backend/config.py` - Configuration management (env → yaml → defaults)
- `backend/core/memory_kernel.py` - Core memory engine (sync, no async)
- `backend/services/search.py` - Qdrant integration with auto-detection
- `backend/mcp_memory.py` - MCP Server entry point

**Environment Variables**:
- `QDRANT_URL` - Qdrant Server URL (e.g., `http://localhost:6333`)
- `MCP_MEMORY_PROJECT_ID` - Project isolation (e.g., `阿默斯海默症`)
- `MEMORY_ANCHOR_COLLECTION` - Override collection name (testing only)

**Common Workflows**:

1. **Adding a new feature**:
   ```bash
   # 1. Write the test first (TDD)
   uv run pytest backend/tests/test_new_feature.py -x
   # 2. Implement the feature
   # 3. Run all tests
   uv run pytest
   # 4. Check types and lint
   uv run mypy backend && uv run ruff check backend --fix
   ```

2. **Debugging MCP issues**:
   ```bash
   # 1. Check Qdrant Server
   curl http://127.0.0.1:6333/collections
   # 2. Test search directly
   ./ma status --project 阿默斯海默症
   # 3. Check logs (MCP uses stderr)
   # 4. Verify environment variables
   echo $QDRANT_URL $MCP_MEMORY_PROJECT_ID
   ```

3. **Running integration tests**:
   ```bash
   # Start Qdrant Server first
   cd ~/.qdrant_storage && ~/bin/qdrant --config-path ./config/config.yaml &
   # Set test collection to avoid polluting main data
   export MEMORY_ANCHOR_COLLECTION=memory_anchor_test_notes
   # Run tests
   uv run pytest backend/tests/
   ```

---

## Development Commands

```bash
# Install dependencies
uv sync --all-extras

# Run development server (FastAPI HTTP)
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
uv run pytest                                    # All tests
uv run pytest backend/tests/test_search.py      # Single file
uv run pytest -k "test_memory_write"            # Pattern match
uv run pytest -x                                 # Stop on first failure
uv run pytest --cov=backend                      # With coverage

# Linting & formatting
uv run ruff check backend                        # Check
uv run ruff check backend --fix                  # Auto-fix
uv run ruff format backend                       # Format code

# Type checking
uv run mypy backend

# CLI entry points (prefer ./ma for shorter commands)
./ma doctor --project NAME                       # Health check
./ma init --project NAME                         # Initialize project
./ma up --project NAME                           # Start MCP service (stdio mode)
./ma serve --mode http --port 8000               # Start HTTP API server

# Start Qdrant Server (required for concurrent access)
cd ~/.qdrant_storage && ~/bin/qdrant --config-path ./config/config.yaml &

# Verify Qdrant is running
curl http://127.0.0.1:6333/collections
```

## Architecture

```
backend/
├── main.py                 # FastAPI HTTP entry point
├── mcp_memory.py           # MCP Server entry point (stdio)
├── config.py               # Configuration management (env → yaml → defaults)
├── core/
│   ├── memory_kernel.py    # Central memory engine (sync, no async)
│   └── active_context.py   # L1 working memory (in-process cache)
├── services/
│   ├── search.py           # Qdrant vector search (Server/Local modes)
│   ├── memory.py           # High-level memory service (async wrapper)
│   ├── constitution.py     # Constitution layer management
│   └── embedding.py        # FastEmbed text vectorization
├── models/
│   ├── note.py             # Memory layer enums, note schemas
│   └── constitution_change.py  # Change proposal models
├── api/                    # FastAPI routers
│   ├── notes.py            # CRUD for notes
│   ├── search.py           # Search endpoint
│   ├── memory.py           # Memory operations
│   └── constitution.py     # Constitution changes
├── cli/                    # Typer CLI commands
│   ├── doctor_cmd.py       # Health diagnostics
│   ├── init_cmd.py         # Project initialization
│   └── serve_cmd.py        # Server startup
└── tests/                  # pytest tests with singleton isolation
```

### Five-Layer Cognitive Memory Model (v2.0)

| Layer | Code | Cognitive Analog | Persistence |
|-------|------|------------------|-------------|
| **L0** | `identity_schema` | Self-concept | YAML + Qdrant, 3x approval |
| **L1** | `active_context` | Working memory | In-process only |
| **L2** | `event_log` | Episodic memory | Qdrant, TTL optional |
| **L3** | `verified_fact` | Semantic memory | Qdrant, permanent |
| **L4** | `operational_knowledge` | Procedural | .ai/operations/ files |

### Key Design Decisions

- **MemoryKernel** (`core/memory_kernel.py`): Sync-only Python, no async. All services wrap it for async contexts. Designed for Codex/script direct calls.
- **SearchService** (`services/search.py`): Auto-detects Qdrant Server vs Local mode. Server mode preferred for concurrent MCP access.
- **Configuration** (`config.py`): Priority: env vars → project yaml → global yaml → defaults. `MCP_MEMORY_PROJECT_ID` isolates collections.
- **Test isolation** (`tests/conftest.py`): Uses `MEMORY_ANCHOR_COLLECTION=memory_anchor_test_notes` and resets all singletons between tests.
- **Concurrent access**: Use Qdrant Server mode (not local file mode) when running MCP + HTTP simultaneously to avoid storage lock conflicts.

### Qdrant Modes

```bash
# Server mode (recommended for MCP)
QDRANT_URL=http://localhost:6333 uv run memory-anchor serve

# Local mode (fallback, single-process only)
# No QDRANT_URL set → uses .qdrant/ local storage
```

### Testing Strategy

- **Test isolation**: Uses `MEMORY_ANCHOR_COLLECTION=memory_anchor_test_notes` environment variable
- **Singleton reset**: `conftest.py` resets all singletons (`SearchService`, config) between tests
- **Qdrant mode**: Tests use local file mode by default, can override to Server mode
- **Fixtures**: Shared fixtures in `conftest.py` for client, search service, and test data
- **Coverage**: Run `pytest --cov=backend` to check test coverage

### Frontend Structure

```
frontend/caregiver/     # React 18 + Vite + Tailwind (记忆管理界面)
  ├── src/
  │   ├── api/          # HTTP client to backend
  │   ├── components/   # UI components
  │   ├── hooks/        # React hooks
  │   └── pages/        # Route pages
  └── package.json
```

---

## 🚨 标准开场流程（每次新会话强制执行）

> **这是固定指令块，Claude 必须在回答用户问题前先执行以下步骤**

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 读取用户输入                                        │
│     ↓                                                        │
│  Step 1: 用一句话总结用户需求 → query                         │
│     ↓                                                        │
│  Step 2: 调用 mcp__memory-anchor__search_memory(query)       │
│     ↓                                                        │
│  Step 3: 引用搜索结果，开始回答问题/写代码                     │
└─────────────────────────────────────────────────────────────┘
```

**示例执行**：
```
用户："上次我们为什么选择 Qdrant？"

Claude 内部执行：
1. query = "Qdrant 选型决策"
2. 调用 search_memory(query="Qdrant 选型决策")
3. 获取结果：[verified_fact] 决定使用 Qdrant 是因为支持向量检索 + 本地部署 + 并发访问
4. 回答用户："根据记忆，选择 Qdrant 是因为：支持向量检索、本地部署、并发访问"
```

**跳过条件**（仅以下情况可跳过 search_memory）：
- 用户明确说"不用查记忆"
- 已经在本会话中查过相同内容

---

## 🔴 硬约束：先查记忆再动手

> **核心规则**：如果当前任务不是"完全新东西"，就必须先 search_memory。

### 必须先查记忆的场景

| 场景 | 示例问题 | 为什么要查 |
|------|---------|-----------|
| **涉及项目历史** | "上次我们讨论的..." | 避免重复劳动 |
| **涉及设计决策** | "为什么用 Qdrant？" | 查出当初的理由 |
| **涉及 Bug/修复** | "之前那个空指针问题" | 查出修复细节 |
| **涉及上下文** | "继续上次的任务" | 恢复工作状态 |
| **不确定是否新东西** | 任何模糊的任务 | 宁可多查一次 |

### 不查记忆 = 不合规范

```
❌ 错误行为：
用户："上次我们修复的 search_memory Bug 是什么问题？"
Claude：（直接凭记忆回答，或说"我不记得"）

✅ 正确行为：
用户："上次我们修复的 search_memory Bug 是什么问题？"
Claude：
1. 调用 search_memory(query="search_memory Bug 修复")
2. 获取结果：[fact] 修复 search_memory 空查询时返回 None 导致空指针...
3. 引用结果回答用户
```

### 自检清单

在回答涉及"历史/决策/Bug/上下文"的问题前，Claude 应自问：
- [ ] 这个问题需要项目历史信息吗？→ 是 → 先 search_memory
- [ ] 这个问题涉及之前的决策吗？→ 是 → 先 search_memory
- [ ] 我不确定这是不是"新东西"？→ 是 → 先 search_memory

**违反后果**：用户可以直接说"你查记忆了吗？"，Claude 必须重新执行流程。

---

## 🟢 结束流程：写入 Observation（每轮任务完成时强制执行）

> **核心规则**：每当一轮任务完成（用户说"好了"、"完成了"、"可以了"，或 Claude 主动说"这一轮完成了"），必须执行以下流程。

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 复盘刚才发生了什么                                  │
│     ↓                                                        │
│  Step 2: 生成结构化 Observation                              │
│     ↓                                                        │
│  Step 3: 调用 add_memory 写入 memory-anchor                  │
│     ↓                                                        │
│  Step 4: 告知用户"已记录到记忆系统"                           │
└─────────────────────────────────────────────────────────────┘
```

### Observation JSON Schema

```json
{
  "type": "决策类型",
  "summary": "一句话描述发生了什么",
  "layer": "verified_fact | event_log",
  "category": "person | place | event | item | routine",
  "confidence": 0.95
}
```

### type 枚举及示例

| type | 说明 | 示例 |
|------|------|------|
| `decision` | 设计/架构决策 | "决定使用 Qdrant Server 模式解决并发锁问题" |
| `bugfix` | Bug 修复 | "修复了 search_memory 空查询返回 None 导致空指针" |
| `feature` | 新功能完成 | "完成了身份图式层三次审批机制" |
| `refactor` | 重构 | "将 SearchService 改为支持 Server/Local 双模式" |
| `discovery` | 发现/调研结论 | "发现 Qdrant 本地模式不支持并发访问" |
| `sprint` | Sprint/里程碑完成 | "Sprint 3 完成了身份图式层三次审批机制" |

### 示例执行

```
用户："好了，这个 Bug 修好了"

Claude 内部执行：
1. 复盘：刚才修复了 Qdrant 并发锁问题
2. 生成 Observation：
   {
     "type": "bugfix",
     "summary": "修复 Qdrant 并发锁：切换到 Server 模式，search.py 支持自动检测和降级",
     "layer": "verified_fact",
     "category": "event",
     "confidence": 0.95
   }
3. 调用 add_memory(content="修复 Qdrant 并发锁...", layer="verified_fact", category="event", confidence=0.95)
4. 回复用户："✅ 已完成，并记录到记忆系统。下次可以通过 search_memory 查询这次修复。"
```

### 必须写入 Observation 的场景

| 场景 | layer | category |
|------|-------|----------|
| 做了重要决策 | verified_fact | event |
| 修复了 Bug | verified_fact | event |
| 完成了新功能 | verified_fact | event |
| 完成了重构 | verified_fact | event |
| 发现了重要信息 | verified_fact | 按内容 |
| Sprint/里程碑完成 | verified_fact | event |
| 一轮对话结束（有实质进展） | event_log | event |

### 跳过条件

- 仅闲聊，无实质代码/决策变更
- 用户明确说"不用记录"

---

## Technology Stack

- **Backend**: Python 3.12 + FastAPI + Pydantic
- **Frontend**: React 18 + Vite + Tailwind CSS
- **Storage**: SQLite (constitution changes) + Qdrant (vector search)
- **Embeddings**: FastEmbed (all-MiniLM-L6-v2)
- **MCP**: Model Context Protocol for AI integration
- **CLI**: Typer + Rich for terminal UI

## 五层认知记忆模型（v2.0）

> **版本**: 2.0.0 | **更新**: 2025-12-15 | **详见**: `docs/MEMORY_STRATEGY.md`

| 层级 | 代码标识 | 认知对应 | 说明 |
|------|---------|---------|------|
| **L0** | `identity_schema` | 自我概念 | 核心身份（项目目标），仅用户可改，需三次审批 |
| **L1** | `active_context` | 工作记忆 | 会话临时状态，不持久化 |
| **L2** | `event_log` | 情景记忆 | 带时空标记的事件，可设 TTL |
| **L3** | `verified_fact` | 语义记忆 | 验证过的长期事实 |
| **L4** | `operational_knowledge` | 技能图式 | 操作性知识（.ai/operations/）|

### 向后兼容术语映射
| 旧术语 (v1.x) | 新术语 (v2.x) |
|--------------|--------------|
| `constitution` | `identity_schema` |
| `fact` | `verified_fact` |
| `session` | `event_log` + `active_context` |

## Development Conventions

- **Tests required**: Every PR must include tests
- **Privacy first**: Never log sensitive memory content
- **Developer-friendly**: Clear error messages with actionable guidance
- **No destructive defaults**: Never auto-delete data
- **Protected directories**: Don't manually edit `.memos/` or `.qdrant/`

## Code Organization Principles

- **Sync core, async wrappers**: `MemoryKernel` is pure sync Python. FastAPI routes and MCP handlers wrap it with async.
- **Dependency injection**: Services accept dependencies (e.g., `SearchService` injected into `MemoryKernel`) for testability.
- **Configuration cascade**: Environment variables override YAML, which overrides defaults. See `backend/config.py`.
- **Collection isolation**: Each project uses a separate Qdrant collection via `MCP_MEMORY_PROJECT_ID`.
- **Layer normalization**: Code uses v2.0 layer names (`identity_schema`, `verified_fact`, `event_log`), but accepts v1.x names for backward compatibility.

---

## 🎯 傻瓜 SOP（技术小白必读）

> **版本**: 2.0.0 | **更新**: 2025-12-15
> **核心原则**：把复杂留给系统，把简单留给用户

### 5 句话

1. **Memory Anchor 是 AI 的外挂记忆**——像便利贴帮你记住重要的事
2. **唯一命令入口是 `ma`**——不用管端口、进程、配置
3. **每天开始前运行 `ma doctor`**——确认系统健康
4. **看到红叉就运行 `ma fix`**——自动修复
5. **MCP 模式默认零端口**——不会和其他服务打架

### 3 个命令

```bash
# 1. 首次使用：初始化项目
./ma init --project 阿默斯海默症

# 2. 每日检查：自诊断（每天第一次用之前）
./ma doctor --project 阿默斯海默症

# 3. 出问题时：自动修复
./ma fix --project 阿默斯海默症
```

### 决策树（贴显示器）

```
              开始
                │
          运行 ma doctor
                │
        ┌───────┴───────┐
        ↓               ↓
     全绿 ✅          有红 ❌
        │               │
     直接用         运行 ma fix
                        │
                ┌───────┴───────┐
                ↓               ↓
           修复成功         修复失败
                │               │
             直接用         找开发者
```

### 其他常用命令

```bash
./ma up --project NAME      # 启动 MCP 服务
./ma status --project NAME  # 查看记忆状态
./ma --help                 # 查看完整帮助
```

---

## Memory Anchor MCP 使用 SOP（详细版）

> **重要**：本项目使用 `memory-anchor` 作为**唯一记忆源**，不要使用 claude-mem 或其他记忆插件。
> **傻瓜用户**：只需看上面的"傻瓜 SOP"即可，以下为 AI 开发者参考。

---

### Phase 1: 会话初始化（每次新会话必须执行）

```python
# Step 1: 加载宪法层（核心身份）
constitution = mcp__memory-anchor__get_constitution()
# 宪法层始终全量加载，不依赖检索

# Step 2: 根据当前任务生成 query
task_summary = "用一句话总结当前任务或用户问题"
query = generate_query(task_summary)

# Step 3: 搜索相关记忆
memories = mcp__memory-anchor__search_memory(
    query=query,
    layer="fact",  # 或 "session" 或省略搜全部
    limit=5
)

# Step 4: 构建上下文
context = {
    "constitution": constitution,  # 永远在最前面
    "relevant_facts": memories,
    "user_query": user_input
}
```

**触发条件**：
- 新会话开始
- 用户切换话题
- 用户明确说"重新加载记忆"

---

### Phase 2: 记忆写入（完成重要工作后）

```python
# 完成重要工作后，生成 observation
def generate_observation(work_result):
    return {
        "content": "用一句话描述发生了什么",
        "layer": "verified_fact",  # verified_fact | event_log（identity_schema禁止AI写入）
        "category": "event",  # person | place | event | item | routine
        "confidence": 0.85  # AI 提取时必填
    }

# 调用 add_memory
observation = generate_observation(work_result)
mcp__memory-anchor__add_memory(
    content=observation["content"],
    layer=observation["layer"],
    category=observation["category"],
    confidence=observation["confidence"]
)
```

**必须写入记忆的场景**：

| 场景 | layer | category | 示例 |
|------|-------|----------|------|
| 重要决策 | verified_fact | event | "决定使用 Qdrant 作为向量数据库" |
| Bug 修复 | verified_fact | event | "修复了 search_memory 的空指针问题" |
| 架构变更 | verified_fact | item | "升级到五层认知记忆模型" |
| 发现关键信息 | verified_fact | 按内容 | "发现 Qdrant 本地模式不支持并发访问" |
| 会话摘要 | event_log | - | "本次会话讨论了 MCP 集成方案" |

---

### Phase 2.5: 结束语 Prompt（任务完成时强制执行）

> **触发词**：当用户说以下话时，必须执行此流程：
> - "这一轮完成了" / "这个任务完成了"
> - "这个 Bug 修好了" / "搞定了"
> - "告一段落" / "先到这里"
> - "存一下进度"

**Claude 必须执行的三个步骤：**

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 用自己的话复述刚刚发生的关键事件                     │
│     "刚才我们做了：..."                                      │
│     ↓                                                        │
│  Step 2: 生成符合 Observation JSON 的候选记忆                 │
│     展示 JSON，让用户确认                                    │
│     ↓                                                        │
│  Step 3: 询问是否写入记忆                                    │
│     "是否要将这条记忆写入 memory-anchor？(y/n)"              │
│     ↓                                                        │
│  Step 4: 用户确认后，调用 add_memory                         │
└─────────────────────────────────────────────────────────────┘
```

**Observation JSON 模板**（参考 docs/MEMORY_STRATEGY.md）：

```json
{
  "type": "<decision|bugfix|refactor|discovery|note>",
  "summary": "<一句话总结，最多200字符>",
  "details": "<可选的详细说明>",
  "files": ["<涉及的文件路径>"],
  "layer": "<fact|session>",
  "tags": ["<标签1>", "<标签2>"],
  "created_at": "<ISO 8601>",
  "author": "claude-code"
}
```

**类型-层级映射规则**：
| type | 默认 layer | 何时使用 |
|------|-----------|---------|
| `decision` | verified_fact | 架构/技术决策 |
| `bugfix` | verified_fact | Bug 修复 |
| `refactor` | verified_fact | 重构记录 |
| `discovery` | event_log | 发现/探索（待验证） |
| `note` | event_log | 临时笔记 |

**示例对话**：

```
用户：这个 Bug 修好了

Claude：
📋 **刚才我们做了**：
修复了 `search_memory` 在 query 为空时返回 None 导致空指针的问题，
改为返回空列表 `[]`。

📝 **候选记忆**：
{
  "type": "bugfix",
  "summary": "修复 search_memory 空查询时返回 None 导致空指针，改为返回空列表",
  "details": null,
  "files": ["backend/services/memory.py"],
  "layer": "verified_fact",
  "tags": ["bugfix", "search", "null-safety"],
  "created_at": "2025-12-11T17:00:00Z",
  "author": "claude-code"
}

是否要将这条记忆写入 memory-anchor？(y/n)

用户：y

Claude：[调用 mcp__memory-anchor__add_memory]
✅ 记忆已写入（layer=verified_fact, confidence=0.9）
```

**注意**：
- 只有用户确认后才调用 `add_memory`
- `confidence` 默认 0.9（经用户确认的记忆）
- `decision/bugfix/refactor` 类型使用 `layer=fact`
- `discovery/note` 类型使用 `layer=session`

---

### Phase 3: 记忆引用（回答问题时）

```python
# 在回答用户问题或写代码时
def respond_with_memory(user_query, context):
    # 1. 优先引用宪法层（核心身份）
    if is_identity_question(user_query):
        return format_from_constitution(context["constitution"])

    # 2. 引用搜索结果
    if context["relevant_facts"]:
        return incorporate_memories(user_query, context["relevant_facts"])

    # 3. 无相关记忆时，明确告知
    return "我没有找到相关记忆，这可能是新内容"
```

---

### 四个 MCP 工具速查

| 工具 | 用途 | 何时调用 |
|------|------|---------|
| `get_constitution` | 获取项目核心身份 | 每会话开始、项目定位相关问题 |
| `search_memory` | 语义搜索记忆 | 需要历史信息时 |
| `add_memory` | 添加新记忆 | 完成重要工作后 |
| `propose_constitution_change` | 提议修改宪法层 | 需要修改核心身份时（需三次审批） |

### 置信度分级处理

| 置信度 | 处理方式 | 说明 |
|--------|----------|------|
| **≥ 0.9** | 直接存入事实层 | 高置信度，无需人工审批 |
| **0.7-0.9** | 存入待审批区 | 需用户确认 |
| **< 0.7** | 拒绝存入 | 信息太模糊，丢弃 |

### 红线禁止

- **禁止** AI 直接写入宪法层（必须通过 `propose_constitution_change`）
- **禁止** 绕过三次审批机制修改宪法层
- **禁止** 在日志中记录便利贴内容
- **禁止** 未经确认覆盖已有记忆
- **禁止** 使用 claude-mem 或其他记忆插件（本项目仅用 memory-anchor）

---

### 宪法层修改流程（三次审批）

> **强制规则**：宪法层的任何修改，必须通过 `propose_constitution_change`，不得直接编辑。

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Claude 调用 propose_constitution_change            │
│     ↓                                                        │
│  Step 2: 创建 pending 状态的变更提议                         │
│     ↓                                                        │
│  Step 3: 用户审批（调用 3 次 /approve/{id}）                 │
│     ↓                                                        │
│  Step 4: approvals_count >= 3 时，自动应用变更               │
└─────────────────────────────────────────────────────────────┘
```

**调用示例**：
```python
# 提议新增宪法条目（项目核心目标）
mcp__memory-anchor__propose_constitution_change(
    change_type="create",
    proposed_content="项目目标：为 AI 提供跨会话持久化记忆系统",
    reason="明确项目定位",
    category="item"
)

# 提议修改现有条目
mcp__memory-anchor__propose_constitution_change(
    change_type="update",
    proposed_content="项目目标：为 AI 提供五层认知记忆系统",
    reason="架构升级到五层模型",
    target_id="原条目的UUID",
    category="item"
)
```

**审批 API**：
```bash
# 用户审批（每次调用 +1，需要 3 次）
POST /api/v1/constitution/approve/{change_id}

# 查看待审批列表
GET /api/v1/constitution/pending
```

---

## 记忆同步规则（自动继承）

> 本项目遵循全局记忆同步规则，详见 `~/.claude/rules/13-memory-sync.md`

### 快速参考

- **Qdrant** 是记忆单一真相源
- **`.memos/`** 是人类可读备份
- 任务完成后调用 `add_memory` 写入
- 会话开始时调用 `search_memory` 加载上下文

### 记忆块规范

在本文件中使用结构化记忆块：

```memory-anchor
id: unique-id
type: decision | bugfix | refactor | discovery | note
summary: 一句话总结
layer: fact | session
tags: [tag1, tag2]
```
