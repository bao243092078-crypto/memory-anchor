"""
test_context_budget.py - ContextBudgetManager 测试 (v3.0)

测试覆盖：
- 基础 token 估算
- 预算分配和检查
- 截断逻辑
- 报告生成
- 环境变量配置
- 边界情况
"""

import os
import pytest
from unittest.mock import patch

from backend.core.context_budget import (
    ContextBudget,
    ContextBudgetManager,
    BudgetUsage,
    BudgetReport,
    BudgetLayer,
    get_budget_manager,
    reset_budget_manager,
)


class TestContextBudget:
    """ContextBudget 数据类测试"""

    def test_default_values(self):
        """测试默认值"""
        budget = ContextBudget()
        assert budget.l0_identity == 500
        assert budget.l1_active == 200
        assert budget.l2_events == 500
        assert budget.l3_facts == 2000
        assert budget.l4_ops == 300
        assert budget.total_limit == 4000
        assert budget.chars_per_token == 4.0
        assert budget.truncate_strategy == "tail"

    def test_custom_values(self):
        """测试自定义值"""
        budget = ContextBudget(
            l0_identity=1000,
            l3_facts=3000,
            total_limit=5000,
        )
        assert budget.l0_identity == 1000
        assert budget.l3_facts == 3000
        assert budget.total_limit == 5000

    def test_from_env(self):
        """测试从环境变量加载"""
        with patch.dict(os.environ, {
            "MA_BUDGET_L0": "600",
            "MA_BUDGET_L3": "2500",
            "MA_BUDGET_TOTAL": "5000",
        }):
            budget = ContextBudget.from_env()
            assert budget.l0_identity == 600
            assert budget.l3_facts == 2500
            assert budget.total_limit == 5000


class TestBudgetUsage:
    """BudgetUsage 数据类测试"""

    def test_usage_ratio(self):
        """测试使用率计算"""
        usage = BudgetUsage(
            layer="verified_fact",
            allocated=500,
            limit=2000,
            items_count=5,
        )
        assert usage.usage_ratio == 0.25
        assert usage.remaining == 1500

    def test_usage_ratio_zero_limit(self):
        """测试零上限情况"""
        usage = BudgetUsage(
            layer="test",
            allocated=100,
            limit=0,
            items_count=1,
        )
        assert usage.usage_ratio == 0.0

    def test_to_dict(self):
        """测试字典转换"""
        usage = BudgetUsage(
            layer="verified_fact",
            allocated=500,
            limit=2000,
            items_count=5,
            truncated=2,
        )
        d = usage.to_dict()
        assert d["layer"] == "verified_fact"
        assert d["allocated"] == 500
        assert d["limit"] == 2000
        assert d["remaining"] == 1500
        assert d["usage_ratio"] == 0.25
        assert d["items_count"] == 5
        assert d["truncated"] == 2


