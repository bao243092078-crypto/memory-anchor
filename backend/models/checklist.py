"""
Checklist data models - 清单数据模型

与 Note 的核心区别：
- Note: 被动记忆（存储信息）
- Checklist: 主动清单（跟踪待办事项，与 Plan skill 协同）

设计原则（来自三方 AI 头脑风暴）：
- Checklist 是"战略层"（跨会话持久）
- Plan skill 是"战术层"（单次任务）
- 通过 (ma:xxx) ID 机制连接两者
"""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ChecklistStatus(str, Enum):
    """清单项状态"""
    OPEN = "open"           # 待办
    DONE = "done"           # 已完成
    SNOOZED = "snoozed"     # 暂缓


class ChecklistScope(str, Enum):
    """清单作用域"""
    PROJECT = "project"     # 项目级
    REPO = "repo"           # 仓库级
    GLOBAL = "global"       # 全局


class ChecklistPriority(int, Enum):
    """清单优先级"""
    CRITICAL = 1    # 紧急
    HIGH = 2        # 高
    NORMAL = 3      # 普通
    LOW = 4         # 低
    BACKLOG = 5     # 待定


# === Request Models ===


class ChecklistItemCreate(BaseModel):
    """创建清单项请求"""

    content: str = Field(..., min_length=1, max_length=500, description="清单内容")
    status: ChecklistStatus = Field(default=ChecklistStatus.OPEN, description="状态")
    scope: ChecklistScope = Field(default=ChecklistScope.PROJECT, description="作用域")
    priority: ChecklistPriority = Field(default=ChecklistPriority.NORMAL, description="优先级")
    tags: list[str] = Field(default_factory=list, description="标签")
    ttl_days: int | None = Field(default=None, ge=1, description="存活天数（可选）")
    project_id: str | None = Field(default=None, description="项目 ID")


class ChecklistItemUpdate(BaseModel):
    """更新清单项请求"""

    content: str | None = Field(default=None, min_length=1, max_length=500)
    status: ChecklistStatus | None = None
    priority: ChecklistPriority | None = None
    tags: list[str] | None = None
    ttl_days: int | None = Field(default=None, ge=1, description="存活天数（可选）")


class ChecklistBriefingRequest(BaseModel):
    """获取清单简报请求"""

    project_id: str = Field(..., description="项目 ID")
    scope: ChecklistScope | None = Field(default=None, description="作用域过滤")
    limit: int = Field(default=12, ge=1, le=50, description="返回数量限制")
    include_ids: bool = Field(default=True, description="是否包含 (ma:xxx) ID")
    format: str = Field(default="markdown", description="输出格式")


class PlanSyncRequest(BaseModel):
    """Plan 同步请求（从 plan.md 回写）"""

    project_id: str = Field(..., description="项目 ID")
    session_id: str = Field(..., description="会话 ID")
    plan_markdown: str = Field(..., description="plan.md 内容")
    create_policy: str = Field(default="tag:@persist", description="创建策略")
    complete_policy: str = Field(default="checked_box_with_id", description="完成策略")


# === Response Models ===


class ChecklistItemResponse(BaseModel):
    """清单项响应"""

    id: UUID = Field(default_factory=uuid4)
    content: str
    status: ChecklistStatus = ChecklistStatus.OPEN
    scope: ChecklistScope = ChecklistScope.PROJECT
    priority: ChecklistPriority = ChecklistPriority.NORMAL
    tags: list[str] = Field(default_factory=list)
    project_id: str | None = None

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    expires_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    def short_id(self) -> str:
        """返回短 ID（用于 plan.md 引用）"""
        return str(self.id)[:8]

    def ma_ref(self) -> str:
        """返回 Memory Anchor 引用格式"""
        return f"(ma:{self.short_id()})"


class SyncedItemInfo(BaseModel):
    """同步的清单项信息（用于 PlanSyncResponse）"""

    id: str = Field(..., description="清单项 ID")
    content: str = Field(..., description="清单内容")
    ma_ref: str = Field(..., description="Memory Anchor 引用格式 (ma:xxxxxxxx)")


class PlanSyncResponse(BaseModel):
    """Plan 同步响应"""

    completed: list[str] = Field(default_factory=list, description="标记完成的项目 ID")
    created: list[SyncedItemInfo] = Field(default_factory=list, description="新创建的项目")
    updated: list[SyncedItemInfo] = Field(default_factory=list, description="更新的项目")
    warnings: list[str] = Field(default_factory=list, description="警告信息")


# === 导出 ===

__all__ = [
    "ChecklistStatus",
    "ChecklistScope",
    "ChecklistPriority",
    "ChecklistItemCreate",
    "ChecklistItemUpdate",
    "ChecklistItemResponse",
    "ChecklistBriefingRequest",
    "PlanSyncRequest",
    "PlanSyncResponse",
    "SyncedItemInfo",
]
