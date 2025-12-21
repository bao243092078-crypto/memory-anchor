# Memory Anchor 🧠⚓

> **为 AI 提供持久化记忆，如同阿尔茨海默症患者的便利贴**

Memory Anchor 是一个基于 MCP（Model Context Protocol）的 AI 记忆系统，让 AI 助手拥有跨会话的持久记忆能力。

## 核心理念

把 AI 当作阿尔茨海默症患者——**能力很强，但容易失忆**。Memory Anchor 就是 AI 的外挂海马体：

- **五层认知记忆模型**：基于认知科学的人类记忆系统，从核心身份到操作性知识
- **清单革命**：跨会话持久化的清单管理，与 Plan skill 协同
- **语义搜索**：基于 Qdrant 向量数据库，支持自然语言检索
- **MCP 协议**：无缝集成 Claude Code、Claude Desktop 等 AI 工具

## 适用场景

| 场景 | 说明 |
|------|------|
| 🏥 **患者照护** | 阿尔茨海默症患者的记忆辅助系统 |
| 🤖 **AI 开发** | 让 AI 助手记住项目上下文、决策历史 |
| 📚 **知识管理** | 个人知识库，语义检索笔记 |

## 快速开始

### 傻瓜 SOP（5 句话 + 3 个命令）

1. 第一次：运行 `uv run memory-anchor init --project my-project` 创建项目。  
2. 每天：运行 `uv run memory-anchor serve --project my-project`，让 Claude/Codex 自动连上记忆。  
3. 看到红叉/报错：先跑 `uv run memory-anchor doctor --project my-project`，按“修复建议”执行。  
4. 只要你没明确要 HTTP，就不要开端口（MCP 用 stdio，不会端口冲突）。  
5. 想要 HTTP API 再用 `memory-anchor serve --mode http --port 8000`，端口占用先 doctor。  

（在仓库目录也可以用 `./ma init|up|doctor`，内部等价于 `uv run memory-anchor ...`）

### 安装

```bash
# 使用 pip
pip install memory-anchor

# 或使用 uv（推荐）
uv add memory-anchor
```

### 初始化项目

```bash
# 交互式初始化
memory-anchor init

# > 项目名称: my-project
# > 项目类型: [ai-development]
# > 核心身份: 我是 baobao，AI 驱动的开发者
```

### 启动服务

```bash
# 启动 MCP Server（stdio 模式，用于 Claude Code）
memory-anchor serve

# 启动 HTTP API（用于自定义集成）
memory-anchor serve --mode http --port 8000
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

## 五层认知记忆模型 (v2.0)

基于认知科学的人类记忆系统，映射到 AI 的记忆架构：

```
┌─────────────────────────────────────────────────────────────┐
│  L0: identity_schema (自我概念) ←── 三次审批 ←── 照护者     │
│  L1: active_context (工作记忆)  ←── 会话临时 ←── AI        │
│  L2: event_log (情景记忆)       ←── 时空标记 ←── AI/人工   │
│  L3: verified_fact (语义记忆)   ←── 置信度≥0.8 ←── AI/人工 │
│  L4: operational_knowledge (技能图式) ←── .ai/operations/  │
└─────────────────────────────────────────────────────────────┘
```

| 层级 | 代码标识 | 认知对应 | 写入权限 | 持久化 |
|------|---------|---------|----------|--------|
| 🔴 L0 | `identity_schema` | 自我概念 | 仅照护者，三次审批 | YAML + Qdrant |
| 🟡 L1 | `active_context` | 工作记忆 | 自动 | 仅内存（不持久化） |
| 🟢 L2 | `event_log` | 情景记忆 | AI + 人工 | Qdrant（可设 TTL） |
| 🔵 L3 | `verified_fact` | 语义记忆 | AI + 人工 | Qdrant（永久） |
| ⚪ L4 | `operational_knowledge` | 技能图式 | 文件系统 | .ai/operations/ |

### 向后兼容

| 旧术语 (v1.x) | 新术语 (v2.x) |
|--------------|--------------|
| `constitution` | `identity_schema` |
| `fact` | `verified_fact` |
| `session` | `event_log` + `active_context` |

## MCP 工具

### 记忆管理（核心）

| 工具 | 说明 |
|------|------|
| `search_memory` | 语义搜索记忆（支持 layer/category 过滤） |
| `add_memory` | 添加新记忆（支持置信度分级） |
| `get_constitution` | 获取身份图式层（L0，每会话自动加载） |
| `propose_constitution_change` | 提议修改身份图式（需三次审批） |

### 清单革命（v2.0 新增）

> **设计原则**：Checklist = 战略层（跨会话持久），Plan skill = 战术层（单次任务）

| 工具 | 说明 |
|------|------|
| `create_checklist_item` | 创建持久化清单项（支持优先级/范围/标签） |
| `get_checklist_briefing` | 获取清单简报（会话开始时自动调用） |
| `sync_from_plan` | 从 Plan skill 同步状态（通过 `(ma:xxx)` ID 桥接） |

### 事件日志（v2.0 新增）

| 工具 | 说明 |
|------|------|
| `log_event` | 记录带时空标记的事件（L2 情景记忆） |
| `search_events` | 按时间/地点/人物过滤事件 |
| `promote_to_fact` | 将事件提升为验证事实（L2 → L3） |

### 使用示例

```python
# AI 搜索相关记忆
memories = search_memory(query="上次讨论的架构决策")

