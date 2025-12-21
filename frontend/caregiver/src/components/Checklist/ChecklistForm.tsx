import { useState } from 'react';
import { Button } from '../Common/Button';
import type {
  ChecklistItem,
  CreateChecklistItemRequest,
  UpdateChecklistItemRequest,
  ChecklistPriority,
  ChecklistScope,
} from '../../types/checklist';
import { PRIORITY_CONFIG, SCOPE_CONFIG } from '../../types/checklist';

interface ChecklistFormProps {
  item?: ChecklistItem;
  projectId: string;
  onSubmit: (data: CreateChecklistItemRequest | UpdateChecklistItemRequest) => void;
  onCancel: () => void;
  loading?: boolean;
}

export function ChecklistForm({ item, projectId, onSubmit, onCancel, loading }: ChecklistFormProps) {
  const [content, setContent] = useState(item?.content || '');
  const [priority, setPriority] = useState<ChecklistPriority>(item?.priority || 3);
  const [scope, setScope] = useState<ChecklistScope>(item?.scope || 'project');
  const [tags, setTags] = useState<string>(item?.tags?.join(', ') || '');
  const [expiresAt, setExpiresAt] = useState(
    item?.expires_at ? new Date(item.expires_at).toISOString().split('T')[0] : ''
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const tagsArray = tags
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t);

    if (item) {
      // 更新
      const update: UpdateChecklistItemRequest = {
        content,
        priority,
        tags: tagsArray,
        expires_at: expiresAt || undefined,
      };
      onSubmit(update);
    } else {
      // 创建
      const create: CreateChecklistItemRequest = {
        project_id: projectId,
        content,
        priority,
        scope,
        tags: tagsArray,
        expires_at: expiresAt || undefined,
      };
      onSubmit(create);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* 内容 */}
      <div>
        <label htmlFor="content" className="block text-sm font-medium text-gray-700 mb-1">
          清单内容 <span className="text-red-500">*</span>
        </label>
        <textarea
          id="content"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="输入清单项内容..."
          required
        />
      </div>

      {/* 优先级 */}
      <div>
        <label htmlFor="priority" className="block text-sm font-medium text-gray-700 mb-1">
          优先级
        </label>
        <select
          id="priority"
          value={priority}
          onChange={(e) => setPriority(Number(e.target.value) as ChecklistPriority)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {Object.entries(PRIORITY_CONFIG).map(([key, config]) => (
            <option key={key} value={key}>
              {config.icon} {config.label}
            </option>
          ))}
        </select>
      </div>

      {/* 作用域（仅创建时） */}
      {!item && (
        <div>
          <label htmlFor="scope" className="block text-sm font-medium text-gray-700 mb-1">
            作用域
          </label>
          <select
            id="scope"
            value={scope}
            onChange={(e) => setScope(e.target.value as ChecklistScope)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {Object.entries(SCOPE_CONFIG).map(([key, config]) => (
              <option key={key} value={key}>
                {config.label} - {config.description}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* 标签 */}
      <div>
        <label htmlFor="tags" className="block text-sm font-medium text-gray-700 mb-1">
          标签
        </label>
        <input
          id="tags"
          type="text"
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="用逗号分隔，例如：前端, bug修复, 高优"
        />
        <p className="text-xs text-gray-500 mt-1">用逗号分隔多个标签</p>
      </div>

      {/* 截止日期 */}
      <div>
        <label htmlFor="expiresAt" className="block text-sm font-medium text-gray-700 mb-1">
          截止日期（可选）
        </label>
        <input
          id="expiresAt"
          type="date"
          value={expiresAt}
          onChange={(e) => setExpiresAt(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* 按钮 */}
      <div className="flex justify-end gap-3 pt-4">
        <Button type="button" variant="secondary" onClick={onCancel}>
          取消
        </Button>
        <Button type="submit" loading={loading}>
          {item ? '保存' : '创建'}
        </Button>
      </div>
    </form>
  );
}
