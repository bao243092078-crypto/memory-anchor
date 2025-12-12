"""Constitution Change data models - 宪法层变更数据模型

实现三次审批机制的数据结构。
基于 docs/MEMORY_STRATEGY.md 的宪法层修改规则。
"""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ChangeType(str, Enum):
    """变更类型"""
    CREATE = "create"  # 新增宪法条目
    UPDATE = "update"  # 修改现有条目
    DELETE = "delete"  # 删除条目


class ChangeStatus(str, Enum):
    """变更状态"""
    PENDING = "pending"  # 等待审批（0-2次确认）
    APPROVED = "approved"  # 已审批（3次确认）
    APPLIED = "applied"  # 已应用到宪法层
    REJECTED = "rejected"  # 被拒绝
    EXPIRED = "expired"  # 超时未审批


# --- Request Models ---


class ConstitutionProposeRequest(BaseModel):
    """提议宪法变更请求"""

    change_type: ChangeType = Field(
        default=ChangeType.CREATE,
        description="变更类型：create/update/delete"
    )
    proposed_content: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="提议的内容（新增或修改后的内容）"
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="变更理由"
    )
    target_id: UUID | None = Field(
        default=None,
        description="目标条目ID（update/delete时必填）"
    )
    category: str | None = Field(
        default=None,
        description="分类：person/place/event/item/routine"
    )


class ConstitutionApproveRequest(BaseModel):
    """审批宪法变更请求"""

    approver: str = Field(
        default="cli_user",
        description="审批人标识"
    )
    comment: str | None = Field(
        default=None,
        description="审批备注"
    )


# --- Response Models ---


class ConstitutionChangeResponse(BaseModel):
    """宪法变更响应"""

    id: UUID = Field(default_factory=uuid4)
    change_type: ChangeType
    proposed_content: str
    reason: str
    target_id: UUID | None = None
    category: str | None = None

    # 审批状态
    status: ChangeStatus = ChangeStatus.PENDING
    approvals_count: int = 0
    approvals_needed: int = 3
    approvals: list[dict] = Field(default_factory=list)  # 审批记录

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    applied_at: datetime | None = None

    # 关联信息
    proposer: str = "unknown"

    model_config = ConfigDict(from_attributes=True)


class ConstitutionChangeListResponse(BaseModel):
    """宪法变更列表响应"""

    changes: list[ConstitutionChangeResponse]
    total: int
    pending_count: int
