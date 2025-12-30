"""
ContextBudgetManager - 上下文预算管理器 (v3.0)

防止上下文爆炸，确保各层记忆在 token 预算内。

设计原则：
1. 简单优先 - 字符估算（4字符≈1 token），避免引入重依赖
2. 分层管理 - 每层有独立预算，可配置
3. 优雅降级 - 超限时按重要性截断，而非报错
4. 可观测 - 提供使用情况统计

基于四方 AI 头脑风暴结论：
- L0 (identity_schema): 500 tokens - 核心身份，始终优先
- L2 (event_log): 500 tokens - 近期事件，FIFO
- L3 (verified_fact): 2000 tokens - 长期事实，按相关性

参考：
- Zep 论文 arXiv:2501.13956 (ContextBudgetManager 概念)
- MemoryAgentBench arXiv:2507.05257 (上下文管理重要性)
"""

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class BudgetLayer(str, Enum):
    """预算层级枚举（与 MemoryLayer 对应）"""
    L0_IDENTITY = "identity_schema"
    L1_ACTIVE = "active_context"
    L2_EVENTS = "event_log"
    L3_FACTS = "verified_fact"
    L4_OPS = "operational_knowledge"


@dataclass
class ContextBudget:
    """
    上下文预算配置

    每层的 token 上限，可通过环境变量覆盖：
    - MA_BUDGET_L0: 身份层预算
    - MA_BUDGET_L2: 事件层预算
    - MA_BUDGET_L3: 事实层预算
    - MA_BUDGET_TOTAL: 总预算上限
    """
    l0_identity: int = 500      # L0 身份层上限（核心身份，始终加载）
    l1_active: int = 200        # L1 工作记忆上限（会话内）
    l2_events: int = 500        # L2 事件层上限（近期事件）
    l3_facts: int = 2000        # L3 事实层上限（语义记忆）
    l4_ops: int = 300           # L4 操作层上限（SOP 摘要）
    total_limit: int = 4000     # 总上限（所有层之和）

    # 高级配置
    chars_per_token: float = 4.0  # 字符/token 估算比例（中英混合）
    truncate_strategy: str = "tail"  # 截断策略：tail（截尾）| head（截头）| smart（按相关性）

    @classmethod
    def from_env(cls) -> "ContextBudget":
        """从环境变量加载配置"""
        import os
        return cls(
            l0_identity=int(os.getenv("MA_BUDGET_L0", "500")),
            l1_active=int(os.getenv("MA_BUDGET_L1", "200")),
            l2_events=int(os.getenv("MA_BUDGET_L2", "500")),
            l3_facts=int(os.getenv("MA_BUDGET_L3", "2000")),
            l4_ops=int(os.getenv("MA_BUDGET_L4", "300")),
            total_limit=int(os.getenv("MA_BUDGET_TOTAL", "4000")),
        )


@dataclass
class BudgetUsage:
    """预算使用情况"""
    layer: str
    allocated: int      # 已分配 tokens
    limit: int          # 上限
    items_count: int    # 记忆条数
    truncated: int = 0  # 被截断条数

    @property
    def usage_ratio(self) -> float:
        """使用率 (0.0 - 1.0)"""
        return self.allocated / self.limit if self.limit > 0 else 0.0

    @property
    def remaining(self) -> int:
        """剩余可用 tokens"""
        return max(0, self.limit - self.allocated)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "layer": self.layer,
            "allocated": self.allocated,
            "limit": self.limit,
            "remaining": self.remaining,
            "usage_ratio": round(self.usage_ratio, 2),
            "items_count": self.items_count,
            "truncated": self.truncated,
        }


