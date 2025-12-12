"""Note and Reminder data models - 便利贴与提醒数据模型"""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class MemoryLayer(str, Enum):
    """三层记忆模型"""

    CONSTITUTION = "constitution"  # 宪法层：核心身份，永不过期
    FACT = "fact"  # 事实层：长期记忆，可过期
    SESSION = "session"  # 会话层：短期对话，24h归档


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
    layer: MemoryLayer = Field(default=MemoryLayer.FACT, description="记忆层级")
    category: NoteCategory | None = Field(default=None, description="分类")
    priority: int = Field(default=100, ge=0, le=999, description="优先级，0=最高")
    expires_at: datetime | None = Field(default=None, description="过期时间")


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
