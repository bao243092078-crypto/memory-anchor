import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getConstitution,
  proposeChange,
  approveChange,
  getPendingChanges,
  getChangeHistory,
} from '../api/constitution';
import type { ProposeChangeRequest, ChangeStatus } from '../types/constitution';

// Query keys
export const constitutionKeys = {
  all: ['constitution'] as const,
  memories: () => [...constitutionKeys.all, 'memories'] as const,
  pending: () => [...constitutionKeys.all, 'pending'] as const,
  history: (status?: ChangeStatus) => [...constitutionKeys.all, 'history', status] as const,
};

// 获取宪法层记忆
export function useConstitution() {
  return useQuery({
    queryKey: constitutionKeys.memories(),
    queryFn: getConstitution,
  });
}

// 获取待审批变更
export function usePendingChanges() {
  return useQuery({
    queryKey: constitutionKeys.pending(),
    queryFn: getPendingChanges,
  });
}

// 获取变更历史
export function useChangeHistory(status?: ChangeStatus) {
  return useQuery({
    queryKey: constitutionKeys.history(status),
    queryFn: () => getChangeHistory(status),
  });
}

// 提议变更
export function useProposeChange() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: ProposeChangeRequest) => proposeChange(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: constitutionKeys.pending() });
    },
  });
}

// 审批变更
export function useApproveChange() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (changeId: string) => approveChange(changeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: constitutionKeys.pending() });
      queryClient.invalidateQueries({ queryKey: constitutionKeys.memories() });
    },
  });
}

// 提议宪法层变更（别名，方便使用）
export const useProposeConstitutionChange = useProposeChange;

// 拒绝变更（暂时返回空操作，后端暂无此接口）
export function useRejectChange() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (_changeId: string) => {
      // TODO: 后端暂无 reject 接口，先返回空
      console.warn('Reject API not implemented yet');
      return null;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: constitutionKeys.pending() });
    },
  });
}
