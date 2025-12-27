// 五层认知记忆模型 (v2.0)
// L0: identity_schema (自我概念) - 核心身份，需三次审批
// L1: active_context (工作记忆) - 会话临时，不持久化
// L2: event_log (情景记忆) - 带时空标记，可设 TTL
// L3: verified_fact (语义记忆) - 验证过的长期事实
// L4: operational_knowledge (技能图式) - 操作性知识

// 新版层级（v2.0）
export type MemoryLayerV2 =
  | 'identity_schema'      // L0
  | 'active_context'       // L1
  | 'event_log'            // L2
  | 'verified_fact'        // L3
  | 'operational_knowledge'; // L4

// 旧版层级（v1.x 向后兼容）
export type MemoryLayerV1 = 'constitution' | 'fact' | 'session';

// 统一类型（支持新旧两种）
export type MemoryLayer = MemoryLayerV2 | MemoryLayerV1;

export const V2_LAYERS: MemoryLayerV2[] = [
  'identity_schema',
  'active_context',
  'event_log',
  'verified_fact',
  'operational_knowledge',
];

export const NOTE_CREATION_LAYERS: MemoryLayerV2[] = [
  'identity_schema',
  'verified_fact',
  'event_log',
];

// 记忆分类
export type NoteCategory = 'person' | 'place' | 'event' | 'item' | 'routine';

// 层级映射：旧 → 新
export const LAYER_MAPPING: Record<MemoryLayerV1, MemoryLayerV2> = {
  constitution: 'identity_schema',
  fact: 'verified_fact',
  session: 'event_log',
};

// 规范化层级名称（兼容旧版）
export function normalizeLayer(layer: MemoryLayer): MemoryLayerV2 {
  if (layer in LAYER_MAPPING) {
    return LAYER_MAPPING[layer as MemoryLayerV1];
  }
  return layer as MemoryLayerV2;
}

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

// 层级显示配置（五层模型 + 向后兼容）
interface LayerConfigItem {
  label: string;
  shortLabel: string;
  color: string;
  bgColor: string;
  icon: string;
  level: number;
}

export const LAYER_CONFIG: Record<MemoryLayer, LayerConfigItem> = {
  // v2.0 五层模型
  identity_schema: {
    label: '身份图式 (L0)',
    shortLabel: 'L0',
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    icon: '🔴',
    level: 0
  },
  active_context: {
    label: '工作记忆 (L1)',
    shortLabel: 'L1',
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-50',
    icon: '🟡',
    level: 1
  },
  event_log: {
    label: '情景记忆 (L2)',
    shortLabel: 'L2',
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    icon: '🟢',
    level: 2
  },
  verified_fact: {
    label: '语义记忆 (L3)',
    shortLabel: 'L3',
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    icon: '🔵',
    level: 3
  },
  operational_knowledge: {
    label: '技能图式 (L4)',
    shortLabel: 'L4',
    color: 'text-gray-600',
    bgColor: 'bg-gray-50',
    icon: '⚪',
    level: 4
  },
  // v1.x 向后兼容（映射到新层级样式）
  constitution: {
    label: '宪法层',
    shortLabel: 'L0',
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    icon: '🔴',
    level: 0
  },
  fact: {
    label: '事实层',
    shortLabel: 'L3',
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    icon: '🔵',
    level: 3
  },
  session: {
    label: '会话层',
    shortLabel: 'L2',
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    icon: '🟢',
    level: 2
  },
};

// 分类显示配置
export const CATEGORY_CONFIG: Record<NoteCategory, { label: string; icon: string }> = {
  person: { label: '人物', icon: '👤' },
  place: { label: '地点', icon: '📍' },
  event: { label: '事件', icon: '📅' },
  item: { label: '物品', icon: '📦' },
  routine: { label: '日常', icon: '🔄' },
};
