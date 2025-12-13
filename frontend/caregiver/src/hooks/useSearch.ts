import { useQuery } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import { searchNotes, type SearchParams } from '../api/search';

// Query keys
export const searchKeys = {
  all: ['search'] as const,
  results: (params: SearchParams) => [...searchKeys.all, params] as const,
};

// 搜索 hook（带防抖）
export function useSearch(params: SearchParams, debounceMs = 300) {
  const [debouncedParams, setDebouncedParams] = useState(params);

  // 防抖处理
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedParams(params);
    }, debounceMs);

    return () => clearTimeout(timer);
  }, [params, debounceMs]);

  return useQuery({
    queryKey: searchKeys.results(debouncedParams),
    queryFn: () => searchNotes(debouncedParams),
    enabled: !!debouncedParams.q && debouncedParams.q.length >= 2,
  });
}
