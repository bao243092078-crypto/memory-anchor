// 变更类型
export type ChangeType = 'create' | 'update' | 'delete';

// 变更状态
export type ChangeStatus = 'pending' | 'approved' | 'applied' | 'rejected' | 'expired';

// 审批记录
export interface Approval {
  approver: string;
  comment: string;
  timestamp: string;
}

// 宪法层变更
export interface ConstitutionChange {
  id: string;
  change_type: ChangeType;
  proposed_content: string;
  reason: string;
  target_id: string | null;
  category: string | null;
  status: ChangeStatus;
  approvals_count: number;
  approvals_needed: number;  // 固定为 3
  approvals: Approval[];
  created_at: string;
  updated_at: string;
  applied_at: string | null;
  proposer: string;
}

// 变更历史列表响应
export interface ConstitutionChangeListResponse {
  changes: ConstitutionChange[];
  total: number;
  pending_count: number;
}

// 提议变更请求
export interface ProposeChangeRequest {
  change_type: ChangeType;
  proposed_content: string;
  reason: string;
  target_id?: string;
  category?: string;
}

// 状态显示配置
export const STATUS_CONFIG: Record<ChangeStatus, { label: string; color: string }> = {
  pending: { label: '待审批', color: 'text-yellow-600' },
  approved: { label: '已审批', color: 'text-blue-600' },
  applied: { label: '已应用', color: 'text-green-600' },
  rejected: { label: '已拒绝', color: 'text-red-600' },
  expired: { label: '已过期', color: 'text-gray-600' },
};
