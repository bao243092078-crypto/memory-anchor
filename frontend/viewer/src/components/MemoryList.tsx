import type { Memory } from '../types';
import { MemoryCard } from './MemoryCard';

interface MemoryListProps {
  memories: Memory[];
  loading: boolean;
  error: string | null;
  searchQuery: string;
  onVerify?: (id: string) => void;
  onDelete?: (id: string) => void;
  onCardClick?: (memory: Memory) => void;
  verifyingId?: string | null;
}

export function MemoryList({ memories, loading, error, searchQuery, onVerify, onDelete, onCardClick, verifyingId }: MemoryListProps) {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="relative">
          <div className="w-16 h-16 rounded-2xl bg-gray-100 animate-pulse" />
          <div className="absolute inset-0 flex items-center justify-center">
            <svg className="w-8 h-8 text-gray-300 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
          </div>
        </div>
        <p className="mt-4 text-sm text-gray-400 font-medium">加载记忆中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="w-16 h-16 rounded-2xl bg-red-50 flex items-center justify-center mb-4">
          <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h3 className="text-base font-semibold text-gray-900 mb-1">连接错误</h3>
        <p className="text-sm text-gray-500 text-center max-w-sm">{error}</p>
      </div>
    );
  }

  if (memories.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="w-16 h-16 rounded-2xl bg-gray-50 flex items-center justify-center mb-4">
          <svg className="w-8 h-8 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
          </svg>
        </div>
        <h3 className="text-base font-semibold text-gray-900 mb-1">
          {searchQuery ? '未找到匹配结果' : '暂无记忆'}
        </h3>
        <p className="text-sm text-gray-500 text-center max-w-sm">
          {searchQuery
            ? '试试其他搜索词或清除筛选条件'
            : '添加记忆后将显示在这里'
          }
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {searchQuery && (
        <div className="flex items-center gap-2 mb-6">
          <span className="text-sm text-gray-500">
            找到 <span className="font-semibold text-gray-900">{memories.length}</span> 条结果
          </span>
          <span className="text-gray-300">•</span>
          <span className="text-sm text-gray-400">按相关度排序</span>
        </div>
      )}

      <div className="grid gap-4">
        {memories.map((memory, index) => (
          <MemoryCard
            key={memory.id}
            memory={memory}
            index={index}
            onVerify={onVerify}
            onDelete={onDelete}
            onClick={onCardClick}
            verifying={verifyingId === memory.id}
          />
        ))}
      </div>
    </div>
  );
}
