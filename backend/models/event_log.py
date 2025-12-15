"""
EventLog Model - L2 情景记忆

基于认知科学的情景记忆（Episodic Memory）概念：
- 带时空标记的经历记录（when/where/who）
- 可设置 TTL 自动过期
- 可提升为 verified_fact 层
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class EventLog(BaseModel):
    """
    L2: 事件日志（情景记忆）

    情景记忆的核心特征（来自认知科学）：
    - 时间标记（when）：事件发生的时间
    - 空间标记（where）：事件发生的地点
    - 参与者（who）：涉及的人物

    生命周期：
    - 默认存储在 Qdrant 的 event_log 层
    - 可设置 TTL 自动过期
    - 重要事件可提升为 verified_fact 层
    """

    id: UUID = Field(default_factory=uuid4, description="事件唯一标识")
    content: str = Field(..., min_length=1, max_length=2000, description="事件内容描述")

    # ===== 时空元数据（情景记忆核心） =====
    when: datetime = Field(default_factory=datetime.now, description="事件发生时间")
    where: Optional[str] = Field(default=None, max_length=200, description="事件发生地点")
    who: list[str] = Field(default_factory=list, description="涉及的人物列表")

    # ===== 来源和分类 =====
    source: str = Field(
        default="ai",
        description="事件来源: ai=AI提取, user=用户输入, caregiver=照护者记录",
    )
    category: Optional[str] = Field(
        default=None,
        description="事件分类: person/place/event/item/routine",
    )

    # ===== 生命周期管理 =====
    ttl_days: Optional[int] = Field(
        default=None,
        ge=1,
        description="存活天数，None=永久保留",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="计算后的过期时间（自动填充）",
    )

    # ===== 提升规则 =====
    promoted_to_fact: bool = Field(
        default=False,
        description="是否已提升为 verified_fact 层",
    )
    promoted_at: Optional[datetime] = Field(
        default=None,
        description="提升时间",
    )
    promoted_fact_id: Optional[UUID] = Field(
        default=None,
        description="提升后的 verified_fact 记录 ID",
    )

    # ===== 元数据 =====
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="置信度（AI提取时自动设置）",
    )
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    def compute_expires_at(self) -> Optional[datetime]:
        """根据 ttl_days 计算过期时间"""
        if self.ttl_days is None:
            return None
        from datetime import timedelta

        return self.when + timedelta(days=self.ttl_days)


class EventLogCreate(BaseModel):
    """创建事件日志请求"""

    content: str = Field(..., min_length=1, max_length=2000, description="事件内容")
    when: Optional[datetime] = Field(default=None, description="事件时间（默认当前）")
    where: Optional[str] = Field(default=None, max_length=200, description="事件地点")
    who: list[str] = Field(default_factory=list, description="涉及的人物")
    source: str = Field(default="ai", description="来源")
    category: Optional[str] = Field(default=None, description="分类")
    ttl_days: Optional[int] = Field(default=None, ge=1, description="存活天数")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="置信度")


class EventLogResponse(BaseModel):
    """事件日志响应"""

    id: UUID
    content: str
    when: datetime
    where: Optional[str]
    who: list[str]
    source: str
    category: Optional[str]
    ttl_days: Optional[int]
    expires_at: Optional[datetime]
    promoted_to_fact: bool
    promoted_at: Optional[datetime]
    confidence: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromoteToFactRequest(BaseModel):
    """提升事件为事实层请求"""

    event_id: UUID = Field(..., description="要提升的事件 ID")
    verified_by: str = Field(default="caregiver", description="验证者")
    notes: Optional[str] = Field(default=None, description="提升备注")


__all__ = [
    "EventLog",
    "EventLogCreate",
    "EventLogResponse",
    "PromoteToFactRequest",
]
