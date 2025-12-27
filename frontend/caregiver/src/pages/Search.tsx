import { useState, useEffect } from 'react';
import { Search as SearchIcon } from 'lucide-react';
import { useSearch } from '../hooks/useSearch';
import type { MemoryLayerV2, NoteCategory } from '../types/note';
import type { SearchParams } from '../api/search';
import { LAYER_CONFIG, CATEGORY_CONFIG, V2_LAYERS, normalizeLayer } from '../types/note';
import { Loading } from '../components/Common/Loading';
import { EmptyState } from '../components/Common/EmptyState';
import { LayerBadge } from '../components/Note/LayerBadge';

export function SearchPage() {
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [layer, setLayer] = useState<MemoryLayerV2 | ''>('');
  const [category, setCategory] = useState<NoteCategory | ''>('');

  // 防抖处理
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const searchParams: SearchParams = {
    q: debouncedQuery,
    limit: 20,
    layer: layer || undefined,
    category: category || undefined,
  };

  const { data: results, isLoading, isFetching } = useSearch(searchParams);

  const hasQuery = debouncedQuery.trim().length > 0;

  return (
    <div className="space-y-6">
      {/* 搜索框 */}
      <div className="bg-white rounded-lg shadow-sm border p-4">
        <div className="flex flex-col gap-4">
          {/* 搜索输入 */}
          <div className="relative">
            <SearchIcon
              size={20}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
            />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索记忆条目..."
              className="w-full pl-10 pr-4 py-3 text-lg border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              autoFocus
            />
            {isFetching && (
              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              </div>
            )}
          </div>

          {/* 过滤器 */}
          <div className="flex flex-wrap gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                层级
              </label>
              <select
                value={layer}
                onChange={(e) => setLayer(e.target.value as MemoryLayerV2 | '')}
                className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">全部层级</option>
                {V2_LAYERS.map((l) => (
                  <option key={l} value={l}>
                    {LAYER_CONFIG[l].label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                分类
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as NoteCategory | '')}
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
          </div>
        </div>
      </div>

      {/* 搜索结果 */}
      {!hasQuery ? (
        <EmptyState
          icon={<SearchIcon size={48} />}
          title="输入关键词搜索"
          description="支持语义搜索，可以搜索相关内容而不仅仅是精确匹配"
        />
      ) : isLoading ? (
        <Loading text="搜索中..." />
      ) : results && results.results && results.results.length > 0 ? (
        <div className="space-y-4">
          <p className="text-sm text-gray-500">
            找到 {results.total} 条相关结果
          </p>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {results.results.map((result) => (
              <div key={result.id} className="relative bg-white rounded-lg shadow-sm border p-4">
                <p className="text-gray-800">{result.content}</p>
                <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
                  <LayerBadge layer={normalizeLayer(result.layer)} size="sm" />
                  {result.score !== undefined && (
                    <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded">
                      相关度: {Math.round(result.score * 100)}%
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <EmptyState
          icon={<SearchIcon size={48} />}
          title="没有找到相关内容"
          description="试试其他关键词，或调整过滤条件"
        />
      )}
    </div>
  );
}
