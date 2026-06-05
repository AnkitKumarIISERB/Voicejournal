import React, { useState, useEffect } from 'react';
import { Sparkles, RefreshCw } from 'lucide-react';
import { apiClient } from '../api/client';

export default function WeeklySummary() {
  const [summary, setSummary] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [typedText, setTypedText] = useState('');
  
  const fetchSummary = async () => {
    setIsLoading(true);
    try {
      const res = await apiClient.get('/journals/weekly-summary');
      setSummary(res.data.summary);
      setTypedText('');
    } catch (err) {
      console.error("Failed to fetch weekly summary", err);
      setSummary("Could not generate summary at this time. Please try again later.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, []);

  // Typewriter effect
  useEffect(() => {
    if (!summary) return;
    
    let currentIndex = 0;
    const intervalId = setInterval(() => {
      if (currentIndex < summary.length) {
        setTypedText(summary.slice(0, currentIndex + 1));
        currentIndex++;
      } else {
        clearInterval(intervalId);
      }
    }, 20); // typing speed
    
    return () => clearInterval(intervalId);
  }, [summary]);

  return (
    <div className="glass-panel p-6 rounded-2xl w-full border border-primary/20 relative overflow-hidden group">
      {/* Decorative background glow */}
      <div className="absolute -top-10 -right-10 w-32 h-32 bg-primary/20 rounded-full blur-3xl pointer-events-none"></div>
      
      <div className="flex items-center justify-between mb-4 relative z-10">
        <div className="flex items-center gap-2 text-primary">
          <Sparkles size={18} />
          <h3 className="text-lg font-medium text-white">AI Weekly Insights</h3>
        </div>
        <button 
          onClick={fetchSummary} 
          disabled={isLoading}
          className="text-textMuted hover:text-white transition-colors p-2 disabled:opacity-50"
          title="Regenerate summary"
        >
          <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
        </button>
      </div>
      
      <div className="relative z-10 min-h-[80px]">
        {isLoading && !summary ? (
          <div className="flex flex-col gap-2 animate-pulse">
            <div className="h-4 bg-white/10 rounded w-full"></div>
            <div className="h-4 bg-white/10 rounded w-5/6"></div>
            <div className="h-4 bg-white/10 rounded w-4/6"></div>
          </div>
        ) : (
          <p className="text-white/80 leading-relaxed text-sm md:text-base">
            {typedText}
            {typedText.length < (summary?.length || 0) && (
              <span className="inline-block w-1.5 h-4 ml-1 bg-primary/70 animate-pulse align-middle"></span>
            )}
          </p>
        )}
      </div>
    </div>
  );
}
