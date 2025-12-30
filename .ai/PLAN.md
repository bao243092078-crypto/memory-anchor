# 当前计划

> 最后更新：2025-12-30
> 版本目标：v3.0 - 认知增强版

---

## 🎯 Sprint 目标

**Memory Anchor v3.0**：基于四方 AI 头脑风暴结论，引入上下文预算管理、安全过滤、时间感知和冲突检测，同时保持"我妈能用"的极简理念。

---

## 正在做

（无）

---

## 📋 v3.0 清单（按优先级）

### Phase 0: 前置检查（开始前必做）

> ⏱️ 预计：0.5 天 | 🔴 暂停点

- [ ] **P0-1** 确认 Qdrant Server 运行正常（`curl http://127.0.0.1:6333/collections`）
- [ ] **P0-2** 确认测试全部通过（`uv run pytest` - 当前 498 个）
- [ ] **P0-3** 创建 `feature/v3.0-cognitive-enhancement` 分支
- [ ] **P0-4** 备份现有数据（`./ma cloud push --encrypt`）

🔴 **暂停点**：以上全部 ✅ 后再继续

---

### Phase 1: ContextBudgetManager（P0 优先级）

> ⏱️ 预计：2-3 天 | 🎯 防止上下文爆炸

**1.1 设计（0.5 天）**
- [ ] **P1-1** 创建 `backend/core/context_budget.py` 模块
- [ ] **P1-2** 定义 `ContextBudget` 数据类：
  ```python
  @dataclass
  class ContextBudget:
      l0_identity: int = 500      # 宪法层上限
      l2_events: int = 500        # 事件层上限
      l3_facts: int = 2000        # 事实层上限
      total_limit: int = 4000     # 总上限
  ```
- [ ] **P1-3** 设计 token 计算策略（tiktoken 或字符估算）

**1.2 实现（1 天）**
- [ ] **P1-4** 实现 `ContextBudgetManager` 类：
  - `allocate(layer, content) -> bool` - 检查是否超限
  - `get_usage() -> dict` - 返回各层使用情况
  - `truncate_to_fit(memories, limit) -> list` - 按重要性截断
- [ ] **P1-5** 集成到 `MemoryKernel.search()` 方法
- [ ] **P1-6** 添加 CLI 命令 `./ma budget --project NAME`

**1.3 测试（0.5 天）**
- [ ] **P1-7** 编写 15+ 测试用例（边界值、超限、截断）
- [ ] **P1-8** 运行全量测试确保无回归

🔴 **暂停点**：测试全绿后，提交 commit

---

### Phase 2: SafetyFilter（P0 优先级）

> ⏱️ 预计：1 天 | 🛡️ Anthropic 安全对齐

**2.1 设计（0.25 天）**
- [ ] **P2-1** 创建 `backend/core/safety_filter.py` 模块
- [ ] **P2-2** 定义过滤规则：
  - 敏感词检测（可配置词表）
  - PII 检测（邮箱、电话、身份证）
  - 长度限制（单条记忆 ≤ 2000 字符）

**2.2 实现（0.5 天）**
- [ ] **P2-3** 实现 `SafetyFilter` 类：
  - `filter(content) -> FilterResult` - 返回过滤结果
  - `sanitize(content) -> str` - 脱敏处理
- [ ] **P2-4** 集成到 `add_memory()` 入口
- [ ] **P2-5** 添加配置项 `MA_SAFETY_FILTER_ENABLED=true`

**2.3 测试（0.25 天）**
- [ ] **P2-6** 编写 10+ 测试用例（敏感词、PII、边界）
- [ ] **P2-7** 运行全量测试确保无回归

🔴 **暂停点**：测试全绿后，提交 commit

---

### Phase 3: Bi-temporal 时间感知（P1 优先级）

> ⏱️ 预计：3-5 天 | ⏰ 时间维度增强

