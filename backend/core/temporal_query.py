"""
temporal_query.py - Bi-temporal 时间查询模块 (v3.0)

提供时间维度的记忆查询能力：
- at_time(t): 查询某时刻有效的记忆
- in_range(start, end): 查询时间范围内的记忆
- only_valid(): 只返回未过期的记忆

基于认知科学的时间感知设计：
- valid_at: 记忆生效时间（语义记忆的"习得时间"）
- expires_at: 记忆失效时间（类似遗忘曲线）
- created_at: 系统记录时间（日志用途）
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Union

from qdrant_client.models import (
    FieldCondition,
    Filter,
    IsNullCondition,
    PayloadField,
    Range,
)


@dataclass
class TemporalQuery:
    """
    Bi-temporal 时间查询构建器

    用于构建 Qdrant 的时间过滤条件，支持：
    - 时间点查询（as_of）
    - 时间范围查询（start_time, end_time）
    - 有效性过滤（only_valid）

    Example:
        >>> tq = TemporalQuery.at_time(datetime(2025, 1, 1))
        >>> filters = tq.to_qdrant_filter()

        >>> tq = TemporalQuery.in_range(start, end)
        >>> filters = tq.to_qdrant_filter()
    """

    # 时间点查询：查询该时刻有效的记忆
    as_of: Optional[datetime] = None

    # 时间范围查询：查询 valid_at 在此范围内的记忆
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # 有效性过滤：是否过滤已过期记忆（默认开启）
    filter_expired: bool = True

    # 额外条件
    _conditions: List[Union[FieldCondition, Filter]] = field(default_factory=list)

    @classmethod
    def at_time(cls, t: datetime) -> "TemporalQuery":
        """
        查询某时刻有效的记忆

        返回满足以下条件的记忆：
        - valid_at <= t（已生效）
        - expires_at > t 或 expires_at is None（未过期）

        Args:
            t: 查询时间点

        Returns:
            TemporalQuery 实例
        """
        return cls(as_of=t)

    @classmethod
    def in_range(
        cls,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> "TemporalQuery":
        """
        查询时间范围内的记忆

        返回 valid_at 在 [start, end] 范围内的记忆

        Args:
            start: 开始时间（包含）
            end: 结束时间（包含）

        Returns:
            TemporalQuery 实例
        """
        return cls(start_time=start, end_time=end)

    @classmethod
    def only_valid(cls) -> "TemporalQuery":
        """
        只返回当前有效的记忆

        等价于 at_time(now)

        Returns:
            TemporalQuery 实例
        """
        return cls(as_of=datetime.now(timezone.utc))

    @classmethod
    def no_filter(cls) -> "TemporalQuery":
        """
        不进行时间过滤（返回所有记忆，包括已过期）

        Returns:
            TemporalQuery 实例
        """
        return cls(filter_expired=False)

    def to_qdrant_conditions(self) -> List[Union[FieldCondition, Filter]]:
        """
        转换为 Qdrant 过滤条件列表

        Returns:
            可直接用于 Qdrant Filter.must 的条件列表
        """
        conditions: List[Union[FieldCondition, Filter]] = []

        if self.as_of is not None:
            # 时间点查询：valid_at <= as_of AND (expires_at > as_of OR expires_at IS NULL)
            as_of_ts = self.as_of.timestamp()

            # 条件1: valid_at <= as_of (已生效)
            # 注意：valid_at 可能为 None，表示立即生效（使用 created_at）
            conditions.append(
                Filter(
                    should=[
                        # valid_at 为 None（立即生效）
                        IsNullCondition(is_null=PayloadField(key="valid_at")),
                        # 或 valid_at <= as_of（已生效）
                        FieldCondition(key="valid_at", range=Range(lte=as_of_ts)),
                    ]
                )
            )

            # 条件2: expires_at > as_of OR expires_at IS NULL (未过期)
            conditions.append(
                Filter(
                    should=[
                        # expires_at 为 None（永不过期）
                        IsNullCondition(is_null=PayloadField(key="expires_at")),
                        # 或 expires_at > as_of（未过期）
                        FieldCondition(key="expires_at", range=Range(gt=as_of_ts)),
                    ]
                )
            )

        elif self.start_time is not None or self.end_time is not None:
            # 时间范围查询：start <= valid_at <= end
            range_params: dict[str, float] = {}

            if self.start_time is not None:
                range_params["gte"] = self.start_time.timestamp()
            if self.end_time is not None:
                range_params["lte"] = self.end_time.timestamp()

            if range_params:
                conditions.append(
                    FieldCondition(key="valid_at", range=Range(**range_params))
                )

            # 如果启用过期过滤，还需要过滤已过期记忆
            if self.filter_expired:
                current_ts = datetime.now(timezone.utc).timestamp()
                conditions.append(
                    Filter(
                        should=[
                            IsNullCondition(is_null=PayloadField(key="expires_at")),
                            FieldCondition(key="expires_at", range=Range(gte=current_ts)),
                        ]
                    )
                )

        elif self.filter_expired:
            # 仅过期过滤（无时间点/范围查询）
            current_ts = datetime.now(timezone.utc).timestamp()
            conditions.append(
                Filter(
                    should=[
                        IsNullCondition(is_null=PayloadField(key="expires_at")),
                        FieldCondition(key="expires_at", range=Range(gte=current_ts)),
                    ]
                )
            )

        # 添加额外条件
        conditions.extend(self._conditions)

        return conditions

    def add_condition(self, condition: Union[FieldCondition, Filter]) -> "TemporalQuery":
        """
        添加额外的过滤条件

        Args:
            condition: Qdrant 过滤条件

        Returns:
            self（支持链式调用）
        """
        self._conditions.append(condition)
        return self

    def __repr__(self) -> str:
        parts = []
        if self.as_of:
            parts.append(f"as_of={self.as_of.isoformat()}")
        if self.start_time:
            parts.append(f"start={self.start_time.isoformat()}")
        if self.end_time:
            parts.append(f"end={self.end_time.isoformat()}")
        if not self.filter_expired:
            parts.append("include_expired=True")
        return f"TemporalQuery({', '.join(parts) or 'default'})"


def parse_temporal_params(
    as_of: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    include_expired: bool = False,
) -> TemporalQuery:
    """
    从字符串参数解析 TemporalQuery

    用于 API 和 MCP 工具的参数解析

    Args:
        as_of: ISO 8601 格式的时间点
        start_time: ISO 8601 格式的开始时间
        end_time: ISO 8601 格式的结束时间
        include_expired: 是否包含已过期记忆

    Returns:
        TemporalQuery 实例
    """
    def parse_dt(s: Optional[str]) -> Optional[datetime]:
        if s is None:
            return None
        try:
            # 支持 'Z' 后缀
            return datetime.fromisoformat(s.replace('Z', '+00:00'))
        except ValueError:
            return None

    as_of_dt = parse_dt(as_of)
    start_dt = parse_dt(start_time)
    end_dt = parse_dt(end_time)

    if as_of_dt:
        return TemporalQuery.at_time(as_of_dt)
    elif start_dt or end_dt:
        tq = TemporalQuery.in_range(start_dt, end_dt)
        tq.filter_expired = not include_expired
        return tq
    elif include_expired:
        return TemporalQuery.no_filter()
    else:
        # 默认行为：仅过滤已过期记忆，不要求 valid_at 存在
        # 这保持向后兼容性（现有记忆可能没有 valid_at）
        return TemporalQuery(filter_expired=True)
