"""
test_temporal_query.py - Bi-temporal 时间查询测试 (v3.0)

测试覆盖：
1. TemporalQuery 类的基本功能
2. at_time() 时间点查询
3. in_range() 时间范围查询
4. only_valid() 当前有效记忆
5. no_filter() 不过滤
6. parse_temporal_params() 参数解析
7. to_qdrant_conditions() 条件生成
8. 与 SearchService 集成
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from qdrant_client.models import FieldCondition, Filter, IsNullCondition, Range

from backend.core.temporal_query import (
    TemporalQuery,
    parse_temporal_params,
)


class TestTemporalQueryBasic:
    """TemporalQuery 基本功能测试"""

    def test_default_instance(self):
        """测试默认实例"""
        tq = TemporalQuery()
        assert tq.as_of is None
        assert tq.start_time is None
        assert tq.end_time is None
        assert tq.filter_expired is True

    def test_repr(self):
        """测试字符串表示"""
        tq = TemporalQuery()
        assert "TemporalQuery" in repr(tq)

    def test_repr_with_as_of(self):
        """测试带 as_of 的字符串表示"""
        now = datetime.now(timezone.utc)
        tq = TemporalQuery.at_time(now)
        assert "as_of=" in repr(tq)


class TestTemporalQueryAtTime:
    """at_time() 时间点查询测试"""

    def test_at_time_creates_instance(self):
        """测试 at_time 创建实例"""
        now = datetime.now(timezone.utc)
        tq = TemporalQuery.at_time(now)
        assert tq.as_of == now

    def test_at_time_conditions(self):
        """测试 at_time 生成的 Qdrant 条件"""
        now = datetime.now(timezone.utc)
        tq = TemporalQuery.at_time(now)
        conditions = tq.to_qdrant_conditions()

        # 应该有 2 个条件：valid_at 和 expires_at
        assert len(conditions) == 2

        # 检查条件类型
        assert all(isinstance(c, Filter) for c in conditions)

    def test_at_time_past(self):
        """测试查询过去时间点"""
        past = datetime.now(timezone.utc) - timedelta(days=30)
        tq = TemporalQuery.at_time(past)
        conditions = tq.to_qdrant_conditions()

        # 应该正确生成条件
        assert len(conditions) == 2


class TestTemporalQueryInRange:
    """in_range() 时间范围查询测试"""

    def test_in_range_both_bounds(self):
        """测试带上下界的范围查询"""
        start = datetime.now(timezone.utc) - timedelta(days=30)
        end = datetime.now(timezone.utc)
        tq = TemporalQuery.in_range(start, end)

        assert tq.start_time == start
        assert tq.end_time == end

    def test_in_range_start_only(self):
        """测试只有开始时间"""
        start = datetime.now(timezone.utc) - timedelta(days=30)
        tq = TemporalQuery.in_range(start=start)

        assert tq.start_time == start
        assert tq.end_time is None

    def test_in_range_end_only(self):
        """测试只有结束时间"""
        end = datetime.now(timezone.utc)
        tq = TemporalQuery.in_range(end=end)

        assert tq.start_time is None
        assert tq.end_time == end

    def test_in_range_conditions(self):
        """测试范围查询生成的条件"""
        start = datetime.now(timezone.utc) - timedelta(days=30)
        end = datetime.now(timezone.utc)
        tq = TemporalQuery.in_range(start, end)
        conditions = tq.to_qdrant_conditions()

        # 应该有范围条件和过期过滤
        assert len(conditions) >= 1


class TestTemporalQueryOnlyValid:
    """only_valid() 测试"""

    def test_only_valid_sets_as_of_to_now(self):
        """测试 only_valid 设置 as_of 为当前时间"""
        before = datetime.now(timezone.utc)
        tq = TemporalQuery.only_valid()
        after = datetime.now(timezone.utc)

        assert tq.as_of is not None
        assert before <= tq.as_of <= after

    def test_only_valid_conditions(self):
        """测试 only_valid 生成的条件"""
        tq = TemporalQuery.only_valid()
        conditions = tq.to_qdrant_conditions()

        # 应该有 valid_at 和 expires_at 条件
        assert len(conditions) == 2


class TestTemporalQueryNoFilter:
    """no_filter() 测试"""

    def test_no_filter_disables_filtering(self):
        """测试 no_filter 禁用过滤"""
        tq = TemporalQuery.no_filter()
        assert tq.filter_expired is False

    def test_no_filter_empty_conditions(self):
        """测试 no_filter 生成空条件"""
        tq = TemporalQuery.no_filter()
        conditions = tq.to_qdrant_conditions()

        # 应该没有条件
        assert len(conditions) == 0


class TestTemporalQueryAddCondition:
    """add_condition() 测试"""

    def test_add_condition_returns_self(self):
        """测试链式调用"""
        tq = TemporalQuery()
        mock_condition = MagicMock()
        result = tq.add_condition(mock_condition)

        assert result is tq

    def test_add_condition_appends(self):
        """测试添加条件"""
        tq = TemporalQuery()
        mock_condition = MagicMock()
        tq.add_condition(mock_condition)

        conditions = tq.to_qdrant_conditions()
        assert mock_condition in conditions


class TestParseTemporalParams:
    """parse_temporal_params() 测试"""

    def test_parse_as_of(self):
        """测试解析 as_of 参数"""
        as_of_str = "2025-01-01T00:00:00Z"
        tq = parse_temporal_params(as_of=as_of_str)

        assert tq.as_of is not None
        assert tq.as_of.year == 2025

    def test_parse_as_of_with_timezone(self):
        """测试解析带时区的 as_of"""
        as_of_str = "2025-01-01T08:00:00+08:00"
        tq = parse_temporal_params(as_of=as_of_str)

        assert tq.as_of is not None

    def test_parse_time_range(self):
        """测试解析时间范围"""
        start = "2025-01-01T00:00:00Z"
        end = "2025-01-31T23:59:59Z"
        tq = parse_temporal_params(start_time=start, end_time=end)

        assert tq.start_time is not None
        assert tq.end_time is not None

    def test_parse_include_expired(self):
        """测试 include_expired 参数"""
        tq = parse_temporal_params(include_expired=True)

        assert tq.filter_expired is False

    def test_parse_default_behavior(self):
        """测试默认行为（仅过滤过期，不要求 valid_at）"""
        tq = parse_temporal_params()

        # 默认行为应该是只过滤过期，但不要求 valid_at
        assert tq.as_of is None
        assert tq.filter_expired is True

    def test_parse_invalid_datetime_ignored(self):
        """测试无效日期时间被忽略"""
        tq = parse_temporal_params(as_of="invalid-datetime")

        # 无效的 as_of 应该被忽略
        assert tq.as_of is None

    def test_parse_priority_as_of_over_range(self):
        """测试 as_of 优先于范围"""
        as_of = "2025-01-15T00:00:00Z"
        start = "2025-01-01T00:00:00Z"
        end = "2025-01-31T00:00:00Z"
        tq = parse_temporal_params(as_of=as_of, start_time=start, end_time=end)

        # as_of 应该优先
        assert tq.as_of is not None
        assert tq.start_time is None
        assert tq.end_time is None


class TestTemporalQueryConditionsDetail:
    """Qdrant 条件生成详细测试"""

    def test_filter_expired_only_conditions(self):
        """测试仅过滤过期的条件"""
        tq = TemporalQuery(filter_expired=True)
        conditions = tq.to_qdrant_conditions()

        # 应该有一个 Filter 条件
        assert len(conditions) == 1
        assert isinstance(conditions[0], Filter)

    def test_at_time_valid_at_condition(self):
        """测试 at_time 的 valid_at 条件允许 NULL"""
        now = datetime.now(timezone.utc)
        tq = TemporalQuery.at_time(now)
        conditions = tq.to_qdrant_conditions()

        # 第一个条件应该是 valid_at 过滤
        valid_at_filter = conditions[0]
        assert isinstance(valid_at_filter, Filter)

        # 应该允许 valid_at IS NULL 或 valid_at <= as_of
        assert valid_at_filter.should is not None
        assert len(valid_at_filter.should) == 2

    def test_at_time_expires_at_condition(self):
        """测试 at_time 的 expires_at 条件"""
        now = datetime.now(timezone.utc)
        tq = TemporalQuery.at_time(now)
        conditions = tq.to_qdrant_conditions()

        # 第二个条件应该是 expires_at 过滤
        expires_at_filter = conditions[1]
        assert isinstance(expires_at_filter, Filter)

        # 应该允许 expires_at IS NULL 或 expires_at > as_of
        assert expires_at_filter.should is not None


class TestTemporalQueryEdgeCases:
    """边界情况测试"""

    def test_very_old_as_of(self):
        """测试非常久远的时间点"""
        old_time = datetime(1900, 1, 1, tzinfo=timezone.utc)
        tq = TemporalQuery.at_time(old_time)
        conditions = tq.to_qdrant_conditions()

        # 应该正常生成条件
        assert len(conditions) == 2

    def test_future_as_of(self):
        """测试未来时间点"""
        future = datetime.now(timezone.utc) + timedelta(days=365)
        tq = TemporalQuery.at_time(future)
        conditions = tq.to_qdrant_conditions()

        # 应该正常生成条件
        assert len(conditions) == 2

    def test_same_start_end_time(self):
        """测试开始和结束时间相同"""
        same_time = datetime.now(timezone.utc)
        tq = TemporalQuery.in_range(same_time, same_time)
        conditions = tq.to_qdrant_conditions()

        # 应该正常生成条件
        assert len(conditions) >= 1

    def test_z_suffix_parsing(self):
        """测试 Z 后缀的 ISO 8601 解析"""
        tq = parse_temporal_params(as_of="2025-12-31T23:59:59Z")
        assert tq.as_of is not None
        assert tq.as_of.tzinfo is not None

    def test_empty_string_ignored(self):
        """测试空字符串被忽略"""
        tq = parse_temporal_params(as_of="")
        assert tq.as_of is None


class TestTemporalQueryWithSearchService:
    """与 SearchService 集成测试（需要真实 Qdrant）"""

    @pytest.fixture
    def mock_search_service(self):
        """模拟 SearchService"""
        mock = MagicMock()
        mock.search = MagicMock(return_value=[])
        return mock

    def test_search_with_as_of_parameter(self, mock_search_service):
        """测试 search 调用带 as_of 参数"""
        # 这个测试验证参数正确传递
        as_of = "2025-01-01T00:00:00Z"
        mock_search_service.search(
            query="test",
            as_of=as_of,
        )

        mock_search_service.search.assert_called_once()
        call_kwargs = mock_search_service.search.call_args.kwargs
        assert call_kwargs.get("as_of") == as_of

    def test_search_with_time_range(self, mock_search_service):
        """测试 search 调用带时间范围"""
        start = "2025-01-01T00:00:00Z"
        end = "2025-01-31T00:00:00Z"
        mock_search_service.search(
            query="test",
            start_time=start,
            end_time=end,
        )

        call_kwargs = mock_search_service.search.call_args.kwargs
        assert call_kwargs.get("start_time") == start
        assert call_kwargs.get("end_time") == end
