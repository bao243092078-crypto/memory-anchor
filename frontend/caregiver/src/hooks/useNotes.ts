import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getNotes, getNote, createNote, updateNote, deleteNote } from '../api/notes';
import type { CreateNoteRequest, UpdateNoteRequest, NotesQueryParams } from '../types/note';

// Query keys
export const noteKeys = {
  all: ['notes'] as const,
  lists: () => [...noteKeys.all, 'list'] as const,
  list: (params?: NotesQueryParams) => [...noteKeys.lists(), params] as const,
  details: () => [...noteKeys.all, 'detail'] as const,
  detail: (id: string) => [...noteKeys.details(), id] as const,
};

// 获取便利贴列表
export function useNotes(params?: NotesQueryParams) {
  return useQuery({
    queryKey: noteKeys.list(params),
    queryFn: () => getNotes(params),
  });
}

// 获取单个便利贴
export function useNote(id: string) {
  return useQuery({
    queryKey: noteKeys.detail(id),
    queryFn: () => getNote(id),
    enabled: !!id,
  });
}

// 创建便利贴
export function useCreateNote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (note: CreateNoteRequest) => createNote(note),
    onSuccess: () => {
      // 刷新列表
      queryClient.invalidateQueries({ queryKey: noteKeys.lists() });
    },
  });
}

// 更新便利贴
export function useUpdateNote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, note }: { id: string; note: UpdateNoteRequest }) =>
      updateNote(id, note),
    onSuccess: (data, { id }) => {
      // 更新缓存
      queryClient.setQueryData(noteKeys.detail(id), data);
      // 刷新列表
      queryClient.invalidateQueries({ queryKey: noteKeys.lists() });
    },
  });
}

// 删除便利贴
export function useDeleteNote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => deleteNote(id),
    onSuccess: () => {
      // 刷新列表
      queryClient.invalidateQueries({ queryKey: noteKeys.lists() });
    },
  });
}
