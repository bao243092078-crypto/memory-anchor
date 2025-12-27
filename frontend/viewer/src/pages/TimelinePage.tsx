import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMemories } from '../hooks/useMemories';
import { useTimelineData } from '../hooks/useTimelineData';
import { TimelineChart } from '../components/timeline/TimelineChart';
import { TimelineFilters, type TimeRange, type Granularity } from '../components/timeline/TimelineFilters';

export function TimelinePage() {
  const { t } = useTranslation();
  const [timeRange, setTimeRange] = useState<TimeRange>('all');
  const [granularity, setGranularity] = useState<Granularity>('day');

  const { memories, loading, error } = useMemories({ limit: 1000 });
  const timelineData = useTimelineData(memories, { timeRange, granularity });

  return (
    <div className="space-y-6">
      {/* Stats summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-100 p-4">
          <p className="text-sm text-gray-500">{t('timeline.totalMemories')}</p>
          <p className="text-2xl font-semibold text-gray-900">
            {loading ? '...' : memories.length}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-4">
          <p className="text-sm text-gray-500">{t('timeline.timeSpan')}</p>
          <p className="text-2xl font-semibold text-gray-900">
            {loading ? '...' : `${timelineData.length} ${t(`time.${granularity}`)}`}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-4">
          <p className="text-sm text-gray-500">
            {t(`timeline.avgPer${granularity.charAt(0).toUpperCase() + granularity.slice(1)}`)}
          </p>
          <p className="text-2xl font-semibold text-gray-900">
            {loading || timelineData.length === 0
              ? '...'
              : (timelineData.reduce((sum, d) => sum + d.total, 0) / timelineData.length).toFixed(1)}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-4">
          <p className="text-sm text-gray-500">
            {t(`timeline.mostActive${granularity.charAt(0).toUpperCase() + granularity.slice(1)}`)}
          </p>
          <p className="text-2xl font-semibold text-gray-900">
            {loading || timelineData.length === 0
              ? '...'
              : (() => {
                  const maxDay = timelineData.reduce((max, day) =>
                    day.total > max.total ? day : max
                  );
                  return maxDay.total;
                })()}
          </p>
        </div>
      </div>

      {/* Chart section */}
      <div className="bg-white rounded-xl border border-gray-100 p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <h2 className="text-lg font-semibold text-gray-900">{t('timeline.title')}</h2>
          <TimelineFilters
            timeRange={timeRange}
            granularity={granularity}
            onTimeRangeChange={setTimeRange}
            onGranularityChange={setGranularity}
          />
        </div>

        {loading ? (
          <div className="h-[400px] flex items-center justify-center">
            <div className="flex items-center gap-2 text-gray-500">
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              {t('common.loading')}
            </div>
          </div>
        ) : error ? (
          <div className="h-[400px] flex items-center justify-center">
            <div className="text-red-500">{t('memory.loadError')}: {error}</div>
          </div>
        ) : (
          <TimelineChart data={timelineData} />
        )}
      </div>

      {/* Layer distribution */}
      <div className="bg-white rounded-xl border border-gray-100 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">{t('timeline.layerDistribution')}</h2>
        <div className="grid grid-cols-4 gap-4">
          {(['L0', 'L2', 'L3', 'L4'] as const).map((layer) => {
            const total = timelineData.reduce((sum, day) => sum + day[layer], 0);
            const colors = {
              L0: 'bg-red-500',
              L2: 'bg-yellow-500',
              L3: 'bg-green-500',
              L4: 'bg-blue-500',
            };
            const labelKeys = {
              L0: 'layer.identity_schema',
              L2: 'layer.event_log',
              L3: 'layer.verified_fact',
              L4: 'layer.operational_knowledge',
            };
            const percentage =
              memories.length > 0 ? ((total / memories.length) * 100).toFixed(1) : '0';

            return (
              <div key={layer} className="text-center">
                <div
                  className={`w-12 h-12 rounded-full ${colors[layer]} mx-auto mb-2 flex items-center justify-center text-white font-semibold`}
                >
                  {layer}
                </div>
                <p className="text-sm text-gray-500">{t(labelKeys[layer])}</p>
                <p className="text-xl font-semibold text-gray-900">{total}</p>
                <p className="text-xs text-gray-400">{percentage}%</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
