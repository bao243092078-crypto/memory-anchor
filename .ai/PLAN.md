# 当前计划

> 最后更新：2025-12-22

## 正在做

（无）

## 已完成

- [x] 高风险操作 Gating Hook
  - [x] 设计 Gating Hook 机制（拦截 delete_memory、clear_*、constitution delete）
  - [x] 实现确认短语检测（"确认删除"/"confirm delete"/"我确认"）
  - [x] 实现 backend/hooks/gating_hook.py
  - [x] 添加 MCP delete_memory 工具（带 Gating）
  - [x] 测试 Gating Hook 功能（14 个测试通过）

- [x] 偏离度量化（语义相似度）
  - [x] 设计偏离度计算算法
  - [x] 实现 /drift-check 命令的量化输出
  - [x] 测试偏离度计算

- [x] 北极星同步到 Memory Anchor L0（宪法层）
  - [x] 设计同步机制：NORTH_STAR.md → constitution 层
  - [x] 实现 CLI 命令 `./ma sync-north-star`
  - [x] 测试同步流程（`get_constitution()` 验证成功）

- [x] 实现北极星对齐系统
  - [x] SessionStart hook 注入北极星
  - [x] 每 N 轮周期性提醒
  - [x] Stop hook 结束提醒
  - [x] /drift-check 命令
- [x] 实现计划持久化系统
  - [x] PLAN.md 模板
  - [x] Hook 注入计划
  - [x] AI 自动更新计划的规则（已写入 CLAUDE.md）
- [x] 三方 AI 头脑风暴分析问题
- [x] 苏格拉底式问题拆解

## 待定（以后再做）

（无）
