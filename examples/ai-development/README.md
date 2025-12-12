# AI 开发场景示例

这个示例展示如何使用 Memory Anchor 让 AI 助手记住项目上下文和开发历史。

## 使用方法

```bash
# 1. 复制配置到 Memory Anchor
cp constitution.yaml ~/.memory-anchor/projects/my-project/

# 2. 启动服务
memory-anchor serve --project my-project

# 3. 配置到 Claude Code
# 在 ~/.claude.json 中添加 mcpServers
```

## 宪法层设计要点

### 推荐包含的信息

| 分类 | 内容 | 说明 |
|------|------|------|
| person | 用户身份、技术偏好 | 帮助 AI 理解用户 |
| item | 技术栈、代码规范 | 保持一致性 |
| routine | 开发原则、工作流 | 指导 AI 行为 |

### 与事实层的配合

- 宪法层：不变的核心信息（技术栈、原则）
- 事实层：会演化的信息（架构决策、Bug 修复记录）
- 会话层：临时上下文（当前任务进度）

## 配置说明

```yaml
settings:
  min_search_score: 0.3  # 标准阈值
  session_expire_hours: 24  # 一天的会话记忆
  require_approval_threshold: 0.9  # 标准审批门槛
```

## 典型使用场景

1. **新会话开始**：AI 加载宪法层，了解项目技术栈
2. **搜索"上次讨论的架构"**：从事实层检索
3. **完成 Bug 修复**：记录到事实层，下次可查
4. **重构代码**：AI 参考代码规范和开发原则
