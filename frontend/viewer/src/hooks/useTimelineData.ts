import { useMemo } from 'react';
import type { Memory, MemoryLayer } from '../types';

export interface TimelineData {
  date: string;  // "2025-12-27"
  L0: number;    // identity_schema
  L2: number;    // event_log
  L3: number;    // verified_fact
  L4: number;    // operational_knowledge
  total: number;
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

// Format date to YYYY-MM-DD
const formatDate = (dateStr: string): string => {
  const date = new Date(dateStr);
  return date.toISOString().split('T')[0];
};

// Generate date range between two dates
const generateDateRange = (startDate: Date, endDate: Date): string[] => {
  const dates: string[] = [];
  const current = new Date(startDate);

  while (current <= endDate) {
    dates.push(current.toISOString().split('T')[0]);
    current.setDate(current.getDate() + 1);
  }

  return dates;
};

export function useTimelineData(memories: Memory[]): TimelineData[] {
  return useMemo(() => {
    if (memories.length === 0) {
      return [];
    }

    // Group memories by date
    const dateMap = new Map<string, TimelineData>();

    // Find date range
    let minDate = new Date();
    let maxDate = new Date(0);

    memories.forEach((memory) => {
      const date = new Date(memory.created_at);
      if (date < minDate) minDate = date;
      if (date > maxDate) maxDate = date;
    });

    // Initialize all dates in range
    const allDates = generateDateRange(minDate, maxDate);
    allDates.forEach((date) => {
      dateMap.set(date, {
        date,
        L0: 0,
        L2: 0,
        L3: 0,
        L4: 0,
        total: 0,
      });
    });

    // Count memories by date and layer
    memories.forEach((memory) => {
      const date = formatDate(memory.created_at);
      const layerKey = layerToKey(memory.layer);

      if (!layerKey) return;

      const entry = dateMap.get(date);
      if (entry) {
        entry[layerKey]++;
        entry.total++;
      }
    });

    // Convert to sorted array
    return Array.from(dateMap.values()).sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    );
  }, [memories]);
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
