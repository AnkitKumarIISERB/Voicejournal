import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';

interface MoodData {
  date: string;
  valence: number;
  emotion: string;
}

interface MoodChartProps {
  data: MoodData[];
}

export default function MoodChart({ data }: MoodChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="glass-panel p-8 rounded-2xl flex flex-col items-center justify-center h-64 border border-white/5">
        <p className="text-textMuted">Not enough data to display your mood arc.</p>
        <p className="text-sm text-textMuted mt-2">Record your first journal entry!</p>
      </div>
    );
  }

  // Format dates for the X axis
  const formattedData = data.map(item => ({
    ...item,
    formattedDate: new Date(item.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  }));

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const p = payload[0].payload;
      return (
        <div className="bg-surface border border-white/10 p-3 rounded-lg shadow-xl">
          <p className="text-white font-medium mb-1">{p.formattedDate}</p>
          <p className="text-primary text-sm">Valence: {p.valence.toFixed(2)}</p>
          <p className="text-textMuted text-xs mt-1 capitalize">Emotion: {p.emotion}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="glass-panel p-6 rounded-2xl w-full border border-white/5">
      <h3 className="text-lg font-medium text-white mb-6">Your Mood Arc (30 Days)</h3>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={formattedData}
            margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
          >
            <defs>
              <linearGradient id="colorValence" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.5} />
                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis 
              dataKey="formattedDate" 
              stroke="#94a3b8" 
              fontSize={12}
              tickLine={false}
              axisLine={false}
              dy={10}
            />
            <YAxis 
              stroke="#94a3b8" 
              fontSize={12}
              tickLine={false}
              axisLine={false}
              domain={[-1, 1]}
              tickFormatter={(value) => {
                if (value === 1) return 'Positive';
                if (value === 0) return 'Neutral';
                if (value === -1) return 'Negative';
                return '';
              }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area 
              type="monotone" 
              dataKey="valence" 
              stroke="#8b5cf6" 
              strokeWidth={3}
              fillOpacity={1} 
              fill="url(#colorValence)" 
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