**3.1 数据模型升级（1 天）**
- [ ] **P3-1** 扩展 `Note` 模型，添加 3 个时间戳：
  ```python
  created_at: datetime      # 创建时间（已有）
  valid_at: datetime | None # 生效时间（新增）
  expired_at: datetime | None  # 失效时间（新增）
  ```
- [ ] **P3-2** 更新 Qdrant payload schema
- [ ] **P3-3** 编写数据迁移脚本（现有数据 `valid_at = created_at`）

**3.2 查询增强（1 天）**
- [ ] **P3-4** 实现 `TemporalQuery` 类：
  - `at_time(t)` - 查询某时刻有效的记忆
  - `in_range(start, end)` - 查询时间范围内的记忆
  - `only_valid()` - 只返回未过期的记忆
- [ ] **P3-5** 更新 `search_memory` MCP 工具，添加 `as_of` 参数
- [ ] **P3-6** 更新 `search_events` MCP 工具，支持时间范围

**3.3 UI 更新（0.5 天）**
- [ ] **P3-7** 前端 NoteCard 显示有效期状态
- [ ] **P3-8** 时间线视图支持 Bi-temporal 筛选

**3.4 测试（0.5 天）**
- [ ] **P3-9** 编写 20+ 测试用例（时间查询、过期、迁移）
- [ ] **P3-10** 运行全量测试确保无回归

🔴 **暂停点**：测试全绿后，提交 commit + 更新 CHANGELOG

---

### Phase 4: ConflictDetector MVP（P2 优先级）

> ⏱️ 预计：3-4 天 | ⚔️ 冲突检测

**4.1 规则引擎（1.5 天）**
- [ ] **P4-1** 创建 `backend/core/conflict_detector.py` 模块
- [ ] **P4-2** 实现基于规则的冲突检测：
  - 时间冲突：同一实体的新旧记录
  - 来源冲突：不同来源的矛盾信息
  - 置信度比较：低置信度 vs 高置信度
- [ ] **P4-3** 定义 `ConflictResult` 数据类：
  ```python
  @dataclass
  class ConflictResult:
      has_conflict: bool
      conflict_type: str  # temporal | source | confidence
      conflicting_memories: list[UUID]
      resolution_hint: str
  ```

**4.2 集成（1 天）**
- [ ] **P4-4** 在 `add_memory()` 前调用冲突检测
- [ ] **P4-5** 冲突时返回警告（不阻止写入，仅提示）
- [ ] **P4-6** 添加 CLI 命令 `./ma conflicts --project NAME`

**4.3 测试（0.5 天）**
- [ ] **P4-7** 编写 15+ 测试用例（各类冲突场景）
- [ ] **P4-8** 运行全量测试确保无回归

🔴 **暂停点**：测试全绿后，提交 commit

---

### Phase 5: Tool Memory L4b（P3 优先级，可选）

> ⏱️ 预计：5+ 天 | 🔧 工具调用记忆（默认关闭）

**5.1 评估（1 天）**
- [ ] **P5-1** 分析 MemOS Tool Memory 的实际价值
- [ ] **P5-2** 评估与现有 `.ai/operations/` SOP 的重叠
- [ ] **P5-3** 决定是否继续（⚠️ 可能跳过）

**5.2 实现（如果继续）**
- [ ] **P5-4** 创建 `backend/core/tool_memory.py` 模块
- [ ] **P5-5** 实现工具调用轨迹记录
- [ ] **P5-6** 添加配置项 `MA_TOOL_MEMORY_ENABLED=false`（默认关闭）

**5.3 测试**
- [ ] **P5-7** 编写测试用例
- [ ] **P5-8** 运行全量测试确保无回归

---

### Phase 6: 发布准备

> ⏱️ 预计：1 天

- [ ] **P6-1** 更新 `pyproject.toml` 版本号 → `3.0.0`
- [ ] **P6-2** 更新 `CHANGELOG.md`
- [ ] **P6-3** 更新 `README.md` 新功能说明
- [ ] **P6-4** 创建 PR，请求 Code Review
- [ ] **P6-5** 合并到 main，打 tag `v3.0.0`
- [ ] **P6-6** 写入 Memory Anchor：`add_memory("v3.0.0 发布...")`

