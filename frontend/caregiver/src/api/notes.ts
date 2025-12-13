import { apiClient } from './client';
import type {
  Note,
  CreateNoteRequest,
  UpdateNoteRequest,
  NotesQueryParams,
} from '../types/note';

// 获取便利贴列表
export async function getNotes(params?: NotesQueryParams): Promise<Note[]> {
  const { data } = await apiClient.get<Note[]>('/notes', { params });
  return data;
}

// 获取单个便利贴
export async function getNote(id: string): Promise<Note> {
  const { data } = await apiClient.get<Note>(`/notes/${id}`);
  return data;
}

// 创建便利贴
export async function createNote(note: CreateNoteRequest): Promise<Note> {
  const { data } = await apiClient.post<Note>('/notes', note);
  return data;
}

// 更新便利贴
export async function updateNote(id: string, note: UpdateNoteRequest): Promise<Note> {
  const { data } = await apiClient.patch<Note>(`/notes/${id}`, note);
  return data;
}

// 删除便利贴（软删除）
export async function deleteNote(id: string): Promise<void> {
  await apiClient.delete(`/notes/${id}`);
}
