// Memory layer types
export type MemoryLayer =
  | 'identity_schema'   // L0
  | 'active_context'    // L1
  | 'event_log'         // L2
  | 'verified_fact'     // L3
  | 'operational_knowledge'  // L4
  // Legacy names (backward compatible)
  | 'constitution'
  | 'fact'
  | 'session';

export type NoteCategory = 'person' | 'place' | 'event' | 'item' | 'routine';

export interface Memory {
  id: string;
  content: string;
  layer: MemoryLayer;
  category?: NoteCategory;
  confidence: number;
  created_at: string;
  // v2.1 traceability fields
  session_id?: string;
  related_files?: string[];
  // Search result field
  score?: number;
}

export interface SearchRequest {
  query: string;
  layer?: MemoryLayer;
  category?: NoteCategory;
  limit?: number;
}

export interface SearchResponse {
  memories: Memory[];
  total: number;
}

// Layer display config
export const LAYER_CONFIG: Record<string, { label: string; color: string; shortLabel: string }> = {
  identity_schema: { label: 'L0 身份图式', color: 'bg-red-500', shortLabel: 'L0' },
  constitution: { label: 'L0 身份图式', color: 'bg-red-500', shortLabel: 'L0' },
  active_context: { label: 'L1 工作记忆', color: 'bg-orange-500', shortLabel: 'L1' },
  event_log: { label: 'L2 事件日志', color: 'bg-yellow-500', shortLabel: 'L2' },
  session: { label: 'L2 事件日志', color: 'bg-yellow-500', shortLabel: 'L2' },
  verified_fact: { label: 'L3 验证事实', color: 'bg-green-500', shortLabel: 'L3' },
  fact: { label: 'L3 验证事实', color: 'bg-green-500', shortLabel: 'L3' },
  operational_knowledge: { label: 'L4 操作知识', color: 'bg-blue-500', shortLabel: 'L4' },
};

export const CATEGORY_CONFIG: Record<NoteCategory, { label: string; emoji: string }> = {
  person: { label: '人物', emoji: '👤' },
  place: { label: '地点', emoji: '📍' },
  event: { label: '事件', emoji: '📅' },
  item: { label: '物品', emoji: '📦' },
  routine: { label: '习惯', emoji: '🔄' },
};
