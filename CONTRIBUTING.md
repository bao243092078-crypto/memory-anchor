# Contributing to Memory Anchor

感谢你对 Memory Anchor 的关注！我们欢迎各种形式的贡献。

## 🚀 快速开始

### 开发环境设置

```bash
# 1. Fork 并 clone 仓库
git clone https://github.com/YOUR_USERNAME/memory-anchor.git
cd memory-anchor

# 2. 安装依赖
uv sync --all-extras

# 3. 启动 Qdrant（可选，用于测试向量搜索）
docker run -d -p 6333:6333 --name qdrant qdrant/qdrant

# 4. 运行测试
uv run pytest

# 5. 代码检查
uv run ruff check backend
```

### 项目结构

```
memory-anchor/
├── backend/
│   ├── api/          # FastAPI 路由
│   ├── cli/          # CLI 命令
│   ├── models/       # 数据模型
│   ├── services/     # 业务逻辑
│   └── tests/        # 测试
├── docs/             # 文档
├── examples/         # 使用示例
└── pyproject.toml    # 项目配置
```

## 🎯 贡献方式

### 报告 Bug

1. 搜索 [Issues](https://github.com/baobao/memory-anchor/issues) 确认问题未被报告
2. 创建新 Issue，包含：
   - 问题描述
   - 复现步骤
   - 预期行为 vs 实际行为
   - 环境信息（Python 版本、OS 等）

### 功能建议

1. 创建 Issue 描述你的想法
2. 说明使用场景和预期效果
3. 等待讨论后再开始实现

### 提交代码

1. Fork 仓库并创建分支：`git checkout -b feature/my-feature`
2. 编写代码和测试
3. 确保测试通过：`uv run pytest`
4. 确保代码风格一致：`uv run ruff check backend --fix`
5. 提交变更：`git commit -m "feat: add my feature"`
6. 推送并创建 Pull Request

## 📝 代码规范

### Commit 消息格式

使用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

类型：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码风格（不影响功能）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具链

### Python 代码风格

- 使用 [Ruff](https://github.com/astral-sh/ruff) 进行代码检查
- 类型注解（Type Hints）是必须的
- 函数和类需要 docstring
- 行长度限制 100 字符

### 测试要求

- 新功能需要对应的测试
- Bug 修复需要添加回归测试
- 测试覆盖率不应下降

## 🏛️ 三层记忆模型

理解核心概念对贡献很重要：

| 层级 | 名称 | 说明 |
|------|------|------|
| Layer 0 | 宪法层 | 核心身份，只读，修改需三次审批 |
| Layer 1 | 事实层 | 长期记忆，可读写 |
| Layer 2 | 会话层 | 短期记忆，24h 过期 |

## 🔴 红线禁止

- 不要在日志中记录记忆内容（隐私）
- 不要绕过三次审批机制修改宪法层
- 不要引入不安全的依赖

## 📞 联系方式

- GitHub Issues: 技术问题讨论
- Email: baobao@example.com

---

感谢你的贡献！🎉
