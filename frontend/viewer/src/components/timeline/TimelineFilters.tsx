export type TimeRange = '7d' | '30d' | '90d' | 'all';
export type Granularity = 'day' | 'week' | 'month';

interface TimelineFiltersProps {
  timeRange: TimeRange;
  granularity: Granularity;
  onTimeRangeChange: (range: TimeRange) => void;
  onGranularityChange: (granularity: Granularity) => void;
}

const TIME_RANGE_OPTIONS: { value: TimeRange; label: string }[] = [
  { value: '7d', label: '最近 7 天' },
  { value: '30d', label: '最近 30 天' },
  { value: '90d', label: '最近 90 天' },
  { value: 'all', label: '全部时间' },
];

const GRANULARITY_OPTIONS: { value: Granularity; label: string }[] = [
  { value: 'day', label: '按天' },
  { value: 'week', label: '按周' },
  { value: 'month', label: '按月' },
];

export function TimelineFilters({
  timeRange,
  granularity,
  onTimeRangeChange,
  onGranularityChange,
}: TimelineFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-4">
      {/* Time Range Selector */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">时间范围:</span>
        <div className="flex bg-gray-100 rounded-lg p-1">
          {TIME_RANGE_OPTIONS.map((option) => (
            <button
              key={option.value}
              onClick={() => onTimeRangeChange(option.value)}
              className={`
                px-3 py-1.5 text-sm font-medium rounded-md
                transition-all duration-200
                ${timeRange === option.value
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
                }
              `}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* Granularity Selector */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">粒度:</span>
        <div className="flex bg-gray-100 rounded-lg p-1">
          {GRANULARITY_OPTIONS.map((option) => (
            <button
              key={option.value}
              onClick={() => onGranularityChange(option.value)}
              className={`
                px-3 py-1.5 text-sm font-medium rounded-md
                transition-all duration-200
                ${granularity === option.value
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
                }
              `}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
