import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { TimelineData, TIMELINE_COLORS, TIMELINE_LABELS } from '../../hooks/useTimelineData';

interface TimelineChartProps {
  data: TimelineData[];
}

// Custom tooltip component
const CustomTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) => {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const total = payload.reduce((sum, item) => sum + item.value, 0);

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3">
      <p className="text-sm font-medium text-gray-900 mb-2">{label}</p>
      <div className="space-y-1">
        {payload.map((item) => (
          <div key={item.name} className="flex items-center justify-between gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-gray-600">
                {TIMELINE_LABELS[item.name as keyof typeof TIMELINE_LABELS]}
              </span>
            </div>
            <span className="font-medium text-gray-900">{item.value}</span>
          </div>
        ))}
      </div>
      <div className="mt-2 pt-2 border-t border-gray-100 flex justify-between text-sm">
        <span className="text-gray-600">总计</span>
        <span className="font-semibold text-gray-900">{total}</span>
      </div>
    </div>
  );
};

// Format date for X axis
const formatXAxis = (dateStr: string): string => {
  const date = new Date(dateStr);
  return `${date.getMonth() + 1}/${date.getDate()}`;
};

// Custom legend component
const CustomLegend = () => (
  <div className="flex justify-center gap-6 mt-4">
    {Object.entries(TIMELINE_LABELS).map(([key, label]) => (
      <div key={key} className="flex items-center gap-2">
        <div
          className="w-3 h-3 rounded-full"
          style={{ backgroundColor: TIMELINE_COLORS[key as keyof typeof TIMELINE_COLORS] }}
        />
        <span className="text-sm text-gray-600">{label}</span>
      </div>
    ))}
  </div>
);

export function TimelineChart({ data }: TimelineChartProps) {
  if (data.length === 0) {
    return (
      <div className="h-[400px] flex items-center justify-center text-gray-500">
        暂无数据
      </div>
    );
  }

  return (
    <div className="w-full">
      <ResponsiveContainer width="100%" height={400}>
        <AreaChart
          data={data}
          margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id="colorL0" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={TIMELINE_COLORS.L0} stopOpacity={0.8} />
              <stop offset="95%" stopColor={TIMELINE_COLORS.L0} stopOpacity={0.1} />
            </linearGradient>
            <linearGradient id="colorL2" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={TIMELINE_COLORS.L2} stopOpacity={0.8} />
              <stop offset="95%" stopColor={TIMELINE_COLORS.L2} stopOpacity={0.1} />
            </linearGradient>
            <linearGradient id="colorL3" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={TIMELINE_COLORS.L3} stopOpacity={0.8} />
              <stop offset="95%" stopColor={TIMELINE_COLORS.L3} stopOpacity={0.1} />
            </linearGradient>
            <linearGradient id="colorL4" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={TIMELINE_COLORS.L4} stopOpacity={0.8} />
              <stop offset="95%" stopColor={TIMELINE_COLORS.L4} stopOpacity={0.1} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis
            dataKey="date"
            tickFormatter={formatXAxis}
            stroke="#9CA3AF"
            fontSize={12}
          />
          <YAxis stroke="#9CA3AF" fontSize={12} />
          <Tooltip content={<CustomTooltip />} />
          <Legend content={<CustomLegend />} />
          <Area
            type="monotone"
            dataKey="L0"
            stackId="1"
            stroke={TIMELINE_COLORS.L0}
            fill="url(#colorL0)"
          />
          <Area
            type="monotone"
            dataKey="L2"
            stackId="1"
            stroke={TIMELINE_COLORS.L2}
            fill="url(#colorL2)"
          />
          <Area
            type="monotone"
            dataKey="L3"
            stackId="1"
            stroke={TIMELINE_COLORS.L3}
            fill="url(#colorL3)"
          />
          <Area
            type="monotone"
            dataKey="L4"
            stackId="1"
            stroke={TIMELINE_COLORS.L4}
            fill="url(#colorL4)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
