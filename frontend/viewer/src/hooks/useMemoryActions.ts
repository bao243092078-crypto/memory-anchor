import { useState, useCallback } from 'react';
import type { Memory } from '../types';
import { verifyMemory, deleteMemory } from '../api/memory';

interface UseMemoryActionsReturn {
  verifying: boolean;
  deleting: boolean;
  error: string | null;
  verify: (id: string) => Promise<Memory | null>;
  remove: (id: string) => Promise<boolean>;
  clearError: () => void;
}

export function useMemoryActions(): UseMemoryActionsReturn {
  const [verifying, setVerifying] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const verify = useCallback(async (id: string): Promise<Memory | null> => {
    setVerifying(true);
    setError(null);
    try {
      const updated = await verifyMemory(id);
      return updated;
    } catch (err) {
      setError(err instanceof Error ? err.message : '确认失败');
      return null;
    } finally {
      setVerifying(false);
    }
  }, []);

  const remove = useCallback(async (id: string): Promise<boolean> => {
    setDeleting(true);
    setError(null);
    try {
      await deleteMemory(id);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败');
      return false;
    } finally {
      setDeleting(false);
    }
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    verifying,
    deleting,
    error,
    verify,
    remove,
    clearError,
  };
}
