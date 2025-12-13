import { useState } from 'react';
import { Shield, Plus, AlertCircle } from 'lucide-react';
import { useConstitution, useProposeConstitutionChange } from '../hooks/useConstitution';
import type { ProposeChangeRequest } from '../types/constitution';
import type { NoteCategory } from '../types/note';
import { CATEGORY_CONFIG } from '../types/note';
import { Modal } from '../components/Common/Modal';
import { Button } from '../components/Common/Button';
import { Loading } from '../components/Common/Loading';
import { EmptyState } from '../components/Common/EmptyState';
import { LayerBadge } from '../components/Note/LayerBadge';

export function ConstitutionPage() {
  const [isProposing, setIsProposing] = useState(false);
  const [content, setContent] = useState('');
  const [reason, setReason] = useState('');
  const [category, setCategory] = useState<NoteCategory | ''>('');

  const { data: constitutionItems, isLoading, error } = useConstitution();
  const proposeMutation = useProposeConstitutionChange();

  const handlePropose = (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim() || !reason.trim()) return;

    const request: ProposeChangeRequest = {
      change_type: 'create',
      proposed_content: content.trim(),
      reason: reason.trim(),
      category: category || undefined,
    };

    proposeMutation.mutate(request, {
      onSuccess: () => {
        setIsProposing(false);
        setContent('');
        setReason('');
        setCategory('');
      },
    });
  };

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">加载宪法层时出错，请稍后重试</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 说明卡片 */}
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <AlertCircle className="text-red-500 mt-0.5 flex-shrink-0" size={20} />
          <div>
            <h3 className="font-medium text-red-800">关于核心身份层</h3>
            <p className="text-sm text-red-700 mt-1">
              核心身份层存储 AI 的不可变身份信息，如项目定位、关键决策、架构原则等。
              任何修改都需要<strong>三次独立确认</strong>才能生效，防止 AI 的核心认知被意外覆盖。
            </p>
          </div>
        </div>
      </div>

      {/* 操作栏 */}
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-medium text-gray-900">
          当前核心身份条目
        </h2>
        <Button onClick={() => setIsProposing(true)}>
          <Plus size={18} className="mr-1" />
          提议新增
        </Button>
      </div>

      {/* 宪法层条目列表 */}
      {isLoading ? (
        <Loading text="加载中..." />
      ) : constitutionItems && constitutionItems.length > 0 ? (
        <div className="space-y-3">
          {constitutionItems.map((item) => (
            <div
              key={item.id}
              className="bg-white rounded-lg shadow-sm border border-l-4 border-l-red-500 p-4"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <LayerBadge layer="constitution" size="sm" />
                    {item.category && CATEGORY_CONFIG[item.category as NoteCategory] && (
                      <span className="text-sm text-gray-500">
                        {CATEGORY_CONFIG[item.category as NoteCategory].icon} {CATEGORY_CONFIG[item.category as NoteCategory].label}
                      </span>
                    )}
                  </div>
                  <p className="text-gray-800">{item.content}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Shield size={48} />}
          title="还没有核心身份条目"
          description="核心身份层存储 AI 的不可变信息，点击上方按钮提议新增"
          action={
            <Button onClick={() => setIsProposing(true)}>
              <Plus size={18} className="mr-1" />
              提议新增
            </Button>
          }
        />
      )}

      {/* 提议新增模态框 */}
      <Modal
        isOpen={isProposing}
        onClose={() => setIsProposing(false)}
        title="提议新增核心身份"
      >
        <form onSubmit={handlePropose} className="space-y-4">
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
            <p className="text-sm text-yellow-800">
              提交后，此条目需要<strong>三次独立确认</strong>才能正式生效。
              请前往「待审批」页面进行确认。
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              条目内容 <span className="text-red-500">*</span>
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="如：项目定位 - Memory Anchor 是 AI 的外挂海马体"
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              分类
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as NoteCategory | '')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">不指定</option>
              {(Object.keys(CATEGORY_CONFIG) as NoteCategory[]).map((c) => (
                <option key={c} value={c}>
                  {CATEGORY_CONFIG[c].icon} {CATEGORY_CONFIG[c].label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              提议理由 <span className="text-red-500">*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="如：项目初始设定 / 用户提供的基础信息"
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              required
            />
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setIsProposing(false)}
            >
              取消
            </Button>
            <Button
              type="submit"
              loading={proposeMutation.isPending}
              disabled={!content.trim() || !reason.trim()}
            >
              提交提议
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
