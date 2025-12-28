import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Header, SearchBar, FilterPanel, MemoryList, ConfirmDialog, MemoryDetail } from './components';
import type { ViewType } from './components/Header';
import { useMemories } from './hooks/useMemories';
import { useMemoryActions } from './hooks/useMemoryActions';
import { useSelection } from './hooks/useSelection';
import { useProject } from './hooks/useProject';
import { TimelinePage } from './pages/TimelinePage';
import { GraphPage } from './pages/GraphPage';
import type { Memory, MemoryLayer, NoteCategory } from './types';

function App() {
  const { t } = useTranslation();
  const [currentView, setCurrentView] = useState<ViewType>('search');
  const [selectedLayer, setSelectedLayer] = useState<MemoryLayer | null>(null);

  // Project management
  const { currentProject, switchProject } = useProject();
  const [selectedCategories, setSelectedCategories] = useState<NoteCategory[]>([]);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [selectedMemory, setSelectedMemory] = useState<Memory | null>(null);
  const [batchDeleteDialogOpen, setBatchDeleteDialogOpen] = useState(false);
  const [batchOperating, setBatchOperating] = useState(false);

  // Use the first selected category for filtering (API supports single category)
  const filterCategory = selectedCategories.length === 1 ? selectedCategories[0] : undefined;

  const {
    memories,
    loading,
    error,
    search,
    isSearching,
    searchQuery,
    clearSearch,
    refresh,
  } = useMemories({
    layer: selectedLayer || undefined,
    category: filterCategory,
    limit: 100,
  });

  const { verify, remove, update, deleting, updating } = useMemoryActions();

  // Selection state for batch operations
  const {
    selectedIds,
    toggle: toggleSelection,
    selectAll,
    deselectAll,
    selectedCount,
    isSelectionMode,
    enterSelectionMode,
    exitSelectionMode,
  } = useSelection<Memory>();

  // Filter memories by categories client-side when multiple selected
  const filteredMemories = selectedCategories.length > 1
    ? memories.filter(m => m.category && selectedCategories.includes(m.category))
    : memories;

  const handleLayerChange = useCallback((layer: MemoryLayer | null) => {
    setSelectedLayer(layer);
  }, []);

  const handleCategoryToggle = useCallback((category: NoteCategory) => {
    setSelectedCategories((prev) =>
      prev.includes(category)
        ? prev.filter((c) => c !== category)
        : [...prev, category]
    );
  }, []);

  const handleClearFilters = useCallback(() => {
    setSelectedLayer(null);
    setSelectedCategories([]);
  }, []);

  const handleVerify = useCallback(async (id: string) => {
    setVerifyingId(id);
    const result = await verify(id);
    setVerifyingId(null);
    if (result) {
      refresh();
    }
  }, [verify, refresh]);

  const handleDeleteClick = useCallback((id: string) => {
    setPendingDeleteId(id);
    setDeleteDialogOpen(true);
  }, []);

  const handleDeleteConfirm = useCallback(async () => {
    if (pendingDeleteId) {
      const success = await remove(pendingDeleteId);
      if (success) {
        refresh();
      }
    }
    setDeleteDialogOpen(false);
    setPendingDeleteId(null);
  }, [pendingDeleteId, remove, refresh]);

  const handleDeleteCancel = useCallback(() => {
    setDeleteDialogOpen(false);
    setPendingDeleteId(null);
  }, []);

  const handleCardClick = useCallback((memory: Memory) => {
    setSelectedMemory(memory);
  }, []);

  const handleDetailClose = useCallback(() => {
    setSelectedMemory(null);
  }, []);

  const handleDetailVerify = useCallback(async (id: string) => {
    setVerifyingId(id);
    const result = await verify(id);
    setVerifyingId(null);
    if (result) {
      // Update the selected memory with verified state
      setSelectedMemory((prev) => prev && prev.id === id ? { ...prev, confidence: 1 } : prev);
      refresh();
    }
  }, [verify, refresh]);

  const handleDetailDelete = useCallback((id: string) => {
    setSelectedMemory(null);
    setPendingDeleteId(id);
    setDeleteDialogOpen(true);
  }, []);

  const handleDetailSave = useCallback(async (
    id: string,
    data: { content?: string; session_id?: string; related_files?: string[] }
  ): Promise<boolean> => {
    const result = await update(id, data);
    if (result) {
      setSelectedMemory(result);
      refresh();
      return true;
    }
    return false;
  }, [update, refresh]);

  // Batch operations
  const handleSelectAll = useCallback(() => {
    selectAll(filteredMemories);
  }, [selectAll, filteredMemories]);

  const handleBatchDeleteClick = useCallback(() => {
    if (selectedCount > 0) {
      setBatchDeleteDialogOpen(true);
    }
  }, [selectedCount]);

  const handleBatchDeleteConfirm = useCallback(async () => {
    setBatchOperating(true);
    const ids = Array.from(selectedIds);
    let successCount = 0;

    for (const id of ids) {
      const success = await remove(id);
      if (success) successCount++;
    }

    setBatchOperating(false);
    setBatchDeleteDialogOpen(false);

    if (successCount > 0) {
      exitSelectionMode();
      refresh();
    }
  }, [selectedIds, remove, exitSelectionMode, refresh]);

  const handleBatchDeleteCancel = useCallback(() => {
    setBatchDeleteDialogOpen(false);
  }, []);

  const handleBatchVerify = useCallback(async () => {
    setBatchOperating(true);
    const ids = Array.from(selectedIds);
    let successCount = 0;

    for (const id of ids) {
      const memory = filteredMemories.find((m) => m.id === id);
      if (memory && memory.confidence < 1) {
        const success = await verify(id);
        if (success) successCount++;
      }
    }

    setBatchOperating(false);

    if (successCount > 0) {
      exitSelectionMode();
      refresh();
    }
  }, [selectedIds, filteredMemories, verify, exitSelectionMode, refresh]);

  return (
    <div className="min-h-screen bg-gray-50/50">
      <Header
        memoryCount={filteredMemories.length}
        isLoading={loading}
        currentView={currentView}
        onViewChange={setCurrentView}
        currentProject={currentProject}
        onProjectChange={switchProject}
      />

      <main className="max-w-7xl mx-auto px-6 lg:px-8 py-8">
        {currentView === 'timeline' ? (
          <TimelinePage />
        ) : currentView === 'graph' ? (
          <GraphPage />
        ) : (
          <div className="flex gap-8">
            {/* Left sidebar - Filters */}
            <FilterPanel
              selectedLayer={selectedLayer}
              selectedCategories={selectedCategories}
              onLayerChange={handleLayerChange}
              onCategoryToggle={handleCategoryToggle}
              onClearFilters={handleClearFilters}
            />

            {/* Main content */}
            <div className="flex-1 min-w-0">
              {/* Search bar */}
              <div className="mb-8">
                <SearchBar
                  onSearch={search}
                  onClear={clearSearch}
                  isSearching={isSearching}
                  currentQuery={searchQuery}
                />
              </div>

              {/* Memory list */}
              <MemoryList
                memories={filteredMemories}
                loading={loading}
                error={error}
                searchQuery={searchQuery}
                onVerify={handleVerify}
                onDelete={handleDeleteClick}
                onCardClick={handleCardClick}
                verifyingId={verifyingId}
                selectionMode={isSelectionMode}
                selectedIds={selectedIds}
                onSelect={toggleSelection}
                onSelectAll={handleSelectAll}
                onDeselectAll={deselectAll}
                onBatchDelete={handleBatchDeleteClick}
                onBatchVerify={handleBatchVerify}
                onEnterSelectionMode={enterSelectionMode}
                onExitSelectionMode={exitSelectionMode}
              />
            </div>
          </div>
        )}
      </main>

      {/* Delete confirmation dialog */}
      <ConfirmDialog
        isOpen={deleteDialogOpen}
        title={t('dialog.deleteTitle')}
        message={t('dialog.deleteMessage')}
        confirmText={t('common.delete')}
        cancelText={t('common.cancel')}
        confirmVariant="danger"
        loading={deleting}
        onConfirm={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
      />

      {/* Batch delete confirmation dialog */}
      <ConfirmDialog
        isOpen={batchDeleteDialogOpen}
        title={t('batch.deleteConfirmTitle')}
        message={t('batch.deleteConfirmMessage', { count: selectedCount })}
        confirmText={t('batch.deleteButton', { count: selectedCount })}
        cancelText={t('common.cancel')}
        confirmVariant="danger"
        loading={batchOperating}
        onConfirm={handleBatchDeleteConfirm}
        onCancel={handleBatchDeleteCancel}
      />

      {/* Memory detail modal */}
      {selectedMemory && (
        <MemoryDetail
          memory={selectedMemory}
          isOpen={!!selectedMemory}
          onClose={handleDetailClose}
          onVerify={handleDetailVerify}
          onDelete={handleDetailDelete}
          onSave={handleDetailSave}
          verifying={verifyingId === selectedMemory.id}
          saving={updating}
        />
      )}
    </div>
  );
}

export default App;
