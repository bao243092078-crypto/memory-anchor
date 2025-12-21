// Checklist 状态
export type ChecklistStatus = 'open' | 'done' | 'cancelled';

// Checklist 作用域
export type ChecklistScope = 'project' | 'session' | 'global';

// Checklist 优先级（1=critical, 5=backlog）
export type ChecklistPriority = 1 | 2 | 3 | 4 | 5;

// Checklist 项
export interface ChecklistItem {
  id: string;
  content: string;
  status: ChecklistStatus;
  scope: ChecklistScope;
  priority: ChecklistPriority;
  tags: string[];
  project_id: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  expires_at?: string;
}

// 创建 Checklist 项请求
export interface CreateChecklistItemRequest {
  project_id: string;
  content: string;
  scope?: ChecklistScope;
  priority?: ChecklistPriority;
  tags?: string[];
  expires_at?: string;
}

// 更新 Checklist 项请求
export interface UpdateChecklistItemRequest {
  status?: ChecklistStatus;
  content?: string;
  priority?: ChecklistPriority;
  tags?: string[];
  expires_at?: string;
}

// Checklist 简报响应
export interface ChecklistBriefingResponse {
  markdown: string;
  items: ChecklistItem[];
  total: number;
  by_priority: {
    [key in ChecklistPriority]: number;
  };
  by_status: {
    [key in ChecklistStatus]: number;
  };
}

// 从 Plan 同步请求
export interface SyncFromPlanRequest {
  project_id: string;
  plan_markdown: string;
  session_id?: string;
}

// 优先级配置
export const PRIORITY_CONFIG: Record<
  ChecklistPriority,
  { label: string; color: string; icon: string; bgColor: string }
> = {
  1: { label: '紧急', color: 'text-red-600', icon: '🔴', bgColor: 'bg-red-50' },
  2: { label: '高优', color: 'text-orange-600', icon: '🟠', bgColor: 'bg-orange-50' },
  3: { label: '普通', color: 'text-yellow-600', icon: '🟡', bgColor: 'bg-yellow-50' },
  4: { label: '低优', color: 'text-green-600', icon: '🟢', bgColor: 'bg-green-50' },
  5: { label: '待定', color: 'text-gray-600', icon: '⚪', bgColor: 'bg-gray-50' },
};

// 状态配置
export const STATUS_CONFIG: Record<
  ChecklistStatus,
  { label: string; color: string; icon: string }
> = {
  open: { label: '待处理', color: 'text-blue-600', icon: '⏳' },
  done: { label: '已完成', color: 'text-green-600', icon: '✅' },
  cancelled: { label: '已取消', color: 'text-gray-600', icon: '❌' },
};

// 作用域配置
export const SCOPE_CONFIG: Record<
  ChecklistScope,
  { label: string; color: string; description: string }
> = {
  project: {
    label: '项目级',
    color: 'text-purple-600',
    description: '仅限当前项目'
  },
  session: {
    label: '会话级',
    color: 'text-blue-600',
    description: '当前会话临时任务'
  },
  global: {
    label: '全局',
    color: 'text-gray-600',
    description: '跨项目通用任务'
  },
};
