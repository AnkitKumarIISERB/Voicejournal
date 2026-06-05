import React, { useState, useEffect } from 'react';
import { Flame } from 'lucide-react';
import { apiClient } from '../api/client';

export default function StreakBadge() {
  const [streakData, setStreakData] = useState<{ current_streak: number; longest_streak: number; total_entries: number } | null>(null);

  useEffect(() => {
    const fetchStreak = async () => {
      try {
        const res = await apiClient.get('/journals/streak');
        setStreakData(res.data);
      } catch (err) {
        // fail silently
      }
    };
    fetchStreak();
  }, []);

  if (!streakData) return null;

  return (
    <div className="flex items-center gap-3 bg-white/5 border border-white/10 rounded-full px-4 py-1.5 backdrop-blur-sm relative overflow-hidden group">
      <div className={`absolute inset-0 bg-gradient-to-r from-orange-500/20 to-red-500/20 opacity-0 group-hover:opacity-100 transition-opacity ${streakData.current_streak > 0 ? 'opacity-50' : ''}`}></div>
      
      <div className="flex items-center gap-1.5 relative z-10">
        <Flame size={16} className={streakData.current_streak > 0 ? "text-orange-400" : "text-textMuted"} />
        <span className="text-sm font-bold text-white">
          {streakData.current_streak} {streakData.current_streak === 1 ? 'Day' : 'Days'}
        </span>
      </div>
      
      <div className="w-px h-4 bg-white/20 relative z-10"></div>
      
      <div className="text-xs text-textMuted relative z-10 hidden sm:block">
        Best: {streakData.longest_streak}
      </div>
    </div>
  );
}
