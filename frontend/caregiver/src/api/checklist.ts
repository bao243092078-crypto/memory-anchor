import { apiClient } from './client';
import type {
  ChecklistItem,
  ChecklistBriefingResponse,
  CreateChecklistItemRequest,
  UpdateChecklistItemRequest,
  SyncFromPlanRequest,
  ChecklistScope,
} from '../types/checklist';

// 获取 Checklist 简报
export async function getChecklistBriefing(
  projectId: string,
  scope?: ChecklistScope,
  limit: number = 12
): Promise<ChecklistBriefingResponse> {
  const { data } = await apiClient.get<ChecklistBriefingResponse>('/checklist/briefing', {
    params: {
      project_id: projectId,
      scope,
      limit,
    },
  });
  return data;
}

// 获取 Checklist 列表
export async function getChecklistItems(
  projectId: string,
  params?: {
    scope?: ChecklistScope;
    status?: string;
    priority?: number;
    limit?: number;
  }
): Promise<ChecklistItem[]> {
  const { data } = await apiClient.get<ChecklistItem[]>('/checklist/items', {
    params: {
      project_id: projectId,
      ...params,
    },
  });
  return data;
}

// 创建 Checklist 项
export async function createChecklistItem(
  item: CreateChecklistItemRequest
): Promise<ChecklistItem> {
  const { data } = await apiClient.post<ChecklistItem>('/checklist/items', item);
  return data;
}

// 更新 Checklist 项
export async function updateChecklistItem(
  itemId: string,
  update: UpdateChecklistItemRequest
): Promise<ChecklistItem> {
  const { data } = await apiClient.put<ChecklistItem>(`/checklist/items/${itemId}`, update);
  return data;
}

// 删除 Checklist 项
export async function deleteChecklistItem(itemId: string): Promise<void> {
  await apiClient.delete(`/checklist/items/${itemId}`);
}

// 从 Plan 同步
export async function syncFromPlan(request: SyncFromPlanRequest): Promise<ChecklistItem[]> {
  const { data } = await apiClient.post<ChecklistItem[]>('/checklist/sync', request);
  return data;
}