---

## ✅ 验收标准（Definition of Done）

| 功能 | 验收条件 |
|------|----------|
| ContextBudgetManager | `./ma budget` 显示各层 token 使用量 |
| SafetyFilter | 敏感词/PII 被自动过滤，有日志记录 |
| Bi-temporal | `search_memory(as_of="2025-01-01")` 返回正确结果 |
| ConflictDetector | 冲突记忆写入时有警告提示 |
| Tool Memory | 配置开启后，工具调用被记录（可选） |
| 整体 | 测试 500+ 个全绿，无回归 |

---

## 📊 里程碑

| 日期 | 目标 | 状态 |
|------|------|------|
| 2025-01-03 | Phase 1-2 完成（P0 优先级） | ⬜ |
| 2025-01-10 | Phase 3 完成（Bi-temporal） | ⬜ |
| 2025-01-15 | Phase 4 完成（ConflictDetector） | ⬜ |
| 2025-01-20 | v3.0.0 发布 | ⬜ |

---

## 🔗 参考资料

- [MemoryAgentBench Paper](https://arxiv.org/abs/2507.05257) - 冲突检测基准
- [Zep Temporal KG Paper](https://arxiv.org/abs/2501.13956) - Bi-temporal 架构
- [四方 AI 头脑风暴结果](待写入 Memory Anchor) - 2025-12-30

---

## 已完成

- [x] 记忆图谱可视化（Memory Graph）（2025-12-28）
  - [x] Phase 1: 后端 API（GraphNode/GraphEdge 模型，`/api/v1/graph` 端点）
  - [x] Phase 2: 前端 D3.js（力导向图，节点按 layer 分色）
  - [x] Phase 3: 交互功能（节点点击/缩放/拖拽/筛选）
  - [x] Phase 4: 测试（15 个新测试，498 个测试全部通过）
  - [x] 更新 README 和版本号（v2.1.0）

- [x] Memory Viewer Web UI 功能扩展（2025-12-28）
  - [x] 时间线可视化 Phase 1（Recharts 堆叠面积图）
  - [x] 时间线可视化 Phase 2（时间范围筛选 + 粒度切换）
  - [x] 批量操作（multi-select delete/verify）
  - [x] 多项目隔离（ProjectSelector 组件）
  - [x] i18n 国际化（中英文切换，143 个翻译键）
  - [x] 提交 8eff2e5, 1c01042, db1062f

- [x] Cloud Sync 云端同步（2025-12-26）
- [x] checkpoint.py 上下文保护（Phase 8）（2025-12-26）
- [x] 多视角审查命令（Phase 7）（2025-12-25）
- [x] 测试篡改检测（Phase 6）（2025-12-25）
- [x] PostToolUse + 测试建议（Phase 5）（2025-12-25）
- [x] 阈值可配置（Phase 4）（2025-12-25）
- [x] Stop Hook + Session 摘要（Phase 3）（2025-12-25）
- [x] 状态文件结构化（Phase 2）（2025-12-25）
- [x] Hook 框架统一（Phase 1）（2025-12-25）
- [x] Memory Refiner（CoDA 上下文解耦）（2025-12-25）
- [x] L4 操作性知识层完整实现（2025-12-24）
- [x] 高风险操作 Gating Hook
- [x] 偏离度量化（语义相似度）
- [x] 北极星同步到 Memory Anchor L0（宪法层）
- [x] 实现北极星对齐系统
- [x] 实现计划持久化系统
- [x] 三方 AI 头脑风暴分析问题
- [x] 苏格拉底式问题拆解

## 待定（以后再做）

- [ ] LLM 辅助冲突解决（需要更多 benchmark 数据）
- [ ] Habit Discovery 引擎（Gemini 建议，待评估）
- [ ] 跨项目记忆共享（企业级功能）