class TestContextBudgetManager:
    """ContextBudgetManager 测试"""

    @pytest.fixture
    def manager(self):
        """创建测试用管理器"""
        return ContextBudgetManager()

    def test_estimate_tokens_empty(self, manager):
        """测试空内容"""
        assert manager.estimate_tokens("") == 0
        assert manager.estimate_tokens(None) == 0

    def test_estimate_tokens_short(self, manager):
        """测试短内容"""
        # 4 字符 = 1 token
        assert manager.estimate_tokens("test") == 1
        # 8 字符 = 2 tokens
        assert manager.estimate_tokens("testtest") == 2

    def test_estimate_tokens_chinese(self, manager):
        """测试中文内容"""
        # 中文每个字符算 1 个字符，4 字符 = 1 token
        content = "这是测试"  # 4 个中文字符
        assert manager.estimate_tokens(content) == 1

    def test_estimate_tokens_long(self, manager):
        """测试长内容"""
        # 400 字符 = 100 tokens
        content = "a" * 400
        assert manager.estimate_tokens(content) == 100

    def test_estimate_memory_tokens(self, manager):
        """测试记忆 token 估算（含元数据开销）"""
        memory = {"content": "a" * 40}  # 10 tokens + 20 metadata = 30
        assert manager.estimate_memory_tokens(memory) == 30

    def test_can_allocate_within_limit(self, manager):
        """测试在限制内分配"""
        assert manager.can_allocate("verified_fact", 100) is True
        assert manager.can_allocate("verified_fact", 2000) is True

    def test_can_allocate_over_layer_limit(self, manager):
        """测试超过层级限制"""
        # verified_fact 默认限制 2000
        assert manager.can_allocate("verified_fact", 2001) is False

    def test_can_allocate_over_total_limit(self, manager):
        """测试超过总限制"""
        # 先分配各层接近上限
        manager.allocate("identity_schema", 500)
        manager.allocate("event_log", 500)
        manager.allocate("verified_fact", 2000)
        # 总计已用 3000，剩余 1000
        assert manager.can_allocate("operational_knowledge", 300) is True
        assert manager.can_allocate("operational_knowledge", 1001) is False

    def test_allocate_success(self, manager):
        """测试成功分配"""
        result = manager.allocate("verified_fact", 100, 5)
        assert result is True
        usage = manager.get_layer_usage("verified_fact")
        assert usage.allocated == 100
        assert usage.items_count == 5

    def test_allocate_failure(self, manager):
        """测试分配失败"""
        result = manager.allocate("verified_fact", 3000)  # 超过 2000 限制
        assert result is False
        usage = manager.get_layer_usage("verified_fact")
        assert usage.allocated == 0

    def test_truncate_to_fit_no_truncation(self, manager):
        """测试无需截断的情况"""
        memories = [
            {"content": "short", "score": 0.9},
            {"content": "also short", "score": 0.8},
        ]
        result, truncated = manager.truncate_to_fit(memories, "verified_fact")
        assert len(result) == 2
        assert truncated == 0

    def test_truncate_to_fit_with_truncation(self, manager):
        """测试需要截断的情况"""
        # 创建一个小预算管理器
        small_budget = ContextBudget(l3_facts=50)  # 只有 50 tokens
        manager = ContextBudgetManager(small_budget)

        memories = [
            {"content": "a" * 40, "score": 0.9},   # 10 + 20 = 30 tokens
            {"content": "b" * 40, "score": 0.8},   # 30 tokens, 总计 60 > 50
            {"content": "c" * 40, "score": 0.7},   # 会被截断
        ]
        result, truncated = manager.truncate_to_fit(memories, "verified_fact")
        assert len(result) == 1  # 只保留第一个
        assert truncated == 2

    def test_truncate_to_fit_sort_by_score(self, manager):
        """测试按分数排序截断"""
        small_budget = ContextBudget(l3_facts=50)
        manager = ContextBudgetManager(small_budget)

        memories = [
            {"content": "a" * 40, "score": 0.5},   # 低分
            {"content": "b" * 40, "score": 0.9},   # 高分，应该保留
            {"content": "c" * 40, "score": 0.7},   # 中分
        ]
        result, truncated = manager.truncate_to_fit(memories, "verified_fact")
        assert len(result) == 1
        assert result[0]["score"] == 0.9  # 高分的被保留

    def test_truncate_to_fit_preserve_first(self, manager):
        """测试保留前 N 条"""
        small_budget = ContextBudget(l3_facts=100)
        manager = ContextBudgetManager(small_budget)

        memories = [
            {"content": "a" * 40, "score": 0.5},
            {"content": "b" * 40, "score": 0.9},
            {"content": "c" * 40, "score": 0.7},
        ]
        # 保留前 2 条（即使超预算）
        result, truncated = manager.truncate_to_fit(
            memories, "verified_fact", preserve_first=2
        )
        assert len(result) >= 2

    def test_truncate_to_fit_empty_list(self, manager):
        """测试空列表"""
        result, truncated = manager.truncate_to_fit([], "verified_fact")
        assert result == []
        assert truncated == 0

    def test_reset(self, manager):
        """测试重置"""
        manager.allocate("verified_fact", 100)
        assert manager.get_layer_usage("verified_fact").allocated == 100

        manager.reset()
        assert manager.get_layer_usage("verified_fact").allocated == 0

    def test_get_report(self, manager):
        """测试获取报告"""
        manager.allocate("identity_schema", 100)
        manager.allocate("verified_fact", 500)

        report = manager.get_report()
        assert isinstance(report, BudgetReport)
        assert report.total_allocated == 600
        assert report.total_limit == 4000
        assert report.is_over_budget is False

    def test_get_report_over_budget(self, manager):
        """测试超预算报告"""
        # 手动设置超预算
        manager.allocate("identity_schema", 500)
        manager.allocate("active_context", 200)
        manager.allocate("event_log", 500)
        manager.allocate("verified_fact", 2000)
        manager.allocate("operational_knowledge", 300)
        # 强制超预算
        manager._usage["verified_fact"].allocated = 3000

        report = manager.get_report()
        assert report.is_over_budget is True

    def test_format_report(self, manager):
        """测试格式化报告"""
        manager.allocate("verified_fact", 500)
        report_str = manager.format_report()
        assert "Context Budget Report" in report_str
        assert "verified_fact" in report_str

    def test_unknown_layer(self, manager):
        """测试未知层级"""
        # 未知层级不限制
        assert manager.can_allocate("unknown_layer", 10000) is True


class TestBudgetReport:
    """BudgetReport 测试"""

    def test_total_usage_ratio(self):
        """测试总使用率"""
        report = BudgetReport(
            layers={},
            total_allocated=2000,
            total_limit=4000,
        )
        assert report.total_usage_ratio == 0.5

    def test_is_over_budget(self):
        """测试超预算判断"""
        report = BudgetReport(
            layers={},
            total_allocated=4001,
            total_limit=4000,
        )
        assert report.is_over_budget is True

    def test_to_dict(self):
        """测试字典转换"""
        report = BudgetReport(
            layers={},
            total_allocated=2000,
            total_limit=4000,
        )
        d = report.to_dict()
        assert d["total_allocated"] == 2000
        assert d["total_limit"] == 4000
        assert d["total_usage_ratio"] == 0.5
        assert d["is_over_budget"] is False


class TestModuleFunctions:
    """模块级函数测试"""

    def test_get_budget_manager_singleton(self):
        """测试单例模式"""
        reset_budget_manager()
        m1 = get_budget_manager()
        m2 = get_budget_manager()
        assert m1 is m2

    def test_reset_budget_manager(self):
        """测试重置单例"""
        reset_budget_manager()
        m1 = get_budget_manager()
        reset_budget_manager()
        m2 = get_budget_manager()
        assert m1 is not m2


class TestBudgetLayer:
    """BudgetLayer 枚举测试"""

    def test_layer_values(self):
        """测试层级值"""
        assert BudgetLayer.L0_IDENTITY.value == "identity_schema"
        assert BudgetLayer.L1_ACTIVE.value == "active_context"
        assert BudgetLayer.L2_EVENTS.value == "event_log"
        assert BudgetLayer.L3_FACTS.value == "verified_fact"
        assert BudgetLayer.L4_OPS.value == "operational_knowledge"
