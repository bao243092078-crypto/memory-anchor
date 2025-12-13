import { apiClient } from './client';
import type { SearchResponse, MemoryLayer, NoteCategory } from '../types/note';

export interface SearchParams {
  q: string;
  limit?: number;
  layer?: MemoryLayer;
  category?: NoteCategory;
  only_active?: boolean;
}

// 语义搜索
export async function searchNotes(params: SearchParams): Promise<SearchResponse> {
  const { data } = await apiClient.get<SearchResponse>('/search', { params });
  return data;
}

// 获取搜索统计
export async function getSearchStats(): Promise<{ total_notes: number; indexed_notes: number }> {
  const { data } = await apiClient.get('/search/stats');
  return data;
}
