import { useState, useCallback } from 'react';
import { Header, SearchBar, FilterPanel, MemoryList } from './components';
import { useMemories } from './hooks/useMemories';
import type { MemoryLayer, NoteCategory } from './types';

function App() {
  const [selectedLayer, setSelectedLayer] = useState<MemoryLayer | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<NoteCategory[]>([]);

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
  } = useMemories({
    layer: selectedLayer || undefined,
    category: filterCategory,
    limit: 100,
  });

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

  return (
    <div className="min-h-screen bg-gray-50/50">
      <Header memoryCount={filteredMemories.length} isLoading={loading} />

      <main className="max-w-7xl mx-auto px-6 lg:px-8 py-8">
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
            />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
