import { Edit2, Trash2 } from 'lucide-react';
import { format } from 'date-fns';
import clsx from 'clsx';
import type { Note, NoteCategory } from '../../types/note';
import { CATEGORY_CONFIG } from '../../types/note';
import { LayerBadge } from './LayerBadge';

interface NoteCardProps {
  note: Note;
  onEdit?: (note: Note) => void;
  onDelete?: (note: Note) => void;
}

export function NoteCard({ note, onEdit, onDelete }: NoteCardProps) {
  const categoryConfig = note.category ? CATEGORY_CONFIG[note.category as NoteCategory] : null;

  return (
    <div
      className={clsx(
        'bg-white rounded-lg shadow-sm border p-4 transition-shadow hover:shadow-md',
        note.layer === 'constitution' && 'border-l-4 border-l-red-500',
        note.layer === 'fact' && 'border-l-4 border-l-blue-500',
        note.layer === 'session' && 'border-l-4 border-l-green-500',
        !note.is_active && 'opacity-60'
      )}
    >
      {/* 头部 */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <LayerBadge layer={note.layer} size="sm" />
          {categoryConfig && (
            <span className="text-sm text-gray-500">
              {categoryConfig.icon} {categoryConfig.label}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          {onEdit && (
            <button
              onClick={() => onEdit(note)}
              className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
              title="编辑"
            >
              <Edit2 size={16} />
            </button>
          )}
          {onDelete && (
            <button
              onClick={() => onDelete(note)}
              className="p-1.5 text-gray-400 hover:text-orange-600 hover:bg-orange-50 rounded"
              title="删除"
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>
      </div>

      {/* 内容 */}
      <p className="text-gray-800 whitespace-pre-wrap">{note.content}</p>

      {/* 底部信息 */}
      <div className="mt-3 pt-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-400">
        <span>优先级: {note.priority}</span>
        <span>{format(new Date(note.created_at), 'yyyy-MM-dd HH:mm')}</span>
      </div>
    </div>
  );
}
