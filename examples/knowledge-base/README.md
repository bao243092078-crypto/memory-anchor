# 知识管理场景示例

这个示例展示如何使用 Memory Anchor 构建个人知识库。

## 使用方法

```bash
# 1. 复制配置到 Memory Anchor
cp constitution.yaml ~/.memory-anchor/projects/knowledge-base/

# 2. 启动服务
memory-anchor serve --project knowledge-base
```

## 宪法层设计要点

### 推荐包含的信息

| 分类 | 内容 | 说明 |
|------|------|------|
| person | 学习者身份、关注领域 | 帮助 AI 理解用户兴趣 |
| item | 知识分类体系 | 统一笔记组织方式 |
| routine | 学习方法论 | 指导知识处理方式 |

### 知识管理方法论

这个示例融合了几种知识管理方法：

1. **Zettelkasten**：原子笔记 + 链接网络
2. **费曼学习法**：用简单语言解释复杂概念
3. **间隔重复**：定期复习重要概念

## 配置说明

```yaml
settings:
  min_search_score: 0.2  # 更低阈值，召回更多相关内容
  session_expire_hours: 72  # 延长会话，方便跨天学习
  require_approval_threshold: 0.85  # 知识类内容审批门槛可以稍低
```

## 典型使用场景

1. **读完一本书**：提取核心观点，存入事实层
2. **搜索"关于增长的笔记"**：语义检索相关内容
3. **头脑风暴**：AI 关联已有知识，提供新视角
4. **复习旧笔记**：AI 在相关话题时主动提及