# AI 记录重要发现（使用新 layer 名称）
add_memory(
    content="决定使用 Qdrant 作为向量数据库",
    layer="verified_fact",  # 新术语，兼容旧的 "fact"
    category="event",
    confidence=0.9
)

# 获取核心身份（每次会话开始时加载）
constitution = get_constitution()

# 创建持久化清单项
create_checklist_item(
    content="实现五层认知记忆模型",
    priority="high",
    scope="project",
    tags=["architecture", "v2.0"]
)

# 获取清单简报（返回 Markdown 格式）
briefing = get_checklist_briefing(
    scope="project",
    include_ids=True  # 包含 (ma:xxx) 引用
)

# 从 Plan 同步完成状态
sync_from_plan(
    plan_markdown=plan_content,  # 解析 [x] 和 (ma:xxx)
    session_id="session-001"
)
```

## 配置文件

初始化后会在 `~/.memory-anchor/projects/{name}/` 创建配置：

```yaml
# constitution.yaml - 宪法层定义
version: 1
project:
  name: "my-project"
  type: "ai-development"

constitution:
  - id: "user-identity"
    category: "person"
    content: "用户是 baobao，AI 驱动的开发者"

  - id: "project-goal"
    category: "item"
    content: "构建可复制的自动化流水线"

settings:
  max_constitution_items: 20
  min_search_score: 0.3
  session_expire_hours: 24
```

## 项目结构

```
memory-anchor/
├── backend/
│   ├── api/              # FastAPI 路由
│   │   ├── notes.py      # 记忆 CRUD
│   │   ├── search.py     # 语义搜索
│   │   ├── memory.py     # 记忆操作
│   │   ├── constitution.py  # 身份图式层
│   │   └── checklist.py  # 清单革命 API
│   ├── cli/              # CLI 命令
│   │   ├── init_cmd.py   # 项目初始化
│   │   ├── serve_cmd.py  # 服务启动
│   │   └── doctor_cmd.py # 健康诊断
│   ├── core/             # 核心引擎
│   │   ├── memory_kernel.py   # 记忆内核（sync）
│   │   └── active_context.py  # L1 工作记忆
│   ├── models/           # 数据模型
│   │   ├── note.py       # 记忆层枚举
│   │   ├── checklist.py  # 清单模型
│   │   └── constitution_change.py  # 变更提议
│   ├── services/         # 业务逻辑
│   │   ├── search.py     # Qdrant 向量搜索
│   │   ├── memory.py     # 记忆服务
│   │   ├── constitution.py  # 身份图式管理
│   │   ├── checklist_service.py  # 清单服务
│   │   └── embedding.py  # FastEmbed 向量化
│   └── tests/            # pytest 测试
├── scripts/              # 运维脚本
│   ├── mcp_wrapper.sh    # MCP 环境包装
│   └── checkpoint.py     # 上下文保护 Hook
├── docs/                 # 文档
│   └── MEMORY_STRATEGY.md  # 记忆策略详解
├── .memos/               # 记忆同步目录
├── ma                    # CLI 快捷入口
├── pyproject.toml        # 项目配置
├── LICENSE               # MIT 许可证
└── README.md
```

## 开发

```bash
# 克隆仓库
git clone https://github.com/baobao/memory-anchor.git
cd memory-anchor

# 安装依赖
uv sync --all-extras

# 启动 Qdrant（可选）
docker run -d -p 6333:6333 --name qdrant qdrant/qdrant

# 运行测试
uv run pytest

# 代码检查
uv run ruff check backend
```

## 技术栈

- **后端**: Python 3.12 + FastAPI + Pydantic
- **向量数据库**: Qdrant（本地/远程）
- **嵌入模型**: FastEmbed (all-MiniLM-L6-v2)
- **MCP**: Model Context Protocol
- **CLI**: Typer + Rich

## 路线图

### 已完成 ✅

- [x] 三层记忆模型 → **升级为五层认知记忆模型 (v2.0)**
- [x] MCP Server 集成
- [x] CLI 工具（init/serve/status/doctor）
- [x] 宪法层三次审批机制
- [x] **清单革命**：ChecklistService + Plan skill 协同
- [x] **事件日志**：L2 情景记忆（带时空标记）
- [x] **向后兼容**：旧 API (constitution/fact/session) 自动映射

### 进行中 🚧

- [ ] Web UI（照护者端）
- [ ] checkpoint.py 上下文保护（PreCompact Hook）

### 规划中 📋

- [ ] TTS 语音播报
- [ ] 多用户支持
- [ ] 云端同步
- [ ] 多语言支持

## 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何参与。

## 许可证

[MIT License](LICENSE)

## 致谢

这个项目的灵感来自于：**如果 AI 是阿尔茨海默症患者，那它需要什么样的外挂记忆？**

答案是：一个可靠的、有层级的、能语义检索的记忆锚点。

---

Made with ❤️ by [baobao](https://github.com/baobao)
