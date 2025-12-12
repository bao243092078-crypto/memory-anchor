"""Constitution API - 宪法层变更接口

实现三次审批机制：
1. propose: 提议变更，进入 pending 队列
2. approve: 审批变更，approvals_count +1
3. 当 approvals_count >= 3 时，自动应用到宪法层
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from backend.models.constitution_change import (
    ChangeStatus,
    ConstitutionApproveRequest,
    ConstitutionChangeListResponse,
    ConstitutionChangeResponse,
    ConstitutionProposeRequest,
)
from backend.services.constitution import get_constitution_service

router = APIRouter(prefix="/constitution", tags=["constitution"])


@router.post("/propose", response_model=ConstitutionChangeResponse, status_code=201)
async def propose_change(request: ConstitutionProposeRequest) -> ConstitutionChangeResponse:
    """
    提议宪法层变更

    - **change_type**: 变更类型（create/update/delete）
    - **proposed_content**: 提议的内容
    - **reason**: 变更理由（必填）
    - **target_id**: 目标条目ID（update/delete时需要）
    - **category**: 分类（person/place/event/item/routine）

    返回：变更记录，状态为 pending
    """
    service = get_constitution_service()
    return await service.propose(request)


@router.post("/approve/{change_id}", response_model=ConstitutionChangeResponse)
async def approve_change(
    change_id: UUID,
    request: ConstitutionApproveRequest = ConstitutionApproveRequest(),
) -> ConstitutionChangeResponse:
    """
    审批宪法层变更

    每次调用 approvals_count +1。
    当 approvals_count >= 3 时，自动应用变更到宪法层。

    - **approver**: 审批人标识
    - **comment**: 审批备注（可选）

    返回：更新后的变更记录
    """
    service = get_constitution_service()
    try:
        return await service.approve(change_id, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pending", response_model=list[ConstitutionChangeResponse])
async def list_pending_changes() -> list[ConstitutionChangeResponse]:
    """
    获取所有待审批的宪法变更

    返回 status=pending 的所有变更记录，按创建时间降序排列
    """
    service = get_constitution_service()
    return await service.get_pending()


@router.get("/changes", response_model=ConstitutionChangeListResponse)
async def list_changes(
    status: ChangeStatus | None = Query(default=None, description="按状态过滤"),
    limit: int = Query(default=20, ge=1, le=100, description="返回数量限制"),
) -> ConstitutionChangeListResponse:
    """
    获取宪法变更历史

    - **status**: 按状态过滤（pending/approved/applied/rejected/expired）
    - **limit**: 返回数量限制
    """
    service = get_constitution_service()
    changes = await service.list_changes(status=status, limit=limit)
    pending = await service.get_pending()

    return ConstitutionChangeListResponse(
        changes=changes,
        total=len(changes),
        pending_count=len(pending),
    )


@router.get("/changes/{change_id}", response_model=ConstitutionChangeResponse)
async def get_change(change_id: UUID) -> ConstitutionChangeResponse:
    """
    获取单个宪法变更记录
    """
    service = get_constitution_service()
    change = await service.get_change(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="变更记录不存在")
    return change
