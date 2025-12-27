import { useState } from 'react';
import type { FormEvent } from 'react';
import type { Note, MemoryLayerV2, NoteCategory, CreateNoteRequest, UpdateNoteRequest } from '../../types/note';
import { LAYER_CONFIG, CATEGORY_CONFIG, NOTE_CREATION_LAYERS, normalizeLayer } from '../../types/note';
import { Button } from '../Common/Button';

interface NoteFormProps {
  note?: Note;  // 编辑模式时传入
  onSubmit: (data: CreateNoteRequest | UpdateNoteRequest) => void;
  onCancel: () => void;
  loading?: boolean;
}

export function NoteForm({ note, onSubmit, onCancel, loading }: NoteFormProps) {
  const [content, setContent] = useState(note?.content || '');
  const [layer, setLayer] = useState<MemoryLayerV2>(
    normalizeLayer(note?.layer || 'verified_fact')
  );
  const [category, setCategory] = useState<NoteCategory | ''>(note?.category || '');
  const [priority, setPriority] = useState(note?.priority ?? 50);

  const isEdit = !!note;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;

    if (isEdit) {
      onSubmit({
        content: content.trim(),
        category: category || undefined,
        priority,
      });
      return;
    }

    onSubmit({
      content: content.trim(),
      layer,
      category: category || undefined,
      priority,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* 内容 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          内容 <span className="text-red-500">*</span>
        </label>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="输入记忆内容..."
          rows={4}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          required
        />
      </div>

      {/* 层级 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          记忆层级 {isEdit && <span className="text-xs text-gray-500">(创建后不可修改)</span>}
        </label>
        <div className="flex gap-2">
          {NOTE_CREATION_LAYERS.map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => setLayer(l)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                layer === l
                  ? `${LAYER_CONFIG[l].bgColor} ${LAYER_CONFIG[l].color} ring-2 ring-offset-1`
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
              disabled={isEdit || (l === 'identity_schema' && !isEdit)}
              title={
                isEdit
                  ? '编辑模式不支持修改层级'
                  : l === 'identity_schema'
                    ? '核心身份需通过审批流程添加'
                    : undefined
              }
            >
              {LAYER_CONFIG[l].label}
            </button>
          ))}
        </div>
        {layer === 'identity_schema' && !isEdit && (
          <p className="mt-1 text-xs text-gray-500">
            核心身份需要通过「核心身份」页面提议并审批
          </p>
        )}
      </div>

      {/* 分类 */}
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

      {/* 优先级 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          优先级 (0-999，越小越重要)
        </label>
        <input
          type="number"
          value={priority}
          onChange={(e) => setPriority(Number(e.target.value))}
          min={0}
          max={999}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      {/* 按钮 */}
      <div className="flex justify-end gap-3 pt-4">
        <Button type="button" variant="secondary" onClick={onCancel}>
          取消
        </Button>
        <Button type="submit" loading={loading} disabled={!content.trim()}>
          {isEdit ? '保存修改' : '创建记忆条目'}
        </Button>
      </div>
    </form>
  );
}
