import { useTranslation } from 'react-i18next';

export type TimeRange = '7d' | '30d' | '90d' | 'all';
export type Granularity = 'day' | 'week' | 'month';

interface TimelineFiltersProps {
  timeRange: TimeRange;
  granularity: Granularity;
  onTimeRangeChange: (range: TimeRange) => void;
  onGranularityChange: (granularity: Granularity) => void;
}

const TIME_RANGE_VALUES: TimeRange[] = ['7d', '30d', '90d', 'all'];
const GRANULARITY_VALUES: Granularity[] = ['day', 'week', 'month'];

export function TimelineFilters({
  timeRange,
  granularity,
  onTimeRangeChange,
  onGranularityChange,
}: TimelineFiltersProps) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-wrap items-center gap-4">
      {/* Time Range Selector */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">{t('timeline.timeRange')}:</span>
        <div className="flex bg-gray-100 rounded-lg p-1">
          {TIME_RANGE_VALUES.map((value) => (
            <button
              key={value}
              onClick={() => onTimeRangeChange(value)}
              className={`
                px-3 py-1.5 text-sm font-medium rounded-md
                transition-all duration-200
                ${timeRange === value
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
                }
              `}
            >
              {t(`timeline.range.${value}`)}
            </button>
          ))}
        </div>
      </div>

      {/* Granularity Selector */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">{t('timeline.granularity')}:</span>
        <div className="flex bg-gray-100 rounded-lg p-1">
          {GRANULARITY_VALUES.map((value) => (
            <button
              key={value}
              onClick={() => onGranularityChange(value)}
              className={`
                px-3 py-1.5 text-sm font-medium rounded-md
                transition-all duration-200
                ${granularity === value
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
                }
              `}
            >
              {t(`timeline.granularityOptions.${value}`)}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
