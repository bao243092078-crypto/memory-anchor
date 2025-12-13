import type { MemoryLayer, NoteCategory, NotesQueryParams } from '../../types/note';
import { LAYER_CONFIG, CATEGORY_CONFIG } from '../../types/note';

interface NoteFiltersProps {
  filters: NotesQueryParams;
  onChange: (filters: NotesQueryParams) => void;
}

export function NoteFilters({ filters, onChange }: NoteFiltersProps) {
  return (
    <div className="flex flex-wrap gap-4">
      {/* 层级过滤 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          层级
        </label>
        <select
          value={filters.layer || ''}
          onChange={(e) =>
            onChange({
              ...filters,
              layer: e.target.value as MemoryLayer | undefined || undefined,
            })
          }
          className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="">全部层级</option>
          {(Object.keys(LAYER_CONFIG) as MemoryLayer[]).map((l) => (
            <option key={l} value={l}>
              {LAYER_CONFIG[l].label}
            </option>
          ))}
        </select>
      </div>

      {/* 分类过滤 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          分类
        </label>
        <select
          value={filters.category || ''}
          onChange={(e) =>
            onChange({
              ...filters,
              category: e.target.value as NoteCategory | undefined || undefined,
            })
          }
          className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="">全部分类</option>
          {(Object.keys(CATEGORY_CONFIG) as NoteCategory[]).map((c) => (
            <option key={c} value={c}>
              {CATEGORY_CONFIG[c].icon} {CATEGORY_CONFIG[c].label}
            </option>
          ))}
        </select>
      </div>

      {/* 激活状态 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          状态
        </label>
        <select
          value={filters.active_only === false ? 'all' : 'active'}
          onChange={(e) =>
            onChange({
              ...filters,
              active_only: e.target.value === 'active' ? true : false,
            })
          }
          className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="active">仅激活</option>
          <option value="all">全部</option>
        </select>
      </div>
    </div>
  );
}
