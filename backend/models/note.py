"""Note and Reminder data models - 便利贴与提醒数据模型"""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MemoryLayer(str, Enum):
    """
    五层认知记忆模型 (v2.0)

    基于认知科学的人类记忆系统映射：
    - L0: identity_schema - 自我概念（核心身份）
    - L1: active_context - 工作记忆（会话临时状态，不持久化）
    - L2: event_log - 情景记忆（带时空标记的事件）
    - L3: verified_fact - 语义记忆（验证过的长期事实）
    - L4: operational_knowledge - 技能图式（操作性知识）
    """

    # ===== 新术语 (v2.x) =====
    IDENTITY_SCHEMA = "identity_schema"  # L0: 核心身份，仅照护者可改，需三次审批
    ACTIVE_CONTEXT = "active_context"  # L1: 会话临时状态，不持久化到 Qdrant
    EVENT_LOG = "event_log"  # L2: 带时空标记的事件，可设 TTL
    VERIFIED_FACT = "verified_fact"  # L3: 验证过的长期事实
    OPERATIONAL_KNOWLEDGE = "operational_knowledge"  # L4: 操作性知识

    # ===== 向后兼容别名 (v1.x) =====
    # Python Enum 允许相同值的别名
    CONSTITUTION = "identity_schema"  # 映射到 IDENTITY_SCHEMA
    FACT = "verified_fact"  # 映射到 VERIFIED_FACT
    SESSION = "event_log"  # 映射到 EVENT_LOG

    @classmethod
    def from_string(cls, value: str) -> "MemoryLayer":
        """
        从字符串创建 MemoryLayer，支持 v1.x 旧术语。

        Args:
            value: 层级字符串（可能是旧术语或新术语）

        Returns:
            对应的 MemoryLayer 枚举

        Raises:
            ValueError: 如果值无效
        """
        if not value:
            raise ValueError("Invalid memory layer: value cannot be None or empty")

        # v1.x → v2.x 术语映射
        aliases = {
            "constitution": "identity_schema",
            "fact": "verified_fact",
            "session": "event_log",
        }
        # 去除前后空格并转小写
        normalized = aliases.get(value.strip().lower(), value.strip().lower())
        try:
            return cls(normalized)
        except ValueError:
            raise ValueError(
                f"Invalid memory layer: '{value}'. "
                f"Valid values: identity_schema, active_context, event_log, verified_fact, operational_knowledge "
                f"(or v1.x aliases: constitution, fact, session)"
            )


class NoteCategory(str, Enum):
    """便利贴分类"""

    PERSON = "person"  # 人物
    PLACE = "place"  # 地点
    EVENT = "event"  # 事件
    ITEM = "item"  # 物品
    ROUTINE = "routine"  # 日常


# --- Request Models ---


class NoteCreate(BaseModel):
    """创建便利贴请求"""

    content: str = Field(..., min_length=1, max_length=1000, description="便利贴内容")
    layer: MemoryLayer = Field(default=MemoryLayer.VERIFIED_FACT, description="记忆层级")
    category: NoteCategory | None = Field(default=None, description="分类")
    priority: int = Field(default=100, ge=0, le=999, description="优先级，0=最高")
    expires_at: datetime | None = Field(default=None, description="过期时间")

    @field_validator("layer", mode="before")
    @classmethod
    def normalize_layer(cls, v):
        """支持 v1.x 旧术语 (constitution/fact/session)"""
        if isinstance(v, str):
            return MemoryLayer.from_string(v)
        return v


class NoteUpdate(BaseModel):
    """更新便利贴请求"""

    content: str | None = Field(default=None, min_length=1, max_length=1000)
    category: NoteCategory | None = None
    priority: int | None = Field(default=None, ge=0, le=999)
    expires_at: datetime | None = None
    is_active: bool | None = None


class ReminderCreate(BaseModel):
    """创建提醒请求"""

    note_id: UUID = Field(..., description="关联的便利贴ID")
    trigger_type: str = Field(..., description="触发类型: time/location/event")
    trigger_value: str = Field(..., description="触发值: cron表达式/geofence/关键词")
    is_recurring: bool = Field(default=False, description="是否重复")


# --- Response Models ---


class NoteResponse(BaseModel):
    """便利贴响应"""

    id: UUID = Field(default_factory=uuid4)
    content: str
    layer: MemoryLayer
    category: NoteCategory | None = None
    priority: int = 100
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    created_by: str = "caregiver"
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime | None = None
    last_verified: datetime | None = None
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class ReminderResponse(BaseModel):
    """提醒响应"""

    id: UUID = Field(default_factory=uuid4)
    note_id: UUID
    trigger_type: str
    trigger_value: str
    is_recurring: bool = False
    last_triggered: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(from_attributes=True)
