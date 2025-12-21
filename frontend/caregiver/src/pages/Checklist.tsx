import { useState } from 'react';
import { Plus, CheckSquare, Filter, RefreshCw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import {
  useChecklistBriefing,
  useChecklistItems,
  useCreateChecklistItem,
  useUpdateChecklistItem,
  useDeleteChecklistItem,
} from '../hooks/useChecklist';
import { ChecklistItem } from '../components/Checklist/ChecklistItem';
import { ChecklistForm } from '../components/Checklist/ChecklistForm';
import { Modal } from '../components/Common/Modal';
import { Button } from '../components/Common/Button';
import { Loading } from '../components/Common/Loading';
import { EmptyState } from '../components/Common/EmptyState';
import type {
  ChecklistItem as ChecklistItemType,
  CreateChecklistItemRequest,
  UpdateChecklistItemRequest,
  ChecklistScope,
  ChecklistPriority,
} from '../types/checklist';
import { PRIORITY_CONFIG } from '../types/checklist';

// TODO: 从配置或 localStorage 获取项目 ID
const DEFAULT_PROJECT_ID = '阿默斯海默症';

export function ChecklistPage() {
  const [projectId] = useState(DEFAULT_PROJECT_ID);
  const [selectedScope, setSelectedScope] = useState<ChecklistScope | undefined>();
  const [selectedPriority, setSelectedPriority] = useState<ChecklistPriority | undefined>();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<ChecklistItemType | null>(null);
  const [deletingItem, setDeletingItem] = useState<ChecklistItemType | null>(null);

  // 获取简报
  const { data: briefing, isLoading: briefingLoading, refetch: refetchBriefing } = useChecklistBriefing(
    projectId,
    selectedScope
  );

  // 获取详细列表
  const { data: items, isLoading: itemsLoading } = useChecklistItems(projectId, {
    scope: selectedScope,
    priority: selectedPriority,
  });

  const createMutation = useCreateChecklistItem();
  const updateMutation = useUpdateChecklistItem();
  const deleteMutation = useDeleteChecklistItem();

  const isLoading = briefingLoading || itemsLoading;

  const handleCreate = (data: CreateChecklistItemRequest | UpdateChecklistItemRequest) => {
    createMutation.mutate(data as CreateChecklistItemRequest, {
      onSuccess: () => {
        setIsCreateModalOpen(false);
        refetchBriefing();
      },
    });
  };

  const handleUpdate = (data: CreateChecklistItemRequest | UpdateChecklistItemRequest) => {
    if (!editingItem) return;
    updateMutation.mutate(
      {
        itemId: editingItem.id,
        update: data as UpdateChecklistItemRequest,
      },
      {
        onSuccess: () => {
          setEditingItem(null);
          refetchBriefing();
        },
      }
    );
  };

  const handleToggle = (itemId: string, done: boolean) => {
    updateMutation.mutate(
      {
        itemId,
        update: { status: done ? 'done' : 'open' },
      },
      {
        onSuccess: () => refetchBriefing(),
      }
    );
  };

  const handleDelete = () => {
    if (!deletingItem) return;
    deleteMutation.mutate(deletingItem.id, {
      onSuccess: () => {
        setDeletingItem(null);
        refetchBriefing();
      },
    });
  };

  // 按优先级分组
  const itemsByPriority: Partial<Record<ChecklistPriority, ChecklistItemType[]>> =
    items?.reduce(
      (acc, item) => {
        if (!acc[item.priority]) {
          acc[item.priority] = [];
        }
        acc[item.priority]!.push(item);
        return acc;
      },
      {} as Partial<Record<ChecklistPriority, ChecklistItemType[]>>
    ) || {};

  return (
    <div className="space-y-6">
      {/* 顶部操作栏 */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">清单革命</h2>
          <p className="text-sm text-gray-500 mt-1">任务清单 - 永不遗忘的待办事项</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={() => refetchBriefing()}>
            <RefreshCw size={18} className="mr-1" />
            刷新
          </Button>
          <Button onClick={() => setIsCreateModalOpen(true)}>
            <Plus size={18} className="mr-1" />
            新建清单项
          </Button>
        </div>
      </div>

      {/* 筛选器 */}
      <div className="bg-white rounded-lg shadow-sm border p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter size={18} className="text-gray-600" />
          <span className="font-medium text-gray-900">筛选</span>
        </div>
        <div className="flex flex-wrap gap-3">
          {/* 作用域筛选 */}
          <select
            value={selectedScope || ''}
            onChange={(e) => setSelectedScope((e.target.value as ChecklistScope) || undefined)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">全部作用域</option>
            <option value="project">项目级</option>
            <option value="session">会话级</option>
            <option value="global">全局</option>
          </select>

          {/* 优先级筛选 */}
          <select
            value={selectedPriority || ''}
            onChange={(e) =>
              setSelectedPriority(e.target.value ? (Number(e.target.value) as ChecklistPriority) : undefined)
            }
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">全部优先级</option>
            {Object.entries(PRIORITY_CONFIG).map(([key, config]) => (
              <option key={key} value={key}>
                {config.icon} {config.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 简报（Markdown） */}
      {briefing?.markdown && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-medium text-blue-900 mb-2">清单简报</h3>
          <div className="prose prose-sm max-w-none text-blue-800">
            <ReactMarkdown>{briefing.markdown}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* 清单列表（按优先级分组） */}
      {isLoading ? (
        <Loading text="加载中..." />
      ) : items && items.length > 0 ? (
        <div className="space-y-6">
          {([1, 2, 3, 4, 5] as ChecklistPriority[]).map((priority) => {
            const priorityItems = itemsByPriority[priority] || [];
            if (priorityItems.length === 0) return null;

            const config = PRIORITY_CONFIG[priority];
            return (
              <div key={priority}>
                <h3 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                  <span className="text-xl">{config.icon}</span>
                  <span>
                    {config.label} ({priorityItems.length})
                  </span>
                </h3>
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {priorityItems.map((item: ChecklistItemType) => (
                    <ChecklistItem
                      key={item.id}
                      item={item}
                      onToggle={handleToggle}
                      onEdit={setEditingItem}
                      onDelete={setDeletingItem}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <EmptyState
          icon={<CheckSquare size={48} />}
          title="还没有清单项"
          description="创建第一个清单项，开始任务管理"
          action={
            <Button onClick={() => setIsCreateModalOpen(true)}>
              <Plus size={18} className="mr-1" />
              新建清单项
            </Button>
          }
        />
      )}

      {/* 创建模态框 */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="新建清单项"
      >
        <ChecklistForm
          projectId={projectId}
          onSubmit={handleCreate}
          onCancel={() => setIsCreateModalOpen(false)}
          loading={createMutation.isPending}
        />
      </Modal>

      {/* 编辑模态框 */}
      <Modal
        isOpen={!!editingItem}
        onClose={() => setEditingItem(null)}
        title="编辑清单项"
      >
        {editingItem && (
          <ChecklistForm
            item={editingItem}
            projectId={projectId}
            onSubmit={handleUpdate}
            onCancel={() => setEditingItem(null)}
            loading={updateMutation.isPending}
          />
        )}
      </Modal>

      {/* 删除确认模态框 */}
      <Modal
        isOpen={!!deletingItem}
        onClose={() => setDeletingItem(null)}
        title="确认删除"
      >
        <div className="space-y-4">
          <p className="text-gray-600">确定要删除这个清单项吗？此操作无法撤销。</p>
          {deletingItem && (
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-sm text-gray-800">{deletingItem.content}</p>
            </div>
          )}
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setDeletingItem(null)}>
              取消
            </Button>
            <Button
              variant="danger"
              onClick={handleDelete}
              loading={deleteMutation.isPending}
            >
              确认删除
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
