import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getChecklistBriefing,
  getChecklistItems,
  createChecklistItem,
  updateChecklistItem,
  deleteChecklistItem,
  syncFromPlan,
} from '../api/checklist';
import type {
  CreateChecklistItemRequest,
  UpdateChecklistItemRequest,
  SyncFromPlanRequest,
  ChecklistScope,
} from '../types/checklist';

// Query keys
const checklistKeys = {
  all: ['checklist'] as const,
  briefing: (projectId: string, scope?: ChecklistScope, limit?: number) =>
    [...checklistKeys.all, 'briefing', projectId, scope, limit] as const,
  items: (projectId: string, filters?: Record<string, unknown>) =>
    [...checklistKeys.all, 'items', projectId, filters] as const,
};

// 获取 Checklist 简报
export function useChecklistBriefing(
  projectId: string,
  scope?: ChecklistScope,
  limit: number = 12
) {
  return useQuery({
    queryKey: checklistKeys.briefing(projectId, scope, limit),
    queryFn: () => getChecklistBriefing(projectId, scope, limit),
    enabled: !!projectId,
  });
}

// 获取 Checklist 列表
export function useChecklistItems(
  projectId: string,
  filters?: {
    scope?: ChecklistScope;
    status?: string;
    priority?: number;
    limit?: number;
  }
) {
  return useQuery({
    queryKey: checklistKeys.items(projectId, filters),
    queryFn: () => getChecklistItems(projectId, filters),
    enabled: !!projectId,
  });
}

// 创建 Checklist 项
export function useCreateChecklistItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (item: CreateChecklistItemRequest) => createChecklistItem(item),
    onSuccess: () => {
      // 重新获取所有相关数据
      queryClient.invalidateQueries({ queryKey: checklistKeys.all });
    },
  });
}

// 更新 Checklist 项
export function useUpdateChecklistItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ itemId, update }: { itemId: string; update: UpdateChecklistItemRequest }) =>
      updateChecklistItem(itemId, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: checklistKeys.all });
    },
  });
}

// 删除 Checklist 项
export function useDeleteChecklistItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (itemId: string) => deleteChecklistItem(itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: checklistKeys.all });
    },
  });
}

// 从 Plan 同步
export function useSyncFromPlan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: SyncFromPlanRequest) => syncFromPlan(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: checklistKeys.all });
    },
  });
}
