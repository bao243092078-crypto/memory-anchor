<div align="center">

# Memory Anchor 🧠⚓

### AI 的外挂海马体 | The External Hippocampus for AI

[![Version](https://img.shields.io/badge/version-3.0.0-blue?style=for-the-badge)](https://github.com/bao243092078-crypto/memory-anchor/releases)
[![Tests](https://img.shields.io/badge/tests-621%20passed-success?style=for-the-badge)](https://github.com/bao243092078-crypto/memory-anchor)
[![Python](https://img.shields.io/badge/python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-14%20tools-8B5CF6?style=for-the-badge)](https://modelcontextprotocol.io/)
[![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)](LICENSE)

**解决 AI 的"阿尔茨海默症"：上下文压缩失忆、任务遗忘、幻觉跑偏**

[快速开始](#-快速开始) · [功能特性](#-功能特性) · [架构设计](#-架构设计) · [Web UI](#-web-ui) · [文档](docs/)

</div>

---

## 🤔 为什么需要 Memory Anchor？

> **核心隐喻**：把 AI 当作阿尔茨海默症患者——能力很强，但有"记忆缺陷"。

使用 Claude Code、Cursor、Codex 等 AI 工具时，你是否遇到过：

| 症状 | 表现 | Memory Anchor 解决方案 |
|------|------|----------------------|
| 🧠 **上下文压缩失忆** | 聊到一半，压缩后忘了关键决策 | L0 身份图式始终预加载 |
| 📋 **任务遗忘** | 做着做着忘了主要目标 | 清单革命 + 跨会话持久 |
| 👻 **幻觉跑偏** | 自己编造任务，跑去做别的 | 北极星对齐 + 偏离检测 |
| 🔄 **新会话失忆** | 每次开始都要重新解释项目 | 自动加载项目上下文 |

---

## 🚀 快速开始

### 安装

```bash
# 使用 uv（推荐）
uv add memory-anchor

# 或 pip
pip install memory-anchor
```

### 初始化 & 启动

```bash
# 1. 初始化项目
./ma init --project my-project

# 2. 健康检查
./ma doctor --project my-project

# 3. 配置 Claude Code（添加到 ~/.claude.json）
```

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

### Qdrant（一次性固定，避免数据“丢失”）

- Qdrant 存储固定在 `~/.qdrant_storage`（Docker 默认挂载），数据不随项目移动
- 只用 Docker 或只用本地 Qdrant，不要混用（避免两个实例读写同一份存储）
- Server 模式请设置：`QDRANT_URL=http://127.0.0.1:6333`
- 路径含非 ASCII 时，使用 `-p memory-anchor` 或设置 `COMPOSE_PROJECT_NAME=memory-anchor`
- 建议固定 `QDRANT_URL` 与 `MCP_MEMORY_PROJECT_ID`，避免写入/查询错项目

```bash
docker compose -p memory-anchor up -d qdrant
export QDRANT_URL=http://127.0.0.1:6333
curl http://127.0.0.1:6333/readyz
```

### 云端同步（可选）

```bash
# 初始化 S3/R2/MinIO
./ma cloud init --provider s3 --bucket my-memories

# 推送（AES-256-GCM 加密）
./ma cloud push --project my-project

# 拉取
./ma cloud pull --project my-project
```

---

## 🏗️ 架构设计

### 五层认知记忆模型

基于认知科学设计，模拟人类记忆系统：

```
┌────────────────────────────────────────────────────────────────┐
│  L0  identity_schema   身份图式   ▓▓▓▓▓  始终预加载 · 三次审批  │
├────────────────────────────────────────────────────────────────┤
│  L1  active_context    工作记忆   ░░░░░  会话临时 · 不持久化    │
├────────────────────────────────────────────────────────────────┤
│  L2  event_log         事件日志   ▓▓▓░░  时间戳 · 可设 TTL     │
├────────────────────────────────────────────────────────────────┤
│  L3  verified_fact     验证事实   ▓▓▓▓░  长期存储 · 语义检索   │
├────────────────────────────────────────────────────────────────┤
│  L4  operational_knowledge 操作知识 ▓▓░░░  SOP · 自动触发      │
└────────────────────────────────────────────────────────────────┘
```

### MCP 工具集（14 个）

<table>
<tr>
<td width="50%">

**核心记忆**
| 工具 | 说明 |
|------|------|
| `search_memory` | 语义搜索 |
| `add_memory` | 添加记忆 |
| `get_constitution` | 获取身份 |
| `delete_memory` | 删除（需确认）|
| `refine_memory` | LLM 压缩 |

</td>
<td width="50%">

**清单革命**
| 工具 | 说明 |
|------|------|
| `create_checklist_item` | 创建清单 |
| `get_checklist_briefing` | 获取简报 |
| `sync_from_plan` | 同步状态 |

</td>
</tr>
<tr>
<td>

**事件日志 (L2)**
| 工具 | 说明 |
|------|------|
| `log_event` | 记录事件 |
| `search_events` | 时间搜索 |
| `promote_to_fact` | 提升为 L3 |

</td>
<td>

**操作知识 (L4)**
| 工具 | 说明 |
|------|------|
| `search_operations` | 搜索 SOP |
| `propose_constitution_change` | 修改身份 |

</td>
</tr>
</table>

---

## ✨ 功能特性

### v3.0 认知增强（新）

| 功能 | 说明 | CLI 命令 |
|------|------|----------|
| **ContextBudgetManager** | Token 预算管理，防止上下文爆炸 | `./ma budget` |
| **SafetyFilter** | PII 检测 + 敏感词过滤 | 自动启用 |
| **Bi-temporal 时间感知** | `valid_at`/`expires_at` 时间维度查询 | MCP: `as_of` 参数 |
| **ConflictDetector** | 规则引擎冲突检测（时间/来源/置信度） | `./ma conflicts` |

```python
# Bi-temporal 查询示例
search_memory(query="患者用药", as_of="2025-01-01T00:00:00Z")

# 冲突检测自动返回警告
add_memory("新记忆") → {"conflict_warning": {...}}
```

### Hook 系统（8 个 Phase）

```
SessionStart ──► PreToolUse ──► PostToolUse ──► PreCompact ──► Stop
     │               │              │               │           │
     ▼               ▼              ▼               ▼           ▼
  加载上下文     Gating检测     测试建议      Checkpoint    会话摘要
```

| Phase | 功能 | 说明 |
|-------|------|------|
| 1 | Hook 框架 | HookType + BaseHook + Registry |
| 2 | 状态管理 | StateManager + SessionState |
| 3 | 会话摘要 | Stop Hook 自动生成 |
| 4 | 阈值配置 | 7 个 MA_* 环境变量 |
| 5 | 测试建议 | PostToolUse + TestMapping |
| 6 | 篡改检测 | 5 种测试修改模式 |
| 7 | 代码审查 | `./ma review` 四视角并行 |
| 8 | 上下文保护 | PRE_COMPACT checkpoint |

### 云端同步

```
┌─────────────┐    AES-256-GCM    ┌─────────────┐
│  Local      │ ◄──────────────► │  S3/R2/MinIO │
│  Qdrant     │    JSONL Export   │  Encrypted   │
└─────────────┘                   └─────────────┘
```

- **加密**: AES-256-GCM（零知识）
- **格式**: JSONL（可读、可 diff）
- **策略**: LWW（Last Write Wins）

---

## 🖥️ Web UI

现代 SaaS 风格的记忆管理界面：

### 功能

| 功能 | 说明 |
|------|------|
| 🔍 **语义搜索** | 向量相似度检索 |
| 🏷️ **层级筛选** | L0-L4 过滤 |
| 📂 **分类筛选** | 人物/地点/事件/物品/习惯 |
| ✅ **批量操作** | 多选删除/验证 |
| 📊 **时间线** | Recharts 堆叠面积图 |
| 🕸️ **记忆图谱** | D3.js 力导向图（节点点击/缩放/筛选）|
| 🌐 **多语言** | 中英文切换（160+ keys）|
| 📁 **多项目** | ProjectSelector 隔离 |

### 启动

```bash
cd frontend/viewer
npm install && npm run dev
# → http://localhost:5173
```

---

## 📊 技术栈

<table>
<tr>
<td width="50%">

**后端**
- Python 3.12 + FastAPI
- Qdrant（向量数据库）
- FastEmbed（嵌入模型）
- Typer + Rich（CLI）

</td>
<td width="50%">

**前端**
- React 18 + TypeScript
- Vite + Tailwind CSS
- D3.js（记忆图谱）
- Recharts（时间线）
- i18next（国际化）

</td>
</tr>
</table>

---

## 📖 文档

| 文档 | 说明 |
|------|------|
| [CLAUDE.md](CLAUDE.md) | AI 开发指南 |
| [docs/MEMORY_STRATEGY.md](docs/MEMORY_STRATEGY.md) | 记忆策略详解 |
| [.ai/NORTH_STAR.md](.ai/NORTH_STAR.md) | 项目北极星 |
| [.ai/PLAN.md](.ai/PLAN.md) | 当前计划 |

---

## 🗺️ 路线图

### v2.1.0 ✅ 最新

- [x] 记忆图谱可视化（D3.js 力导向图）
- [x] 节点交互：点击详情、缩放、拖拽、平移
- [x] 图谱筛选：按层级/分类过滤
- [x] Graph API：`/api/v1/graph` 端点
- [x] 15 个新测试，498 个测试全部通过

### v2.0.1 ✅

- [x] 测试隔离修复：SearchService `path` 优先于 `url`
- [x] 修复 8 个测试文件的隔离问题
- [x] 483 个测试全部通过

### v2.0.0 ✅

- [x] 五层认知记忆模型（L0-L4）
- [x] 14 个 MCP 工具
- [x] Hook 系统（8 个 Phase）
- [x] 云端同步（S3/R2/MinIO + AES-256-GCM）
- [x] Web UI（搜索/筛选/时间线/批量/i18n）
- [x] 469 个测试通过

### 未来方向 🔮

- [ ] VSCode / Cursor 插件
- [ ] 团队协作（多用户）
- [ ] 移动端 PWA

---

## 🤝 贡献

```bash
# 克隆
git clone https://github.com/bao243092078-crypto/memory-anchor.git

# 安装
uv sync --all-extras

# 测试
uv run pytest

# 代码检查
uv run ruff check backend && uv run mypy backend
```

---

## 📜 许可证

[MIT License](LICENSE)

---

<div align="center">

### 💡 核心洞见

**AI 的"阿尔茨海默症"不是 bug，是 feature 的缺失。**

Memory Anchor 不是治愈 AI，而是给它一个**外挂的海马体**。

---

Made with ❤️ by [baobao](https://github.com/bao243092078-crypto)

**[⬆ 回到顶部](#memory-anchor-)**

</div>
