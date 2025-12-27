import { useState, useCallback } from 'react';
import type { Memory } from '../types';
import { verifyMemory, deleteMemory, updateMemory } from '../api/memory';

interface UpdateData {
  content?: string;
  session_id?: string;
  related_files?: string[];
}

interface UseMemoryActionsReturn {
  verifying: boolean;
  deleting: boolean;
  updating: boolean;
  error: string | null;
  verify: (id: string) => Promise<Memory | null>;
  remove: (id: string) => Promise<boolean>;
  update: (id: string, data: UpdateData) => Promise<Memory | null>;
  clearError: () => void;
}

export function useMemoryActions(): UseMemoryActionsReturn {
  const [verifying, setVerifying] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [updating, setUpdating] = useState(false);
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

  const update = useCallback(async (id: string, data: UpdateData): Promise<Memory | null> => {
    setUpdating(true);
    setError(null);
    try {
      const updated = await updateMemory(id, data);
      return updated;
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败');
      return null;
    } finally {
      setUpdating(false);
    }
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    verifying,
    deleting,
    updating,
    error,
    verify,
    remove,
    update,
    clearError,
  };
}
