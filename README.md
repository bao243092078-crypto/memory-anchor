# Memory Anchor 🧠⚓

> **为 AI 提供持久化记忆，如同阿尔茨海默症患者的便利贴**

Memory Anchor 是一个基于 MCP（Model Context Protocol）的 AI 记忆系统，让 AI 助手拥有跨会话的持久记忆能力。

## 核心理念

把 AI 当作阿尔茨海默症患者——**能力很强，但容易失忆**。Memory Anchor 就是 AI 的外挂海马体：

- **三层记忆模型**：宪法层（核心身份）→ 事实层（长期记忆）→ 会话层（短期对话）
- **语义搜索**：基于 Qdrant 向量数据库，支持自然语言检索
- **MCP 协议**：无缝集成 Claude Code、Claude Desktop 等 AI 工具

## 适用场景

| 场景 | 说明 |
|------|------|
| 🏥 **患者照护** | 阿尔茨海默症患者的记忆辅助系统 |
| 🤖 **AI 开发** | 让 AI 助手记住项目上下文、决策历史 |
| 📚 **知识管理** | 个人知识库，语义检索笔记 |

## 快速开始

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

## 三层记忆模型

```
宪法层 ←──[三次审批]── 事实层 ←──[置信度>0.8]── 会话层
  ↓                        ↓                         ↑
[自动加载]           [RAG 语义检索]              [AI 提取]
```

| 层级 | 名称 | 写入权限 | 过期时间 | 用途 |
|------|------|----------|----------|------|
| 🔴 Layer 0 | 宪法层 | 仅人工，三次审批 | 永不 | 核心身份 |
| 🔵 Layer 1 | 事实层 | AI + 人工 | 可配置 | 长期记忆 |
| 🟢 Layer 2 | 会话层 | 自动记录 | 24h | 短期对话 |

## MCP 工具

| 工具 | 说明 |
|------|------|
| `search_memory` | 语义搜索记忆 |
| `add_memory` | 添加新记忆 |
| `get_constitution` | 获取宪法层（核心身份） |
| `propose_constitution_change` | 提议修改宪法层 |

### 使用示例

```python
# AI 搜索相关记忆
memories = search_memory(query="上次讨论的架构决策")

# AI 记录重要发现
add_memory(
    content="决定使用 Qdrant 作为向量数据库",
    layer="fact",
    category="event",
    confidence=0.9
)

# 获取核心身份（每次会话开始时加载）
constitution = get_constitution()
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
│   ├── api/          # FastAPI 路由
│   ├── cli/          # CLI 命令（init/serve/status）
│   ├── models/       # 数据模型
│   ├── services/     # 业务逻辑
│   └── tests/        # 测试
├── examples/         # 使用示例
│   ├── patient-care/     # 患者照护场景
│   ├── ai-development/   # AI 开发场景
│   └── knowledge-base/   # 知识管理场景
├── docs/             # 文档
├── pyproject.toml    # 项目配置
├── LICENSE           # MIT 许可证
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

- [x] 三层记忆模型
- [x] MCP Server 集成
- [x] CLI 工具（init/serve/status）
- [x] 宪法层三次审批机制
- [ ] Web UI（照护者端）
- [ ] TTS 语音播报
- [ ] 多用户支持
- [ ] 云端同步

## 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何参与。

## 许可证

[MIT License](LICENSE)

## 致谢

这个项目的灵感来自于：**如果 AI 是阿尔茨海默症患者，那它需要什么样的外挂记忆？**

答案是：一个可靠的、有层级的、能语义检索的记忆锚点。

---

Made with ❤️ by [baobao](https://github.com/baobao)
