import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { Calendar } from 'lucide-react';

interface EmotionHeatmapProps {
  // Can trigger re-fetch if parent says so
  refreshTrigger?: number;
}

const EMOTION_COLORS: Record<string, string> = {
  neutral: 'bg-gray-500',
  calm: 'bg-teal-500',
  happy: 'bg-amber-500',
  sad: 'bg-blue-500',
  angry: 'bg-red-500',
  fearful: 'bg-purple-500',
  disgust: 'bg-green-500',
  surprised: 'bg-pink-500',
};

const EMOTION_EMOJIS: Record<string, string> = {
  neutral: '😐',
  calm: '😌',
  happy: '😊',
  sad: '😢',
  angry: '😠',
  fearful: '😨',
  disgust: '🤢',
  surprised: '😲',
};

export default function EmotionHeatmap({ refreshTrigger = 0 }: EmotionHeatmapProps) {
  const [trendsMap, setTrendsMap] = useState<Record<string, any>>({});
  const [isLoading, setIsLoading] = useState(true);

  // Get last 90 days
  const days = 90;
  
  useEffect(() => {
    const fetchTrends = async () => {
      try {
        const res = await apiClient.get(`/journals/trends?days=${days}`);
        const map: Record<string, any> = {};
        res.data.trends.forEach((t: any) => {
          map[t.date] = t;
        });
        setTrendsMap(map);
      } catch (err) {
        console.error("Failed to fetch heatmap trends", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchTrends();
  }, [refreshTrigger]);

  // Generate grid cells
  const cells = [];
  const today = new Date();
  
  // We want to render left-to-right, so we start from 90 days ago
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().split('T')[0];
    const data = trendsMap[dateStr];
    
    let colorClass = 'bg-white/5'; // empty
    let tooltip = dateStr;
    
    if (data) {
      colorClass = EMOTION_COLORS[data.emotion] || EMOTION_COLORS.neutral;
      tooltip = `${dateStr} • ${EMOTION_EMOJIS[data.emotion] || ''} ${data.emotion} (Valence: ${data.valence.toFixed(2)})`;
    }

    cells.push(
      <div 
        key={dateStr}
        title={tooltip}
        className={`w-3 h-3 md:w-4 md:h-4 rounded-sm ${colorClass} hover:ring-2 hover:ring-white/50 transition-all cursor-pointer`}
        style={{ animationDelay: `${(days - i) * 0.01}s` }}
      />
    );
  }

  // Group cells into columns of 7 (weeks)
  const columns = [];
  for (let i = 0; i < cells.length; i += 7) {
    columns.push(
      <div key={`col-${i}`} className="flex flex-col gap-1 md:gap-1.5 fade-in-up">
        {cells.slice(i, i + 7)}
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="glass-panel p-6 rounded-2xl w-full border border-white/5 flex items-center justify-center h-32">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="glass-panel p-6 rounded-2xl w-full border border-white/5 overflow-hidden relative group">
      <div className="flex items-center gap-2 mb-4">
        <Calendar size={18} className="text-primary" />
        <h3 className="text-lg font-medium text-white">Emotion History (90 Days)</h3>
      </div>
      
      <div className="flex overflow-x-auto pb-2 scrollbar-hide">
        <div className="flex gap-1 md:gap-1.5 min-w-max">
          {columns}
        </div>
      </div>
      
      <div className="flex items-center gap-4 mt-4 text-xs text-textMuted justify-end">
        <span>Less</span>
        <div className="flex gap-1">
          <div className="w-3 h-3 rounded-sm bg-white/5"></div>
          <div className="w-3 h-3 rounded-sm bg-gray-500"></div>
          <div className="w-3 h-3 rounded-sm bg-blue-500"></div>
          <div className="w-3 h-3 rounded-sm bg-amber-500"></div>
        </div>
        <span>More</span>
      </div>
    </div>
  );
}
