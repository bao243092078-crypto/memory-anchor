# Memory Anchor 🧠⚓

[![Version](https://img.shields.io/badge/version-1.0.0-blue)](https://github.com/bao243092078-crypto/memory-anchor)
[![Tests](https://img.shields.io/badge/tests-469%20passed-brightgreen)](https://github.com/bao243092078-crypto/memory-anchor)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-14%20tools-purple)](https://modelcontextprotocol.io/)
[![Status](https://img.shields.io/badge/status-complete-success)](https://github.com/bao243092078-crypto/memory-anchor)

> **为什么叫"阿默斯海默症"？**
>
> 这是一个**隐喻**：把 AI 当作阿尔茨海默症患者来看待——能力很强，但有"记忆缺陷"。
>
> **AI 不是真的患病，但它有类似的问题：**
>
> | AI 的"病症" | 表现 |
> |-------------|------|
> | 🧠 **上下文压缩失忆** | 聊到一半，压缩后忘了之前讨论的细节 |
> | 📋 **任务遗忘** | 做着做着忘了主要目标，丢三落四 |
> | 👻 **幻觉跑偏** | 自己编造任务，跑去做别的事情 |
>
> **Memory Anchor = AI 的外挂海马体**，解决这些"记忆缺陷"。

## 核心问题

使用 Claude Code、Cursor、Codex 等 AI 开发工具时，你是否遇到过：

1. **长对话压缩后，AI 忘了之前的关键决策**
2. **AI 做着做着跑偏了，忘记了主要任务**
3. **新会话开始，AI 对项目一无所知**
4. **AI 开始幻觉，编造不存在的任务或功能**

这些都是 AI 的"阿默斯海默症"症状。

## 解决方案

Memory Anchor 提供：

| 功能 | 解决的问题 |
|------|-----------|
| **身份图式层 (L0)** | 核心身份和目标，始终预加载，永不遗忘 |
| **清单革命** | 跨会话持久的任务清单，防止丢三落四 |
| **语义记忆 (L3)** | 重要决策和事实，可检索召回 |
| **事件日志 (L2)** | 带时间戳的操作记录，可追溯 |
| **三次审批机制** | 防止 AI 擅自修改关键信息 |

## 快速开始

### 安装

```bash
# 使用 uv（推荐）
uv add memory-anchor

# 或使用 pip
pip install memory-anchor
```

### 初始化项目

```bash
memory-anchor init --project my-project
```

### 配置 Claude Code

在 `~/.claude.json` 中添加：

```json
{
  "mcpServers": {
    "memory-anchor": {
      "command": "memory-anchor",
      "args": ["serve", "--project", "my-project"]
    }
  }
}
```

### 使用

```bash
# 启动 MCP Server（Claude Code 自动调用）
memory-anchor serve --project my-project

# 健康检查
memory-anchor doctor --project my-project

# 快捷命令（在仓库目录）
./ma up --project my-project
./ma doctor --project my-project
```

### 云端同步

```bash
# 初始化云端配置（S3/R2/MinIO）
./ma cloud init --provider s3 --bucket my-memories --region us-west-2

# 推送记忆到云端（自动加密）
./ma cloud push --project my-project

# 从云端拉取记忆
./ma cloud pull --project my-project --strategy lww

# 查看同步状态
./ma cloud status --project my-project
```

### 代码审查

```bash
# 多视角代码审查（Security/Performance/Quality/Memory Integrity）
./ma review --project my-project --paths backend/
```

### Memory Viewer (Web UI)

```bash
# 启动前端（需先启动后端）
cd frontend/viewer
npm install
npm run dev

# 访问 http://localhost:5173
```

**功能特性**:
- 🔍 **语义搜索** - 输入关键词搜索记忆
- 🏷️ **层级筛选** - 按 L0-L4 层级过滤
- 📂 **分类筛选** - 按人物/地点/事件/物品/习惯分类
- ✅ **快速验证** - 一键确认 AI 提取的记忆（提升置信度到 100%）
- 🗑️ **安全删除** - 需二次确认的删除操作
- 📋 **详情查看** - 完整信息 + JSON 原始数据
- ✏️ **内容编辑** - 在详情弹窗中直接修改记忆内容
- 🔗 **关联信息编辑** - 编辑 session_id 和 related_files
- 📊 **时间线可视化** - Recharts 堆叠面积图展示记忆分布
- 📅 **时间筛选器** - 支持 7天/30天/90天/全部时间范围 + 按天/周/月粒度切换

## 五层认知记忆模型

基于认知科学的 AI 记忆架构：

```
┌─────────────────────────────────────────────────────────────┐
│  L0: identity_schema (身份图式) ←── 始终预加载，三次审批    │
│  L1: active_context (工作记忆)  ←── 会话临时，不持久化      │
│  L2: event_log (事件日志)       ←── 时间戳记录，可设 TTL    │
│  L3: verified_fact (验证事实)   ←── 长期存储，语义检索      │
│  L4: operational_knowledge (操作知识) ←── .ai/operations/   │
└─────────────────────────────────────────────────────────────┘
```

| 层级 | 代码标识 | 解决的 AI 问题 |
|------|---------|---------------|
| 🔴 L0 | `identity_schema` | 防止 AI 忘记"我在做什么项目" |
| 🟡 L1 | `active_context` | 会话内的临时状态 |
| 🟢 L2 | `event_log` | 记录"刚才做了什么"，防止跑偏 |
| 🔵 L3 | `verified_fact` | 长期决策记忆，上下文压缩后可召回 |
| ⚪ L4 | `operational_knowledge` | "如何做"的操作手册 |

## MCP 工具（14 个）

### 核心工具

| 工具 | 说明 |
|------|------|
| `search_memory` | 语义搜索记忆（防止 AI 遗忘） |
| `add_memory` | 添加新记忆（任务完成后存档） |
| `get_constitution` | 获取身份图式（每会话自动加载） |
| `propose_constitution_change` | 提议修改核心信息（需三次审批） |
| `delete_memory` | 删除记忆（需确认短语） |
| `refine_memory` | LLM 精炼/压缩记忆（CoDA 上下文解耦） |

### 清单革命

| 工具 | 说明 |
|------|------|
| `create_checklist_item` | 创建持久化清单项（防止丢三落四） |
| `get_checklist_briefing` | 获取清单简报（会话开始时自动加载） |
| `sync_from_plan` | 从 Plan skill 同步完成状态 |

### 事件日志 (L2)

| 工具 | 说明 |
|------|------|
| `log_event` | 记录带时间戳的事件 |
| `search_events` | 按时间范围搜索 |
| `promote_to_fact` | 将事件提升为长期记忆 |

### 操作性知识 (L4)

| 工具 | 说明 |
|------|------|
| `search_operations` | 搜索 SOP/Workflow（遇到常见问题时自动触发） |

L4 工具会在以下场景**自动触发**：
- Qdrant 未运行 / 502 Bad Gateway
- 会话开始 / 恢复上下文
- 遇到已知问题（匹配 `.ai/operations/` 中的触发词）

## 使用场景

### 1. AI 开发项目记忆

```python
# 会话开始时，AI 自动加载项目上下文
constitution = get_constitution()
# → "这是 Memory Anchor 项目，使用 Python + FastAPI + Qdrant"

# 搜索之前的决策
memories = search_memory(query="为什么用 Qdrant")
# → "决定使用 Qdrant 是因为支持向量检索 + 本地部署"
```

### 2. 防止任务遗忘

```python
# 创建清单项，跨会话持久
create_checklist_item(
    content="实现五层认知记忆模型",
    priority="high",
    tags=["architecture", "v2.0"]
)

# 下次会话开始时自动获取
briefing = get_checklist_briefing()
# → "待办：实现五层认知记忆模型 [高优先级]"
```

### 3. 任务完成后存档

```python
# 完成重要工作后，写入记忆
add_memory(
    content="修复了 search_memory 空查询导致的空指针问题",
    layer="verified_fact",
    category="event",
    confidence=0.9
)
```

## 为什么需要 Memory Anchor？

### AI 的"记忆缺陷"本质

| 人类阿尔茨海默症 | AI 的类似问题 |
|-----------------|--------------|
| 短期记忆受损 | 上下文窗口有限（200K tokens） |
| 长期记忆模糊 | 无跨会话持久化 |
| 需要便利贴提醒 | 需要 Memory Anchor |
| 海马体退化 | 没有"海马体"（记忆存储器） |

### Memory Anchor 的作用

```
AI（无 Memory Anchor）          AI（有 Memory Anchor）
       │                               │
   ┌───┴───┐                       ┌───┴───┐
   │上下文满│                       │上下文满│
   │  压缩  │                       │  压缩  │
   └───┬───┘                       └───┬───┘
       │                               │
       ▼                               ▼
   ┌───────┐                       ┌───────┐
   │ 失忆  │                       │ 从 L0 │
   │ 跑偏  │                       │ 恢复  │
   │ 幻觉  │                       │ 上下文│
   └───────┘                       └───────┘
```

## 技术栈

- **后端**: Python 3.12 + FastAPI + Pydantic
- **前端**: React 18 + Vite + Tailwind CSS
- **向量数据库**: Qdrant（本地/远程）
- **嵌入模型**: FastEmbed (paraphrase-multilingual-MiniLM-L12-v2)
- **MCP**: Model Context Protocol
- **CLI**: Typer + Rich
- **云存储**: boto3（S3/R2/MinIO）
- **加密**: cryptography（AES-256-GCM）

## 开发

```bash
# 克隆仓库
git clone https://github.com/bao243092078-crypto/memory-anchor.git
cd memory-anchor

# 安装依赖
uv sync --all-extras

# 启动 Qdrant（推荐）
docker compose up -d qdrant
# 若目录名包含非 ASCII，建议显式设置项目名
docker compose -p memory-anchor up -d qdrant
# 若未使用 docker compose，也可：
docker run -d -p 6333:6333 --name qdrant qdrant/qdrant

# 就绪检查
curl http://localhost:6333/readyz
# 如果之前用过旧的 compose 配置，可强制重建
docker compose -p memory-anchor up -d --force-recreate qdrant

# 连接配置
export QDRANT_URL=http://localhost:6333

# 认证与 CORS（可选）
# 设置后 API 需要 X-API-Key 或 Bearer
export MA_API_KEY=your_api_key
# 逗号分隔允许来源
export MA_CORS_ALLOW_ORIGINS=http://localhost:5173

# 运行测试
uv run pytest

# 代码检查
uv run ruff check backend
```

## 更新记录

- 2025-12-27：时间线可视化（Recharts 堆叠面积图 + 时间筛选器/粒度切换）+ Memory Viewer Web UI 完整编辑功能（Phase 1-4：验证/删除 + 详情弹窗 + 内容编辑 + 关联信息编辑），修复 Cloud Sync 契约与 LWW 逻辑，统一 layer 类型（v2），收紧宪法层写入并加入 API Key/CORS，调整 Qdrant compose 并改用主机侧 readyz 验证。

## 路线图

### 已完成 ✅

**核心功能**
- [x] 五层认知记忆模型（L0-L4 完整）
- [x] MCP Server 集成（14 个工具）
- [x] CLI 工具（init/serve/doctor/review）
- [x] 身份图式三次审批机制 (L0)
- [x] 事件日志 (L2 Event Log)
- [x] 语义记忆 (L3 Verified Fact)
- [x] 操作性知识 (L4 search_operations)
- [x] 清单革命（ChecklistService）
- [x] 北极星对齐系统

**Hook 系统（Phase 1-8）**
- [x] Hook 框架统一（HookType + BaseHook + Registry）
- [x] 高风险操作 Gating Hook（删除需确认短语）
- [x] 状态文件结构化（StateManager + SessionState）
- [x] Stop Hook + 会话摘要生成
- [x] 阈值可配置（7 个 MA_* 环境变量）
- [x] PostToolUse + 测试建议（TestMappingService）
- [x] 测试篡改检测（5 种检测模式）
- [x] 多视角代码审查（`./ma review` 四视角并行）
- [x] checkpoint.py 上下文保护（PRE_COMPACT Hook）

**云端同步**
- [x] CloudStorageBackend Protocol（S3/R2/MinIO）
- [x] DataEncryptor（AES-256-GCM 加密）
- [x] MemoryExporter/Importer（JSONL 格式）
- [x] CLI 命令（`./ma cloud init/push/pull/status`）

**其他**
- [x] Memory Refiner（CoDA 上下文解耦，refine_memory 工具）
- [x] 全面类型安全（mypy strict, 经 GPT-5.2 xhigh 审核）

**Web UI (Memory Viewer)**
- [x] 记忆浏览器（搜索、筛选、查看）
- [x] 快速验证/删除功能（确认弹窗）
- [x] 记忆详情弹窗（完整信息 + JSON 查看）
- [x] 内容编辑功能（详情弹窗内联编辑）
- [x] 关联信息编辑（session_id + related_files）
- [x] 现代 SaaS 设计（黑白配色 + 亮绿强调色）
- [x] 时间线可视化（Recharts 堆叠面积图 + 时间筛选器）
- [x] 多项目隔离增强（ProjectSelector 组件）
- [x] 多语言支持（i18n 中英文切换，143 个翻译键）
- [x] 批量操作（多选删除/验证）

## 许可证

[MIT License](LICENSE)

---

## 致谢

这个项目的核心洞见：

**AI 的"阿默斯海默症"不是 bug，是 feature 的缺失。**

上下文窗口有限、无持久记忆、容易跑偏——这些是当前 AI 的固有限制。Memory Anchor 不是治愈 AI，而是给它一个**外挂的海马体**。

就像阿尔茨海默症患者用便利贴提醒自己重要的事，AI 用 Memory Anchor 记住关键决策、任务清单和项目上下文。

---

Made with ❤️ by [baobao](https://github.com/bao243092078-crypto)
