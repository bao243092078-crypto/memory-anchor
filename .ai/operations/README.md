# L4: Operational Knowledge (操作性知识)

> **认知对应**：技能图式 (Procedural Memory)
> **存储位置**：`.ai/operations/`
> **版本**：2025-12-24

---

## 什么是 L4？

L4 是五层认知记忆模型的最高层，存储**操作性知识**：
- SOP（标准操作流程）
- 常用命令序列
- 项目特定的工作流
- 经过验证的最佳实践

与 L3 (verified_fact) 的区别：
- L3 = "知道什么" (declarative)
- L4 = "知道怎么做" (procedural)

---

## 文件命名规范

```
.ai/operations/
├── README.md                    # 本文件
├── index.yaml                   # 索引（AI 快速检索用）
├── sop-<domain>-<action>.md     # SOP 文件
│   例: sop-qdrant-startup.md
│   例: sop-memory-sync.md
└── workflow-<name>.md           # 工作流文件
    例: workflow-session-start.md
```

---

## SOP 模板

```markdown
# SOP: <操作名称>

**触发条件**：<何时执行此 SOP>
**前置条件**：<执行前需要什么>
**预期结果**：<执行后会怎样>

## 步骤

1. <步骤 1>
   ```bash
   <命令>
   ```

2. <步骤 2>
   ...

## 常见问题

### Q: <问题>
A: <解答>

## 相关文件
- <相关 SOP 或文档>
```

---

## AI 检索方式

AI 应通过以下方式检索 L4：

```python
# 1. 检查索引
Read(".ai/operations/index.yaml")

# 2. 根据任务匹配 SOP
Glob(".ai/operations/sop-*.md")

# 3. 读取具体 SOP
Read(".ai/operations/sop-qdrant-startup.md")
```

---

## 与其他层的关系

| 层级 | 关系 |
|------|------|
| L0 identity_schema | L4 不能违背核心身份 |
| L2 event_log | L4 执行结果可记录到 L2 |
| L3 verified_fact | L4 中的知识来源于 L3 的验证 |
