#!/usr/bin/env python3
"""
Gating Hook 测试

验证高风险操作拦截机制。
"""

import pytest

from backend.hooks.gating_hook import (
    CONFIRMATION_PHRASES,
    HIGH_RISK_OPERATIONS,
    evaluate_risk,
    gate_operation,
    is_confirmation_present,
)


class TestIsConfirmationPresent:
    """确认短语检测测试"""

    def test_empty_message(self):
        """空消息返回 False"""
        assert is_confirmation_present(None) is False
        assert is_confirmation_present("") is False

    def test_confirmation_phrases_chinese(self):
        """中文确认短语"""
        assert is_confirmation_present("确认删除") is True
        assert is_confirmation_present("我确认这个操作") is True
        assert is_confirmation_present("请确认执行") is True

    def test_confirmation_phrases_english(self):
        """英文确认短语"""
        assert is_confirmation_present("confirm delete") is True
        assert is_confirmation_present("I confirm this action") is True
        assert is_confirmation_present("CONFIRM DELETE") is True  # 大小写不敏感

    def test_no_confirmation(self):
        """无确认短语"""
        assert is_confirmation_present("请帮我删除这个记忆") is False
        assert is_confirmation_present("delete this memory") is False
        assert is_confirmation_present("yes") is False


class TestEvaluateRisk:
    """风险评估测试"""

    def test_high_risk_operations(self):
        """高风险操作识别"""
        risk_level, description = evaluate_risk("delete_memory", {})
        assert risk_level == "critical"
        assert "删除记忆" in description

    def test_clear_operations(self):
        """清除操作识别"""
        risk_level, description = evaluate_risk("clear_active_context", {})
        assert risk_level == "high"
        assert "清除" in description

    def test_constitution_delete(self):
        """宪法层删除识别"""
        risk_level, description = evaluate_risk(
            "propose_constitution_change",
            {"change_type": "delete"},
        )
        assert risk_level == "critical"
        assert "宪法层" in description

    def test_safe_operations(self):
        """安全操作返回 None"""
        risk_level, description = evaluate_risk("search_memory", {})
        assert risk_level is None
        assert description is None

        risk_level, description = evaluate_risk("add_memory", {})
        assert risk_level is None
        assert description is None


class TestGateOperation:
    """门控操作测试"""

    def test_safe_operation_allowed(self):
        """安全操作直接放行"""
        result = gate_operation("search_memory", {}, user_message="搜索记忆")
        assert result["allowed"] is True
        assert result["requires_confirmation"] is False

    def test_high_risk_without_confirmation_blocked(self):
        """高风险操作无确认被拦截"""
        result = gate_operation(
            "delete_memory",
            {"note_id": "test-id"},
            user_message="请删除这个记忆",
        )
        assert result["allowed"] is False
        assert result["requires_confirmation"] is True
        assert result["confirmation_message"] is not None
        assert "高风险操作" in result["confirmation_message"]

    def test_high_risk_with_confirmation_allowed(self):
        """高风险操作有确认放行"""
        result = gate_operation(
            "delete_memory",
            {"note_id": "test-id"},
            user_message="我确认删除这个记忆",
        )
        assert result["allowed"] is True
        assert result["reason"] == "用户已确认"

    def test_constitution_delete_without_confirmation(self):
        """宪法层删除无确认被拦截"""
        result = gate_operation(
            "propose_constitution_change",
            {"change_type": "delete", "target_id": "test-id"},
            user_message="删除这条宪法",
        )
        assert result["allowed"] is False
        assert "宪法层" in str(result.get("confirmation_message", ""))

    def test_constitution_delete_with_confirmation(self):
        """宪法层删除有确认放行"""
        result = gate_operation(
            "propose_constitution_change",
            {"change_type": "delete", "target_id": "test-id"},
            user_message="确认删除这条宪法",
        )
        assert result["allowed"] is True

    def test_confirmation_message_format(self):
        """确认消息格式检查"""
        result = gate_operation(
            "delete_memory",
            {"note_id": "test-uuid-12345"},
            user_message="delete",
        )
        msg = result["confirmation_message"]
        assert "高风险操作警告" in msg
        assert "note_id" in msg
        assert "确认删除" in msg  # 提示用户如何确认
