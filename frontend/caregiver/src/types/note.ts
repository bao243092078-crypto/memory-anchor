// 记忆层级
export type MemoryLayer = 'constitution' | 'fact' | 'session';

// 记忆分类
export type NoteCategory = 'person' | 'place' | 'event' | 'item' | 'routine';

// 便利贴
export interface Note {
  id: string;
  content: string;
  layer: MemoryLayer;
  category: NoteCategory | null;
  priority: number;  // 0-999, 0最高
  confidence: number;  // 0-1
  created_by: string;
  created_at: string;
  expires_at: string | null;
  is_active: boolean;
}

// 创建便利贴请求
export interface CreateNoteRequest {
  content: string;
  layer?: MemoryLayer;
  category?: NoteCategory;
  priority?: number;
}

// 更新便利贴请求
export interface UpdateNoteRequest {
  content?: string;
  category?: NoteCategory;
  priority?: number;
  is_active?: boolean;
}

// 便利贴列表查询参数
export interface NotesQueryParams {
  layer?: MemoryLayer;
  category?: NoteCategory;
  active_only?: boolean;
  limit?: number;
  offset?: number;
}

// 搜索参数
export interface SearchParams {
  q: string;
  limit?: number;
  layer?: MemoryLayer;
  category?: NoteCategory;
}

// 搜索结果项（包含便利贴和分数）
export interface SearchResultItem {
  note: Note;
  score?: number;
}

// 搜索结果
export interface SearchResult {
  id: string;
  content: string;
  layer: MemoryLayer;
  category: NoteCategory | null;
  score: number;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
}

// 层级显示配置
export const LAYER_CONFIG: Record<MemoryLayer, { label: string; color: string; bgColor: string }> = {
  constitution: { label: '宪法层', color: 'text-red-600', bgColor: 'bg-red-50' },
  fact: { label: '事实层', color: 'text-blue-600', bgColor: 'bg-blue-50' },
  session: { label: '会话层', color: 'text-green-600', bgColor: 'bg-green-50' },
};

// 分类显示配置
export const CATEGORY_CONFIG: Record<NoteCategory, { label: string; icon: string }> = {
  person: { label: '人物', icon: '👤' },
  place: { label: '地点', icon: '📍' },
  event: { label: '事件', icon: '📅' },
  item: { label: '物品', icon: '📦' },
  routine: { label: '日常', icon: '🔄' },
};
