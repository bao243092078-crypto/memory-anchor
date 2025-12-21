import { CheckSquare, Clock, Tag, Calendar, MoreVertical, Pencil, Trash2 } from 'lucide-react';
import { useState } from 'react';
import clsx from 'clsx';
import type { ChecklistItem as ChecklistItemType } from '../../types/checklist';
import { PRIORITY_CONFIG, STATUS_CONFIG, SCOPE_CONFIG } from '../../types/checklist';

interface ChecklistItemProps {
  item: ChecklistItemType;
  onToggle?: (itemId: string, done: boolean) => void;
  onEdit?: (item: ChecklistItemType) => void;
  onDelete?: (item: ChecklistItemType) => void;
}

export function ChecklistItem({ item, onToggle, onEdit, onDelete }: ChecklistItemProps) {
  const [showMenu, setShowMenu] = useState(false);
  const priorityConfig = PRIORITY_CONFIG[item.priority];
  const statusConfig = STATUS_CONFIG[item.status];
  const scopeConfig = SCOPE_CONFIG[item.scope];

  const handleToggle = () => {
    if (onToggle && item.status !== 'cancelled') {
      onToggle(item.id, item.status !== 'done');
    }
  };

  // 提取 (ma:xxxxxxxx) 引用 ID
  const maIdMatch = item.content.match(/\(ma:([a-f0-9]{8})\)/);
  const maId = maIdMatch ? maIdMatch[1] : null;

  return (
    <div
      className={clsx(
        'bg-white rounded-lg border p-4 hover:shadow-md transition-shadow relative',
        item.status === 'done' && 'opacity-60',
        item.status === 'cancelled' && 'opacity-40'
      )}
    >
      {/* 优先级标识 */}
      <div className="absolute top-2 right-2 flex items-center gap-2">
        <span className={clsx('text-xs px-2 py-1 rounded', scopeConfig.color, 'bg-gray-100')}>
          {scopeConfig.label}
        </span>
        <span className={clsx('text-lg', priorityConfig.color)}>{priorityConfig.icon}</span>

        {/* 菜单按钮 */}
        <div className="relative">
          <button
            onClick={() => setShowMenu(!showMenu)}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <MoreVertical size={16} className="text-gray-400" />
          </button>

          {showMenu && (
            <div className="absolute right-0 top-full mt-1 bg-white border rounded-lg shadow-lg py-1 z-10 min-w-[120px]">
              {onEdit && (
                <button
                  onClick={() => {
                    onEdit(item);
                    setShowMenu(false);
                  }}
                  className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 flex items-center gap-2"
                >
                  <Pencil size={14} />
                  编辑
                </button>
              )}
              {onDelete && (
                <button
                  onClick={() => {
                    onDelete(item);
                    setShowMenu(false);
                  }}
                  className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 flex items-center gap-2 text-red-600"
                >
                  <Trash2 size={14} />
                  删除
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 内容区 */}
      <div className="flex items-start gap-3 pr-20">
        {/* 复选框 */}
        <button
          onClick={handleToggle}
          disabled={item.status === 'cancelled'}
          className={clsx(
            'mt-1 flex-shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors',
            item.status === 'done'
              ? 'bg-green-500 border-green-500 text-white'
              : 'border-gray-300 hover:border-green-500',
            item.status === 'cancelled' && 'border-gray-300 bg-gray-100 cursor-not-allowed'
          )}
        >
          {item.status === 'done' && <CheckSquare size={14} />}
        </button>

        {/* 内容 */}
        <div className="flex-1 min-w-0">
          <p
            className={clsx(
              'text-gray-900 break-words',
              item.status === 'done' && 'line-through text-gray-500'
            )}
          >
            {item.content}
          </p>

          {/* 元信息 */}
          <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-gray-500">
            {/* 状态 */}
            <span className={clsx('flex items-center gap-1', statusConfig.color)}>
              <span>{statusConfig.icon}</span>
              <span>{statusConfig.label}</span>
            </span>

            {/* 创建时间 */}
            <span className="flex items-center gap-1">
              <Clock size={12} />
              {new Date(item.created_at).toLocaleDateString()}
            </span>

            {/* 过期时间 */}
            {item.expires_at && (
              <span className="flex items-center gap-1 text-orange-600">
                <Calendar size={12} />
                截止 {new Date(item.expires_at).toLocaleDateString()}
              </span>
            )}

            {/* 完成时间 */}
            {item.completed_at && (
              <span className="flex items-center gap-1 text-green-600">
                ✓ {new Date(item.completed_at).toLocaleDateString()}
              </span>
            )}

            {/* Memory Anchor 引用 ID */}
            {maId && (
              <span className="flex items-center gap-1 font-mono text-purple-600">
                ma:{maId}
              </span>
            )}
          </div>

          {/* 标签 */}
          {item.tags.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
              {item.tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs"
                >
                  <Tag size={10} />
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
