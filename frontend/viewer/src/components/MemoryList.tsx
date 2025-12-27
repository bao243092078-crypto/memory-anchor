import { useTranslation } from 'react-i18next';
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
  // Batch selection props
  selectionMode?: boolean;
  selectedIds?: Set<string>;
  onSelect?: (id: string) => void;
  onSelectAll?: () => void;
  onDeselectAll?: () => void;
  onBatchDelete?: () => void;
  onBatchVerify?: () => void;
  onEnterSelectionMode?: () => void;
  onExitSelectionMode?: () => void;
}

export function MemoryList({
  memories,
  loading,
  error,
  searchQuery,
  onVerify,
  onDelete,
  onCardClick,
  verifyingId,
  selectionMode = false,
  selectedIds = new Set(),
  onSelect,
  onSelectAll,
  onDeselectAll,
  onBatchDelete,
  onBatchVerify,
  onEnterSelectionMode,
  onExitSelectionMode,
}: MemoryListProps) {
  const { t } = useTranslation();
  const selectedCount = selectedIds.size;
  const isAllSelected = memories.length > 0 && memories.every((m) => selectedIds.has(m.id));
  const hasUnverified = memories.some((m) => selectedIds.has(m.id) && m.confidence < 1);
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
        <p className="mt-4 text-sm text-gray-400 font-medium">{t('memory.loading')}</p>
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
        <h3 className="text-base font-semibold text-gray-900 mb-1">{t('memory.connectionError')}</h3>
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
          {searchQuery ? t('memory.noResults') : t('memory.empty')}
        </h3>
        <p className="text-sm text-gray-500 text-center max-w-sm">
          {searchQuery
            ? t('memory.tryOtherSearch')
            : t('memory.addFirst')
          }
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Batch action toolbar */}
      {selectionMode ? (
        <div className="sticky top-0 z-20 bg-white/95 backdrop-blur-sm border border-gray-200 rounded-xl p-3 shadow-sm animate-fade-in">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              {/* Select all checkbox */}
              <button
                onClick={isAllSelected ? onDeselectAll : onSelectAll}
                className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
              >
                <div
                  className={`
                    w-5 h-5 rounded-md border-2 flex items-center justify-center transition-all
                    ${isAllSelected ? 'bg-lime-500 border-lime-500' : 'bg-white border-gray-300'}
                  `}
                >
                  {isAllSelected && (
                    <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
                {t('batch.selectAll')}
              </button>

              <span className="text-sm text-gray-500">
                {t('batch.selected', { count: selectedCount })}
              </span>
            </div>

            <div className="flex items-center gap-2">
              {/* Batch verify button */}
              {hasUnverified && onBatchVerify && (
                <button
                  onClick={onBatchVerify}
                  disabled={selectedCount === 0}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-lime-700 bg-lime-50 rounded-lg hover:bg-lime-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                  {t('batch.verify')}
                </button>
              )}

              {/* Batch delete button */}
              {onBatchDelete && (
                <button
                  onClick={onBatchDelete}
                  disabled={selectedCount === 0}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-red-700 bg-red-50 rounded-lg hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                  {t('batch.delete')}
                </button>
              )}

              {/* Exit selection mode */}
              <button
                onClick={onExitSelectionMode}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
                {t('common.cancel')}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-between gap-2 mb-2">
          {searchQuery ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">
                {t('search.foundResults', { count: memories.length })}
              </span>
              <span className="text-gray-300">•</span>
              <span className="text-sm text-gray-400">{t('search.sortByRelevance')}</span>
            </div>
          ) : (
            <div />
          )}

          {/* Enter selection mode button */}
          {memories.length > 0 && onEnterSelectionMode && (
            <button
              onClick={onEnterSelectionMode}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              {t('batch.operations')}
            </button>
          )}
        </div>
      )}

      <div className="grid gap-4">
        {memories.map((memory, index) => (
          <MemoryCard
            key={memory.id}
            memory={memory}
            index={index}
            onVerify={selectionMode ? undefined : onVerify}
            onDelete={selectionMode ? undefined : onDelete}
            onClick={selectionMode ? undefined : onCardClick}
            verifying={verifyingId === memory.id}
            selectionMode={selectionMode}
            selected={selectedIds.has(memory.id)}
            onSelect={onSelect}
          />
        ))}
      </div>
    </div>
  );
}
