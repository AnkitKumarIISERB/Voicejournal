import React, { useState, useEffect } from 'react';
import { AlertTriangle, Phone, Heart, X } from 'lucide-react';
import { apiClient } from '../api/client';

export default function CrisisAlert() {
  const [alert, setAlert] = useState<any>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const checkAnomaly = async () => {
      try {
        const res = await apiClient.get('/journals/anomaly-check');
        if (res.data.is_anomaly) {
          setAlert(res.data);
        }
      } catch (err) {
        // Silently fail — don't disrupt the user
      }
    };
    checkAnomaly();
  }, []);

  if (!alert || dismissed) return null;

  const isCrisis = alert.alert_level === 'crisis';

  return (
    <div className={`rounded-2xl p-5 border relative overflow-hidden fade-in-up ${
      isCrisis 
        ? 'bg-red-500/10 border-red-500/30' 
        : 'bg-amber-500/10 border-amber-500/30'
    }`}>
      {/* Dismiss button */}
      <button
        onClick={() => setDismissed(true)}
        className="absolute top-3 right-3 text-textMuted hover:text-white transition-colors"
      >
        <X size={16} />
      </button>

      <div className="flex items-start gap-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
          isCrisis ? 'bg-red-500/20' : 'bg-amber-500/20'
        }`}>
          {isCrisis ? (
            <Heart size={20} className="text-red-400" />
          ) : (
            <AlertTriangle size={20} className="text-amber-400" />
          )}
        </div>

        <div className="flex-1">
          <h4 className={`font-medium mb-1 ${isCrisis ? 'text-red-300' : 'text-amber-300'}`}>
            {isCrisis ? 'We\'re Here For You' : 'Mood Check-In'}
          </h4>
          <p className="text-sm text-white/70 mb-3">{alert.message}</p>

          {/* Recommendations */}
          {alert.recommendations && alert.recommendations.length > 0 && (
            <ul className="space-y-1.5 mb-3">
              {alert.recommendations.map((rec: string, i: number) => (
                <li key={i} className="text-xs text-white/60 flex items-start gap-2">
                  <span className="text-primary mt-0.5">•</span>
                  {rec}
                </li>
              ))}
            </ul>
          )}

          {/* Helplines */}
          {alert.helplines && (
            <div className="space-y-2 mt-3 pt-3 border-t border-white/10">
              <p className="text-xs font-medium text-white/50 uppercase tracking-wider">Helplines</p>
              {Object.values(alert.helplines).map((helpline: any, i: number) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <Phone size={12} className="text-green-400 shrink-0" />
                  <span className="text-white font-medium">{helpline.name}:</span>
                  <span className="text-green-400 font-mono">{helpline.number}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
