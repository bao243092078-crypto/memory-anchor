import { apiClient } from './client';
import type {
  ConstitutionChange,
  ConstitutionChangeListResponse,
  ProposeChangeRequest,
  ChangeStatus,
} from '../types/constitution';
import type { Note } from '../types/note';

// 获取宪法层记忆
export async function getConstitution(): Promise<Note[]> {
  const { data } = await apiClient.get<{ memories: Note[] }>('/memory/constitution');
  return data.memories;
}

// 提议宪法层变更
export async function proposeChange(request: ProposeChangeRequest): Promise<ConstitutionChange> {
  const { data } = await apiClient.post<ConstitutionChange>('/constitution/propose', request);
  return data;
}

// 审批宪法层变更
export async function approveChange(changeId: string): Promise<ConstitutionChange> {
  const { data } = await apiClient.post<ConstitutionChange>(`/constitution/approve/${changeId}`);
  return data;
}

// 获取待审批变更
export async function getPendingChanges(): Promise<ConstitutionChange[]> {
  const { data } = await apiClient.get<ConstitutionChange[]>('/constitution/pending');
  return data;
}

// 获取变更历史
export async function getChangeHistory(status?: ChangeStatus): Promise<ConstitutionChangeListResponse> {
  const { data } = await apiClient.get<ConstitutionChangeListResponse>('/constitution/changes', {
    params: status ? { status } : undefined,
  });
  return data;
}

// 获取单个变更
export async function getChange(changeId: string): Promise<ConstitutionChange> {
  const { data } = await apiClient.get<ConstitutionChange>(`/constitution/changes/${changeId}`);
  return data;
}
