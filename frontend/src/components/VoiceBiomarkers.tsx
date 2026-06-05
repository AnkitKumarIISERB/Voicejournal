import React, { useState, useEffect } from 'react';
import { Activity, Wind, Volume2, Clock, AlertCircle } from 'lucide-react';
import { apiClient } from '../api/client';

interface BiomarkersProps {
  entryId: number;
}

export default function VoiceBiomarkers({ entryId }: BiomarkersProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchBiomarkers = async () => {
      try {
        const res = await apiClient.get(`/journals/biomarkers/${entryId}`);
        setData(res.data);
      } catch (err) {
        // fail silently
      } finally {
        setLoading(false);
      }
    };
    fetchBiomarkers();
  }, [entryId]);

  if (loading) {
    return (
      <div className="mt-4 pt-4 border-t border-white/10 animate-pulse">
        <div className="h-4 bg-white/10 w-1/3 rounded mb-4"></div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[1,2,3,4].map(i => <div key={i} className="h-16 bg-white/5 rounded-xl"></div>)}
        </div>
      </div>
    );
  }

  if (!data || data.error) return null;

  return (
    <div className="mt-4 pt-4 border-t border-white/10">
      <div className="flex items-center gap-2 mb-3">
        <Activity size={16} className="text-secondary" />
        <h4 className="text-sm font-medium text-white/90">Clinical Voice Biomarkers</h4>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div className="bg-white/5 border border-white/10 rounded-xl p-3">
          <div className="flex items-center gap-1.5 text-textMuted mb-1 text-xs uppercase tracking-wider">
            <Volume2 size={12} /> Pitch (F0)
          </div>
          <div className="text-lg font-medium text-white">{data.pitch.mean_hz} <span className="text-xs text-textMuted">Hz</span></div>
          <div className="text-[10px] text-white/50 mt-1 leading-tight">{data.pitch.interpretation}</div>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-3">
          <div className="flex items-center gap-1.5 text-textMuted mb-1 text-xs uppercase tracking-wider">
            <Activity size={12} /> Energy (RMS)
          </div>
          <div className="text-lg font-medium text-white">{data.energy.mean.toFixed(4)}</div>
          <div className="text-[10px] text-white/50 mt-1 leading-tight">{data.energy.interpretation}</div>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-3">
          <div className="flex items-center gap-1.5 text-textMuted mb-1 text-xs uppercase tracking-wider">
            <Wind size={12} /> Speech Rate
          </div>
          <div className="text-lg font-medium text-white">{data.speaking_rate.wpm} <span className="text-xs text-textMuted">WPM</span></div>
          <div className="text-[10px] text-white/50 mt-1 leading-tight">{data.speaking_rate.interpretation}</div>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-3">
          <div className="flex items-center gap-1.5 text-textMuted mb-1 text-xs uppercase tracking-wider">
            <Clock size={12} /> Pauses
          </div>
          <div className="text-lg font-medium text-white">{(data.pauses.silence_ratio * 100).toFixed(1)}% <span className="text-xs text-textMuted">silence</span></div>
          <div className="text-[10px] text-white/50 mt-1 leading-tight">{data.pauses.interpretation}</div>
        </div>
      </div>

      <div className="bg-secondary/10 border border-secondary/20 rounded-xl p-3 flex gap-3 items-start">
        <AlertCircle size={16} className="text-secondary shrink-0 mt-0.5" />
        <div>
          <h5 className="text-xs font-medium text-white/80 mb-0.5">Overall Assessment</h5>
          <p className="text-xs text-white/60 leading-relaxed">{data.overall_assessment}</p>
        </div>
      </div>
    </div>
  );
}
