import { useState, useCallback, useMemo } from 'react';

export interface UseSelectionResult<T> {
  selectedIds: Set<string>;
  isSelected: (id: string) => boolean;
  toggle: (id: string) => void;
  selectAll: (items: T[]) => void;
  deselectAll: () => void;
  isAllSelected: (items: T[]) => boolean;
  isSomeSelected: (items: T[]) => boolean;
  selectedCount: number;
  isSelectionMode: boolean;
  enterSelectionMode: () => void;
  exitSelectionMode: () => void;
}

export function useSelection<T extends { id: string }>(): UseSelectionResult<T> {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isSelectionMode, setIsSelectionMode] = useState(false);

  const isSelected = useCallback((id: string) => selectedIds.has(id), [selectedIds]);

  const toggle = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const selectAll = useCallback((items: T[]) => {
    setSelectedIds(new Set(items.map((item) => item.id)));
  }, []);

  const deselectAll = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const isAllSelected = useCallback(
    (items: T[]) => items.length > 0 && items.every((item) => selectedIds.has(item.id)),
    [selectedIds]
  );

  const isSomeSelected = useCallback(
    (items: T[]) => items.some((item) => selectedIds.has(item.id)),
    [selectedIds]
  );

  const selectedCount = useMemo(() => selectedIds.size, [selectedIds]);

  const enterSelectionMode = useCallback(() => {
    setIsSelectionMode(true);
  }, []);

  const exitSelectionMode = useCallback(() => {
    setIsSelectionMode(false);
    setSelectedIds(new Set());
  }, []);

  return {
    selectedIds,
    isSelected,
    toggle,
    selectAll,
    deselectAll,
    isAllSelected,
    isSomeSelected,
    selectedCount,
    isSelectionMode,
    enterSelectionMode,
    exitSelectionMode,
  };
}