@dataclass
class BudgetReport:
    """预算报告"""
    layers: Dict[str, BudgetUsage] = field(default_factory=dict)
    total_allocated: int = 0
    total_limit: int = 4000

    @property
    def total_usage_ratio(self) -> float:
        """总使用率"""
        return self.total_allocated / self.total_limit if self.total_limit > 0 else 0.0

    @property
    def is_over_budget(self) -> bool:
        """是否超预算"""
        return self.total_allocated > self.total_limit

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "layers": {k: v.to_dict() for k, v in self.layers.items()},
            "total_allocated": self.total_allocated,
            "total_limit": self.total_limit,
            "total_usage_ratio": round(self.total_usage_ratio, 2),
            "is_over_budget": self.is_over_budget,
        }


class ContextBudgetManager:
    """
    上下文预算管理器

    职责：
    1. 估算内容的 token 数
    2. 检查是否超限
    3. 按预算截断记忆列表
    4. 报告使用情况

    使用示例：
    ```python
    manager = ContextBudgetManager()

    # 检查单条记忆
    tokens = manager.estimate_tokens("这是一条记忆内容")
    can_add = manager.can_allocate("verified_fact", tokens)

    # 截断记忆列表
    memories = [{"content": "...", "score": 0.9}, ...]
    truncated = manager.truncate_to_fit(memories, "verified_fact")

    # 获取使用报告
    report = manager.get_report()
    ```
    """

    def __init__(self, budget: Optional[ContextBudget] = None):
        """
        初始化预算管理器

        Args:
            budget: 预算配置，默认从环境变量加载
        """
        self.budget = budget or ContextBudget.from_env()
        self._usage: Dict[str, BudgetUsage] = {}
        self._init_usage()

    def _init_usage(self) -> None:
        """初始化各层使用情况"""
        layer_limits = {
            BudgetLayer.L0_IDENTITY.value: self.budget.l0_identity,
            BudgetLayer.L1_ACTIVE.value: self.budget.l1_active,
            BudgetLayer.L2_EVENTS.value: self.budget.l2_events,
            BudgetLayer.L3_FACTS.value: self.budget.l3_facts,
            BudgetLayer.L4_OPS.value: self.budget.l4_ops,
        }
        for layer, limit in layer_limits.items():
            self._usage[layer] = BudgetUsage(
                layer=layer,
                allocated=0,
                limit=limit,
                items_count=0,
            )

    def reset(self) -> None:
        """重置所有使用情况"""
        self._init_usage()

    def estimate_tokens(self, content: str) -> int:
        """
        估算内容的 token 数

        使用简单的字符估算法（4字符≈1 token）
        对于中英混合文本，这是一个合理的近似

        Args:
            content: 文本内容

        Returns:
            估算的 token 数
        """
        if not content:
            return 0
        return max(1, int(len(content) / self.budget.chars_per_token))

    def estimate_memory_tokens(self, memory: Dict[str, Any]) -> int:
        """
        估算单条记忆的 token 数

        包括 content + 元数据开销

        Args:
            memory: 记忆字典，需包含 'content' 字段

        Returns:
            估算的 token 数
        """
        content = memory.get("content", "")
        base_tokens = self.estimate_tokens(content)
        # 元数据开销（layer, category, timestamp 等）约 20 tokens
        metadata_overhead = 20
        return base_tokens + metadata_overhead

    def can_allocate(self, layer: str, tokens: int) -> bool:
        """
        检查是否可以分配指定 tokens

        Args:
            layer: 层级名称
            tokens: 要分配的 token 数

        Returns:
            是否可以分配
        """
        usage = self._usage.get(layer)
        if not usage:
            logger.warning(f"Unknown layer: {layer}")
            return True  # 未知层不限制

        # 检查层级限制
        if usage.allocated + tokens > usage.limit:
            return False

        # 检查总限制
        total = sum(u.allocated for u in self._usage.values()) + tokens
        if total > self.budget.total_limit:
            return False

        return True

    def allocate(self, layer: str, tokens: int, items: int = 1) -> bool:
        """
        分配 tokens

        Args:
            layer: 层级名称
            tokens: 要分配的 token 数
            items: 记忆条数

        Returns:
            是否分配成功
        """
        if not self.can_allocate(layer, tokens):
            return False

        usage = self._usage.get(layer)
        if usage:
            usage.allocated += tokens
            usage.items_count += items
        return True

    def truncate_to_fit(
        self,
        memories: List[Dict[str, Any]],
        layer: str,
        *,
        sort_by: str = "score",
        preserve_first: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        按预算截断记忆列表

        Args:
            memories: 记忆列表（需包含 'content' 字段）
            layer: 目标层级
            sort_by: 排序字段（默认按相关性分数）
            preserve_first: 保留前 N 条（不截断）

        Returns:
            (截断后的列表, 被截断的条数)
        """
        if not memories:
            return [], 0

        usage = self._usage.get(layer)
        if not usage:
            return memories, 0

        remaining_budget = usage.remaining

        # 按分数降序排列（高分优先保留）
        if sort_by == "score":
            sorted_memories = sorted(
                memories,
                key=lambda m: m.get("score", 0),
                reverse=True
            )
        else:
            sorted_memories = list(memories)

        result = []
        used_tokens = 0
        truncated = 0

        for i, memory in enumerate(sorted_memories):
            tokens = self.estimate_memory_tokens(memory)

            # 保留前 N 条
            if i < preserve_first:
                result.append(memory)
                used_tokens += tokens
                continue

            # 检查预算
            if used_tokens + tokens <= remaining_budget:
                result.append(memory)
                used_tokens += tokens
            else:
                truncated += 1

        # 更新使用情况
        if result:
            self.allocate(layer, used_tokens, len(result))
            usage.truncated = truncated

        return result, truncated

    def get_layer_usage(self, layer: str) -> Optional[BudgetUsage]:
        """获取指定层的使用情况"""
        return self._usage.get(layer)

    def get_report(self) -> BudgetReport:
        """
        获取完整的预算使用报告

        Returns:
            BudgetReport 对象
        """
        total_allocated = sum(u.allocated for u in self._usage.values())
        return BudgetReport(
            layers=dict(self._usage),
            total_allocated=total_allocated,
            total_limit=self.budget.total_limit,
        )

    def format_report(self) -> str:
        """
        格式化报告为人类可读字符串

        Returns:
            格式化的报告字符串
        """
        report = self.get_report()
        lines = [
            "╭─────────────────────────────────────────╮",
            "│         Context Budget Report           │",
            "├─────────────────────────────────────────┤",
        ]

        for layer, usage in report.layers.items():
            bar_len = 20
            filled = int(usage.usage_ratio * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            status = "⚠️" if usage.usage_ratio > 0.9 else "✅"
            lines.append(
                f"│ {layer[:15]:<15} [{bar}] {usage.allocated:>4}/{usage.limit:<4} {status} │"
            )

        lines.append("├─────────────────────────────────────────┤")
        total_bar_len = 20
        total_filled = int(report.total_usage_ratio * total_bar_len)
        total_bar = "█" * total_filled + "░" * (total_bar_len - total_filled)
        total_status = "🔴" if report.is_over_budget else "✅"
        lines.append(
            f"│ {'TOTAL':<15} [{total_bar}] {report.total_allocated:>4}/{report.total_limit:<4} {total_status} │"
        )
        lines.append("╰─────────────────────────────────────────╯")

        return "\n".join(lines)


# ===== 模块级便捷函数 =====

_default_manager: Optional[ContextBudgetManager] = None
_manager_lock = threading.Lock()


def get_budget_manager() -> ContextBudgetManager:
    """获取默认的预算管理器单例"""
    global _default_manager
    if _default_manager is None:
        with _manager_lock:
            if _default_manager is None:
                _default_manager = ContextBudgetManager()
    return _default_manager


def reset_budget_manager() -> None:
    """重置默认预算管理器（用于测试）"""
    global _default_manager
    with _manager_lock:
        _default_manager = None
