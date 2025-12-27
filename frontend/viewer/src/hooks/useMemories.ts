import { useState, useEffect, useCallback } from 'react';
import type { Memory, MemoryLayer, NoteCategory } from '../types';
import { listMemories, searchMemories, getConstitution } from '../api/memory';

interface UseMemoriesOptions {
  layer?: MemoryLayer;
  category?: NoteCategory;
  limit?: number;
}

interface UseMemoriesReturn {
  memories: Memory[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
  search: (query: string) => Promise<void>;
  isSearching: boolean;
  searchQuery: string;
  clearSearch: () => void;
}

export function useMemories(options: UseMemoriesOptions = {}): UseMemoriesReturn {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const fetchMemories = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch regular memories
      const regularMemories = await listMemories({
        layer: options.layer,
        category: options.category,
        limit: options.limit || 50,
      });

      // Also fetch constitution if no layer filter or if layer is identity_schema
      let allMemories = regularMemories;
      if (!options.layer || options.layer === 'identity_schema' || options.layer === 'constitution') {
        try {
          const constitutionMemories = await getConstitution();
          // Filter constitution by category if specified
          const filteredConstitution = options.category
            ? constitutionMemories.filter(m => m.category === options.category)
            : constitutionMemories;
          allMemories = [...filteredConstitution, ...regularMemories];
        } catch {
          // Constitution might not exist, ignore error
        }
      }

      // Sort by created_at descending
      allMemories.sort((a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );

      setMemories(allMemories);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch memories');
    } finally {
      setLoading(false);
    }
  }, [options.layer, options.category, options.limit]);

  const search = useCallback(async (query: string) => {
    if (!query.trim()) {
      setSearchQuery('');
      await fetchMemories();
      return;
    }

    setIsSearching(true);
    setSearchQuery(query);
    setError(null);
    try {
      const results = await searchMemories({
        query,
        layer: options.layer,
        category: options.category,
        limit: options.limit || 50,
      });
      setMemories(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setIsSearching(false);
    }
  }, [options.layer, options.category, options.limit, fetchMemories]);

  const clearSearch = useCallback(() => {
    setSearchQuery('');
    fetchMemories();
  }, [fetchMemories]);

  useEffect(() => {
    if (!searchQuery) {
      fetchMemories();
    }
  }, [fetchMemories, searchQuery]);

  return {
    memories,
    loading,
    error,
    refresh: fetchMemories,
    search,
    isSearching,
    searchQuery,
    clearSearch,
  };
}
