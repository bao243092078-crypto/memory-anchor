"""
Tests for EventLog - L2 Episodic Memory

测试事件日志（情景记忆）功能：
- EventLog 数据模型
- MemoryKernel 的 log_event/search_events/promote_event_to_fact 方法
"""

from datetime import datetime, timedelta
from uuid import UUID

import pytest

from backend.models.event_log import (
    EventLog,
    EventLogCreate,
    EventLogResponse,
    PromoteToFactRequest,
)


class TestEventLogModel:
    """测试 EventLog 数据模型"""

    def test_create_basic_event(self):
        """测试创建基本事件"""
        event = EventLog(
            content="患者今天在花园散步",
        )

        assert event.content == "患者今天在花园散步"
        assert event.source == "ai"
        assert event.confidence == 0.8
        assert event.promoted_to_fact is False
        assert isinstance(event.id, UUID)
        assert isinstance(event.when, datetime)

    def test_create_event_with_metadata(self):
        """测试创建带元数据的事件"""
        event_time = datetime(2025, 12, 15, 10, 30)
        event = EventLog(
            content="患者见到了老朋友张三",
            when=event_time,
            where="社区公园",
            who=["张三", "李四"],
            category="event",
            source="caregiver",
        )

        assert event.when == event_time
        assert event.where == "社区公园"
        assert event.who == ["张三", "李四"]
        assert event.category == "event"
        assert event.source == "caregiver"

    def test_event_with_ttl(self):
        """测试带 TTL 的事件"""
        event = EventLog(
            content="临时活动安排",
            ttl_days=7,
        )

        assert event.ttl_days == 7
        expires = event.compute_expires_at()
        assert expires is not None
        # 验证过期时间大约是 7 天后
        expected_expires = event.when + timedelta(days=7)
        assert abs((expires - expected_expires).total_seconds()) < 1

    def test_event_without_ttl(self):
        """测试无 TTL 的事件（永久保留）"""
        event = EventLog(
            content="重要事件",
            ttl_days=None,
        )

        assert event.ttl_days is None
        assert event.compute_expires_at() is None

    def test_event_confidence_range(self):
        """测试置信度范围"""
        # 正常范围
        event = EventLog(content="测试", confidence=0.95)
        assert event.confidence == 0.95

        # 边界值
        event_min = EventLog(content="测试", confidence=0.0)
        assert event_min.confidence == 0.0

        event_max = EventLog(content="测试", confidence=1.0)
        assert event_max.confidence == 1.0

    def test_event_promoted_flag(self):
        """测试提升标记"""
        event = EventLog(content="测试事件")
        assert event.promoted_to_fact is False
        assert event.promoted_at is None
        assert event.promoted_fact_id is None


class TestEventLogCreate:
    """测试 EventLogCreate 请求模型"""

    def test_create_request_minimal(self):
        """测试最小创建请求"""
        request = EventLogCreate(content="测试事件")
        assert request.content == "测试事件"
        assert request.source == "ai"
        assert request.confidence == 0.8

    def test_create_request_full(self):
        """测试完整创建请求"""
        request = EventLogCreate(
            content="完整测试事件",
            when=datetime(2025, 12, 15, 10, 0),
            where="测试地点",
            who=["人物1", "人物2"],
            source="user",
            category="event",
            ttl_days=30,
            confidence=0.9,
        )

        assert request.content == "完整测试事件"
        assert request.where == "测试地点"
        assert request.who == ["人物1", "人物2"]
        assert request.ttl_days == 30
        assert request.confidence == 0.9


class TestEventLogResponse:
    """测试 EventLogResponse 响应模型"""

    def test_response_from_event(self):
        """测试从 EventLog 创建响应"""
        event = EventLog(
            content="测试事件",
            where="测试地点",
            who=["张三"],
        )

        response = EventLogResponse(
            id=event.id,
            content=event.content,
            when=event.when,
            where=event.where,
            who=event.who,
            source=event.source,
            category=event.category,
            ttl_days=event.ttl_days,
            expires_at=event.expires_at,
            promoted_to_fact=event.promoted_to_fact,
            promoted_at=event.promoted_at,
            confidence=event.confidence,
            created_at=event.created_at,
        )

        assert response.id == event.id
        assert response.content == event.content
        assert response.where == event.where


