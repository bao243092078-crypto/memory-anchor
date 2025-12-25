# 当前计划

> 最后更新：2025-12-25

## 正在做

### Harness 增强（学习 claude-code-harness）

**Phase 6: 测试篡改检测（P3）** ⬅️ 当前
- [ ] L1: CLAUDE.md 测试红线规则
- [ ] L2: .ai/operations/sop-test-quality.md
- [ ] L3: PreToolUse hook 自动检测

**Phase 7: 多视角审查命令（P3）**
- [ ] `/ma-review` CLI 命令
- [ ] 四视角：Security/Performance/Quality/Memory Integrity
- [ ] 并行执行 + 报告生成

## 已完成

- [x] PostToolUse + 测试建议（Phase 5）（2025-12-25）
  - [x] 文件修改检测（PostToolHook 增强）
  - [x] 测试映射规则（.ai/test-mapping.yaml）
  - [x] 创建 TestMappingService（规则解析 + 模式展开）
  - [x] 生成测试建议（置信度分级 + 命令生成）
  - [x] 57 个测试全部通过（27 TestMappingService + 13 PostToolHook 集成 + 17 现有）

- [x] 阈值可配置（Phase 4）（2025-12-25）
  - [x] 添加 7 个阈值配置字段到 MemoryAnchorConfig
  - [x] 添加 MA_* 前缀环境变量覆盖（MA_PLANS_MAX_LINES 等）
  - [x] 更新 StopHook 使用配置阈值
  - [x] 添加 20 个阈值测试（默认值 + 环境变量 + YAML + 集成）
  - [x] 45 个相关测试全部通过

- [x] Stop Hook + Session 摘要（Phase 3）（2025-12-25）
  - [x] Stop hook 生成会话摘要（files/memory ops 统计）
  - [x] 自动写入 Memory Anchor（event_log 层）
  - [x] TODO/FIXME 提取（从修改的源文件中）
  - [x] StateManager 集成（会话归档）
  - [x] 25 个测试全部通过

- [x] 状态文件结构化（Phase 2）（2025-12-25）
  - [x] 创建 `backend/state/` 模块
  - [x] 实现 `StateManager` 类（会话生命周期管理）
  - [x] 实现 `SessionState` / `CoverageRecommendation` Pydantic 模型
  - [x] 实现 `.claude/state/` 目录结构（session.json, test-recommendation.json, session-history/）
  - [x] 30 个测试全部通过

- [x] Hook 框架统一（Phase 1）（2025-12-25）
  - [x] 创建 `backend/hooks/base.py` - HookType 枚举 + BaseHook 抽象类
  - [x] 创建 `backend/hooks/registry.py` - HookRegistry 注册中心
  - [x] 重构 `gating_hook.py` 适配新框架
  - [x] 实现 PostToolUse hook - 文件修改追踪
  - [x] 实现 Stop hook - 会话摘要生成
  - [x] 77 个测试全部通过

- [x] Memory Refiner（CoDA 上下文解耦）（2025-12-25）
  - [x] LLM Provider 抽象层（Anthropic/OpenAI/Local）
  - [x] Memory Refiner 服务（Observation Masking）
  - [x] refine_memory MCP 工具
  - [x] 25 个测试全部通过
  - [x] MCP 工具数 13 → 14


- [x] L4 操作性知识层完整实现（2025-12-24）
  - [x] 创建 .ai/operations/ 基础设施（index.yaml + 3 个 SOP）
  - [x] 实现 search_operations MCP 工具
  - [x] 添加强制触发场景（Qdrant 问题、会话开始等）
  - [x] 添加 L4 测试（11 个测试通过）
  - [x] 更新文档（README.md + CLAUDE.md）
  - [x] 五层认知记忆模型完整（L0-L4 + 13 个 MCP 工具）

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
