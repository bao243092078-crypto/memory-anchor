# 患者照护场景示例

这个示例展示如何使用 Memory Anchor 为阿尔茨海默症患者构建记忆辅助系统。

## 使用方法

```bash
# 1. 复制配置到 Memory Anchor
cp constitution.yaml ~/.memory-anchor/projects/patient-care/

# 2. 启动服务
memory-anchor serve --project patient-care
```

## 宪法层设计要点

### 必须包含的信息

| 分类 | 内容 | 重要性 |
|------|------|--------|
| person | 患者基本信息、家庭成员 | 🔴 关键 |
| routine | 用药时间、日常作息 | 🔴 关键 |
| item | 过敏信息、医疗禁忌 | 🔴 关键 |
| place | 医院、定期活动地点 | 🟡 重要 |

### 安全考虑

- 医疗信息（特别是过敏）必须放在宪法层
- 紧急联系人电话必须准确
- 定期与照护者确认信息是否过时

## 配置说明

```yaml
settings:
  min_search_score: 0.25  # 降低阈值，尽量召回
  session_expire_hours: 48  # 延长会话记忆
  require_approval_threshold: 0.95  # 更严格的审批
```

## 典型使用场景

1. **提醒吃药**：AI 根据 routine 层信息提醒用药时间
2. **回答"女儿电话是多少"**：从宪法层直接返回
3. **记录就医信息**：存入事实层，方便下次查询