class TestPromoteToFactRequest:
    """测试 PromoteToFactRequest 模型"""

    def test_promote_request_minimal(self):
        """测试最小提升请求"""
        from uuid import uuid4

        event_id = uuid4()
        request = PromoteToFactRequest(event_id=event_id)
        assert request.event_id == event_id
        assert request.verified_by == "caregiver"
        assert request.notes is None

    def test_promote_request_full(self):
        """测试完整提升请求"""
        from uuid import uuid4

        event_id = uuid4()
        request = PromoteToFactRequest(
            event_id=event_id,
            verified_by="family_member",
            notes="经女儿确认属实",
        )

        assert request.event_id == event_id
        assert request.verified_by == "family_member"
        assert request.notes == "经女儿确认属实"


class TestMemoryKernelEventMethods:
    """测试 MemoryKernel 的事件相关方法"""

    @pytest.fixture
    def kernel(self):
        """获取 MemoryKernel 实例"""
        from backend.core.memory_kernel import get_memory_kernel

        return get_memory_kernel()

    def test_log_event_basic(self, kernel):
        """测试记录基本事件"""
        result = kernel.log_event(
            content="测试事件：患者今天情绪良好",
        )

        assert "id" in result
        assert result["layer"] == "event_log"
        assert "when" in result  # 事件时间
        assert result["status"] == "saved"

    def test_log_event_with_metadata(self, kernel):
        """测试记录带元数据的事件"""
        event_time = datetime.now()
        result = kernel.log_event(
            content="患者在花园遇到老朋友",
            when=event_time,
            where="社区花园",
            who=["张三"],
            category="event",
        )

        assert "id" in result
        assert result["where"] == "社区花园"
        assert result["who"] == ["张三"]

    def test_search_events_basic(self, kernel):
        """测试搜索事件"""
        # 先记录一个事件
        kernel.log_event(
            content="测试搜索：患者喜欢在阳台晒太阳",
            category="routine",
        )

        # 搜索
        results = kernel.search_events(query="阳台晒太阳", limit=5)

        # 应该能找到
        assert isinstance(results, list)
        # 由于是语义搜索，不保证一定能找到，但格式应该正确
        for r in results:
            assert "id" in r
            assert "content" in r

    def test_search_events_with_filters(self, kernel):
        """测试带过滤条件的搜索"""
        # 记录带地点的事件
        kernel.log_event(
            content="在医院做检查",
            where="市中心医院",
        )

        # 按地点过滤搜索
        results = kernel.search_events(
            query="检查",
            where="市中心医院",
            limit=5,
        )

        assert isinstance(results, list)


class TestEventLogUseCases:
    """测试 EventLog 实际使用场景"""

    @pytest.fixture
    def kernel(self):
        """获取 MemoryKernel 实例"""
        from backend.core.memory_kernel import get_memory_kernel

        return get_memory_kernel()

    def test_daily_activity_logging(self, kernel):
        """测试日常活动记录"""
        # 记录一天的活动
        activities = [
            ("早上吃了鸡蛋和牛奶", "家里", None),
            ("上午在花园散步半小时", "社区花园", None),
            ("中午女儿来探望", "家里", ["女儿"]),
            ("下午看了电视剧", "家里", None),
        ]

        for content, where, who in activities:
            result = kernel.log_event(
                content=content,
                where=where,
                who=who,
                category="routine",
            )
            assert "id" in result

    def test_medical_event_logging(self, kernel):
        """测试医疗事件记录"""
        result = kernel.log_event(
            content="今天按时服用了降压药",
            category="item",
            source="caregiver",
            confidence=0.95,
        )

        assert result["confidence"] == 0.95
        assert result["status"] == "saved"
        assert "id" in result

    def test_social_interaction_logging(self, kernel):
        """测试社交活动记录"""
        result = kernel.log_event(
            content="患者认出了老朋友张三，并聊了旧事",
            where="社区活动中心",
            who=["张三"],
            category="event",
            confidence=0.9,
        )

        assert "张三" in result.get("who", [])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
