import React, { useState, useEffect } from 'react';
import { LineChart, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { apiClient } from '../api/client';

export default function MoodPrediction() {
  const [prediction, setPrediction] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchPrediction = async () => {
      try {
        const res = await apiClient.get('/journals/prediction');
        setPrediction(res.data);
      } catch (err) {
        console.error("Failed to fetch prediction", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchPrediction();
  }, []);

  if (isLoading) {
    return (
      <div className="stat-card animate-pulse">
        <div className="h-4 bg-white/10 rounded w-1/2 mb-3"></div>
        <div className="h-8 bg-white/10 rounded w-3/4"></div>
      </div>
    );
  }

  if (!prediction || prediction.trend === 'insufficient_data') {
    return (
      <div className="stat-card">
        <div className="flex items-center gap-2 mb-2 text-textMuted text-xs font-medium uppercase tracking-wider">
          <LineChart size={16} />
          Tomorrow's Outlook
        </div>
        <div className="text-sm text-textMuted">
          Need a few more entries to predict your mood trend. Keep journaling!
        </div>
      </div>
    );
  }

  const getTrendDisplay = () => {
    switch (prediction.trend) {
      case 'improving':
        return { icon: <TrendingUp size={24} className="text-green-400" />, text: 'Improving', color: 'text-green-400' };
      case 'declining':
        return { icon: <TrendingDown size={24} className="text-red-400" />, text: 'Declining', color: 'text-red-400' };
      default:
        return { icon: <Minus size={24} className="text-amber-400" />, text: 'Stable', color: 'text-amber-400' };
    }
  };

  const getMoodEmoji = (v: number) => {
    if (v > 0.5) return '🌟';
    if (v > 0.2) return '☀️';
    if (v > -0.2) return '⛅';
    if (v > -0.5) return '🌧️';
    return '⛈️';
  };

  const display = getTrendDisplay();

  return (
    <div className="stat-card relative overflow-hidden group">
      <div className="absolute -right-4 -bottom-4 opacity-5 group-hover:opacity-10 transition-opacity">
        {display.icon}
      </div>
      
      <div className="flex items-center gap-2 mb-3 text-textMuted text-xs font-medium uppercase tracking-wider">
        <LineChart size={16} className="text-primary" />
        Tomorrow's Outlook
      </div>
      
      <div className="flex items-end gap-3 mb-1">
        <div className="text-3xl">
          {getMoodEmoji(prediction.predicted_valence)}
        </div>
        <div className={`text-xl font-medium ${display.color}`}>
          {display.text}
        </div>
      </div>
      
      <div className="text-xs text-textMuted mt-2 flex items-center justify-between">
        <span>Predicted Valence: {prediction.predicted_valence > 0 ? '+' : ''}{prediction.predicted_valence}</span>
      </div>
    </div>
  );
}
