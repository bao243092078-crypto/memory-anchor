import { Clock, Check, X, AlertCircle } from 'lucide-react';
import { usePendingChanges, useApproveChange, useRejectChange } from '../hooks/useConstitution';
import type { ConstitutionChange } from '../types/constitution';
import type { NoteCategory } from '../types/note';
import { CATEGORY_CONFIG } from '../types/note';
import { Button } from '../components/Common/Button';
import { Loading } from '../components/Common/Loading';
import { EmptyState } from '../components/Common/EmptyState';
import { format } from 'date-fns';

function ChangeTypeLabel({ type }: { type: ConstitutionChange['change_type'] }) {
  const config = {
    create: { label: '新增', color: 'bg-green-100 text-green-700' },
    update: { label: '修改', color: 'bg-blue-100 text-blue-700' },
    delete: { label: '删除', color: 'bg-orange-100 text-orange-700' },
  };
  const { label, color } = config[type];
  return (
    <span className={`px-2 py-0.5 text-xs font-medium rounded ${color}`}>
      {label}
    </span>
  );
}

function ApprovalProgress({ count, required = 3 }: { count: number; required?: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex gap-1">
        {Array.from({ length: required }).map((_, i) => (
          <div
            key={i}
            className={`w-3 h-3 rounded-full ${
              i < count ? 'bg-green-500' : 'bg-gray-200'
            }`}
          />
        ))}
      </div>
      <span className="text-sm text-gray-500">
        {count}/{required} 次确认
      </span>
    </div>
  );
}

export function PendingPage() {
  const { data: pendingChanges, isLoading, error } = usePendingChanges();
  const approveMutation = useApproveChange();
  const rejectMutation = useRejectChange();

  const handleApprove = (change: ConstitutionChange) => {
    approveMutation.mutate(change.id);
  };

  const handleReject = (change: ConstitutionChange) => {
    rejectMutation.mutate(change.id);
  };

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">加载待审批列表时出错，请稍后重试</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 说明卡片 */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <AlertCircle className="text-yellow-600 mt-0.5 flex-shrink-0" size={20} />
          <div>
            <h3 className="font-medium text-yellow-800">三次确认机制</h3>
            <p className="text-sm text-yellow-700 mt-1">
              为保护 AI 核心身份不被意外覆盖，每个核心身份变更需要<strong>三次独立确认</strong>。
              建议在不同时间点分三次确认，避免误操作。
            </p>
          </div>
        </div>
      </div>

      {/* 待审批列表 */}
      {isLoading ? (
        <Loading text="加载中..." />
      ) : pendingChanges && pendingChanges.length > 0 ? (
        <div className="space-y-4">
          {pendingChanges.map((change) => (
            <div
              key={change.id}
              className="bg-white rounded-lg shadow-sm border p-4 space-y-4"
            >
              {/* 头部 */}
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <ChangeTypeLabel type={change.change_type} />
                  {change.category && CATEGORY_CONFIG[change.category as NoteCategory] && (
                    <span className="text-sm text-gray-500">
                      {CATEGORY_CONFIG[change.category as NoteCategory].icon} {CATEGORY_CONFIG[change.category as NoteCategory].label}
                    </span>
                  )}
                </div>
                <ApprovalProgress count={change.approvals_count} />
              </div>

              {/* 内容 */}
              <div className="space-y-2">
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-sm font-medium text-gray-500 mb-1">提议内容</p>
                  <p className="text-gray-800">{change.proposed_content}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500 mb-1">提议理由</p>
                  <p className="text-sm text-gray-600">{change.reason}</p>
                </div>
              </div>

              {/* 底部 */}
              <div className="flex items-center justify-between pt-2 border-t border-gray-100">
                <span className="text-xs text-gray-400">
                  提议时间: {format(new Date(change.created_at), 'yyyy-MM-dd HH:mm')}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleReject(change)}
                    loading={rejectMutation.isPending}
                  >
                    <X size={16} className="mr-1" />
                    拒绝
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => handleApprove(change)}
                    loading={approveMutation.isPending}
                  >
                    <Check size={16} className="mr-1" />
                    确认 ({change.approvals_count + 1}/3)
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Clock size={48} />}
          title="没有待审批的变更"
          description="所有核心身份变更提议都已处理完毕"
        />
      )}
    </div>
  );
}
