import { useMemo } from 'react';
import type { Memory, MemoryLayer } from '../types';
import type { TimeRange, Granularity } from '../components/timeline/TimelineFilters';

export interface TimelineData {
  date: string;  // "2025-12-27" or "2025-W52" or "2025-12"
  label: string; // Display label
  L0: number;    // identity_schema
  L2: number;    // event_log
  L3: number;    // verified_fact
  L4: number;    // operational_knowledge
  total: number;
}

export interface UseTimelineDataOptions {
  timeRange?: TimeRange;
  granularity?: Granularity;
}

// Map layer names to standardized keys
const layerToKey = (layer: MemoryLayer): 'L0' | 'L2' | 'L3' | 'L4' | null => {
  switch (layer) {
    case 'identity_schema':
    case 'constitution':
      return 'L0';
    case 'event_log':
    case 'session':
      return 'L2';
    case 'verified_fact':
    case 'fact':
      return 'L3';
    case 'operational_knowledge':
      return 'L4';
    case 'active_context':
      return null; // L1 is not persisted
    default:
      return null;
  }
};

// Get start date based on time range
const getStartDate = (timeRange: TimeRange): Date | null => {
  if (timeRange === 'all') return null;

  const now = new Date();
  const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : 90;
  const start = new Date(now);
  start.setDate(start.getDate() - days);
  start.setHours(0, 0, 0, 0);
  return start;
};

// Format date based on granularity
const formatDateByGranularity = (date: Date, granularity: Granularity): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');

  switch (granularity) {
    case 'day':
      return `${year}-${month}-${day}`;
    case 'week': {
      // Get ISO week number
      const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
      const dayNum = d.getUTCDay() || 7;
      d.setUTCDate(d.getUTCDate() + 4 - dayNum);
      const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
      const weekNo = Math.ceil((((d.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
      return `${d.getUTCFullYear()}-W${String(weekNo).padStart(2, '0')}`;
    }
    case 'month':
      return `${year}-${month}`;
  }
};

// Get display label for date key
const getDateLabel = (dateKey: string, granularity: Granularity): string => {
  switch (granularity) {
    case 'day': {
      const date = new Date(dateKey);
      return `${date.getMonth() + 1}/${date.getDate()}`;
    }
    case 'week': {
      // Format: "W52"
      const weekMatch = dateKey.match(/W(\d+)/);
      return weekMatch ? `第${parseInt(weekMatch[1])}周` : dateKey;
    }
    case 'month': {
      // Format: "12月"
      const monthMatch = dateKey.match(/-(\d+)$/);
      return monthMatch ? `${parseInt(monthMatch[1])}月` : dateKey;
    }
  }
};

// Generate all date keys in range based on granularity
const generateDateKeys = (
  startDate: Date,
  endDate: Date,
  granularity: Granularity
): string[] => {
  const keys: string[] = [];
  const current = new Date(startDate);

  while (current <= endDate) {
    const key = formatDateByGranularity(current, granularity);
    if (!keys.includes(key)) {
      keys.push(key);
    }

    switch (granularity) {
      case 'day':
        current.setDate(current.getDate() + 1);
        break;
      case 'week':
        current.setDate(current.getDate() + 7);
        break;
      case 'month':
        current.setMonth(current.getMonth() + 1);
        break;
    }
  }

  return keys;
};

export function useTimelineData(
  memories: Memory[],
  options: UseTimelineDataOptions = {}
): TimelineData[] {
  const { timeRange = 'all', granularity = 'day' } = options;

  return useMemo(() => {
    if (memories.length === 0) {
      return [];
    }

    // Filter by time range
    const startDate = getStartDate(timeRange);
    const filteredMemories = startDate
      ? memories.filter((m) => new Date(m.created_at) >= startDate)
      : memories;

    if (filteredMemories.length === 0) {
      return [];
    }

    // Find date range
    let minDate = new Date();
    let maxDate = new Date(0);

    filteredMemories.forEach((memory) => {
      const date = new Date(memory.created_at);
      if (date < minDate) minDate = date;
      if (date > maxDate) maxDate = date;
    });

    // Generate all date keys
    const allKeys = generateDateKeys(minDate, maxDate, granularity);

    // Initialize map with all keys
    const dataMap = new Map<string, TimelineData>();
    allKeys.forEach((key) => {
      dataMap.set(key, {
        date: key,
        label: getDateLabel(key, granularity),
        L0: 0,
        L2: 0,
        L3: 0,
        L4: 0,
        total: 0,
      });
    });

    // Count memories by date key and layer
    filteredMemories.forEach((memory) => {
      const date = new Date(memory.created_at);
      const dateKey = formatDateByGranularity(date, granularity);
      const layerKey = layerToKey(memory.layer);

      if (!layerKey) return;

      const entry = dataMap.get(dateKey);
      if (entry) {
        entry[layerKey]++;
        entry.total++;
      }
    });

    // Convert to sorted array
    return Array.from(dataMap.values()).sort((a, b) => {
      // Sort by date key string (works for all formats)
      return a.date.localeCompare(b.date);
    });
  }, [memories, timeRange, granularity]);
}

// Layer colors for the chart (matching types.ts LAYER_CONFIG)
export const TIMELINE_COLORS = {
  L0: '#EF4444',  // red-500
  L2: '#EAB308',  // yellow-500
  L3: '#22C55E',  // green-500
  L4: '#3B82F6',  // blue-500
};

// Layer labels
export const TIMELINE_LABELS = {
  L0: 'L0 身份图式',
  L2: 'L2 事件日志',
  L3: 'L3 验证事实',
  L4: 'L4 操作知识',
};
