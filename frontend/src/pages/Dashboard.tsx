import React, { useEffect, useState, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { apiClient } from '../api/client';
import { LogOut, Activity, Clock, Trash2, TrendingUp, Zap, Heart, Download } from 'lucide-react';
import AudioRecorder from '../components/AudioRecorder';
import MoodChart from '../components/MoodChart';
import AudioPlayer from '../components/AudioPlayer';
import EmotionHeatmap from '../components/EmotionHeatmap';
import WeeklySummary from '../components/WeeklySummary';
import MoodPrediction from '../components/MoodPrediction';
import MoodGlobe from '../components/MoodGlobe';
import JournalChat from '../components/JournalChat';
import CrisisAlert from '../components/CrisisAlert';
import StreakBadge from '../components/StreakBadge';
import VoiceBiomarkers from '../components/VoiceBiomarkers';

interface JournalEntry {
  id: number;
  transcript: string | null;
  valence_score: number | null;
  emotion_label: string | null;
  created_at: string;
}

// Emotion → color/emoji mapping
const EMOTION_STYLES: Record<string, { emoji: string; gradient: string; badge: string; glow: string }> = {
  neutral:   { emoji: '😐', gradient: 'from-gray-500/20 to-gray-600/10',   badge: 'bg-gray-500/20 text-gray-300 border-gray-500/30',     glow: 'shadow-gray-500/10' },
  calm:      { emoji: '😌', gradient: 'from-teal-500/20 to-cyan-600/10',    badge: 'bg-teal-500/20 text-teal-300 border-teal-500/30',      glow: 'shadow-teal-500/10' },
  happy:     { emoji: '😊', gradient: 'from-amber-500/20 to-yellow-600/10', badge: 'bg-amber-500/20 text-amber-300 border-amber-500/30',   glow: 'shadow-amber-500/10' },
  sad:       { emoji: '😢', gradient: 'from-blue-500/20 to-indigo-600/10',  badge: 'bg-blue-500/20 text-blue-300 border-blue-500/30',      glow: 'shadow-blue-500/10' },
  angry:     { emoji: '😠', gradient: 'from-red-500/20 to-orange-600/10',   badge: 'bg-red-500/20 text-red-300 border-red-500/30',         glow: 'shadow-red-500/10' },
  fearful:   { emoji: '😨', gradient: 'from-purple-500/20 to-violet-600/10',badge: 'bg-purple-500/20 text-purple-300 border-purple-500/30', glow: 'shadow-purple-500/10' },
  disgust:   { emoji: '🤢', gradient: 'from-green-500/20 to-emerald-600/10',badge: 'bg-green-500/20 text-green-300 border-green-500/30',   glow: 'shadow-green-500/10' },
  surprised: { emoji: '😲', gradient: 'from-pink-500/20 to-rose-600/10',    badge: 'bg-pink-500/20 text-pink-300 border-pink-500/30',      glow: 'shadow-pink-500/10' },
};

function getEmotionStyle(emotion: string | null) {
  return EMOTION_STYLES[emotion || 'neutral'] || EMOTION_STYLES.neutral;
}

function getValenceColor(v: number | null) {
  if (v === null) return 'text-textMuted';
  if (v > 0.3) return 'text-green-400';
  if (v > -0.3) return 'text-amber-400';
  return 'text-red-400';
}

function getMoodEmoji(v: number) {
  if (v > 0.5) return '🌟';
  if (v > 0.2) return '☀️';
  if (v > -0.2) return '⛅';
  if (v > -0.5) return '🌧️';
  return '⛈️';
}

export default function Dashboard() {
  const { user, logout } = useAuth();
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [trends, setTrends] = useState<any[]>([]);
  const [averageValence, setAverageValence] = useState<number>(0);
  const [commonEmotion, setCommonEmotion] = useState<string>('neutral');
  const [isLoading, setIsLoading] = useState(true);
  const [expandedAudioId, setExpandedAudioId] = useState<number | null>(null);
  const [refreshCount, setRefreshCount] = useState<number>(0);
  
  const wsRef = useRef<WebSocket | null>(null);

  const fetchData = async () => {
    try {
      const [entriesRes, trendsRes] = await Promise.all([
        apiClient.get('/journals/'),
        apiClient.get('/journals/trends?days=30')
      ]);
      
      setEntries(entriesRes.data.entries);
      setTrends(trendsRes.data.trends);
      setAverageValence(trendsRes.data.average_valence);
      setCommonEmotion(trendsRes.data.most_common_emotion);
      setRefreshCount(prev => prev + 1);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();

    // Setup WebSocket for real-time updates when tasks finish
    const token = localStorage.getItem('access_token');
    if (token) {
      // Create WebSocket connection
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const baseUrl = apiUrl.replace(/\/api\/v1\/?$/, '');
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsHost = baseUrl.replace(/^https?:/, wsProtocol);
      const wsUrl = import.meta.env.VITE_WS_URL || `${wsHost}/ws`;
      
      const ws = new WebSocket(`${wsUrl}/${token}`);
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.status === 'completed' || data.status === 'error') {
            // Task finished, refresh data
            fetchData();
          }
        } catch (e) {
          console.error('Error parsing WS message', e);
        }
      };

      wsRef.current = ws;

      return () => {
        ws.close();
      };
    }
  }, []);

  // Poll for updates if any entry is processing
  useEffect(() => {
    const hasProcessing = entries.some(e => !e.emotion_label);
    if (hasProcessing) {
      const interval = setInterval(() => {
        fetchData();
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [entries]);

  // Keyboard Shortcuts (6.5)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Shift + E to export data
      if (e.shiftKey && e.key.toLowerCase() === 'e') {
        e.preventDefault();
        handleExportData();
      }
      // Esc to clear selected audio
      if (e.key === 'Escape') {
        setExpandedAudioId(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleExportData = async () => {
    try {
      const res = await apiClient.get('/auth/export');
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(res.data, null, 2));
      const a = document.createElement('a');
      a.href = dataStr;
      a.download = "voicejournal_export.json";
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      console.error("Failed to export data", err);
      alert("Failed to export data. Please try again.");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this entry?')) return;
    
    try {
      await apiClient.delete(`/journals/${id}`);
      fetchData();
    } catch (error) {
      console.error('Error deleting entry:', error);
      alert('Failed to delete entry');
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Activity className="animate-spin text-primary" size={32} />
          <p className="text-textMuted text-sm">Loading your journal...</p>
        </div>
      </div>
    );
  }

  const emotionStyle = getEmotionStyle(commonEmotion);

  return (
    <div className="min-h-screen bg-background text-textMain pb-12 relative overflow-hidden noise-overlay">
      {/* Animated background orbs */}
      <div className="orb orb-1" style={{ top: '-10%', right: '-5%' }}></div>
      <div className="orb orb-2" style={{ bottom: '20%', left: '-10%' }}></div>

      {/* Navbar */}
      <nav className="border-b border-white/[0.05] bg-background/60 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-gradient-to-br from-primary to-secondary rounded-xl flex items-center justify-center shadow-lg shadow-primary/20">
              <Activity size={18} className="text-white" />
            </div>
            <span className="font-bold text-lg tracking-tight">VoiceJournal</span>
          </div>
          
          <div className="flex items-center gap-4">
            <StreakBadge />
            <span className="text-sm text-textMuted hidden sm:block">{user?.email}</span>
            <button 
              onClick={handleExportData}
              className="p-2.5 hover:bg-white/5 rounded-xl transition-all duration-300 text-textMuted hover:text-white"
              title="Export Data (Shift+E)"
            >
              <Download size={18} />
            </button>
            <button 
              onClick={logout}
              className="p-2.5 hover:bg-white/5 rounded-xl transition-all duration-300 text-textMuted hover:text-white"
              title="Logout"
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8 relative z-10">
        
        <div className="mb-2">
          <CrisisAlert />
        </div>

        {/* Greeting */}
        <div className="fade-in-up">
          <h1 className="text-3xl font-bold text-white">
            Good {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'} {getMoodEmoji(averageValence)}
          </h1>
          <p className="text-textMuted mt-1">Here's your emotional wellness overview</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 fade-in-up fade-in-up-delay-1">
          <div className="lg:col-span-2 space-y-6">
            <AudioRecorder onUploadSuccess={() => {
              setTimeout(fetchData, 1000); 
            }} />
            <EmotionHeatmap refreshTrigger={refreshCount} />
          </div>
          
          {/* Stats column */}
          <div className="space-y-4">
            <div className="stat-card">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                  <TrendingUp size={16} className="text-primary" />
                </div>
                <span className="text-xs font-medium text-textMuted uppercase tracking-wider">30-Day Mood</span>
              </div>
              <div className={`text-4xl font-light mb-1 ${getValenceColor(averageValence)}`}>
                {averageValence > 0 ? '+' : ''}{averageValence.toFixed(2)}
              </div>
              <div className="text-xs text-textMuted">Average Valence Score</div>
            </div>

            <div className="stat-card">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-8 h-8 rounded-lg bg-secondary/10 flex items-center justify-center">
                  <Heart size={16} className="text-secondary" />
                </div>
                <span className="text-xs font-medium text-textMuted uppercase tracking-wider">Dominant</span>
              </div>
              <div className="text-3xl mb-1">{emotionStyle.emoji}</div>
              <div className="text-lg font-medium text-white capitalize">{commonEmotion}</div>
            </div>

            <div className="stat-card">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
                  <Zap size={16} className="text-accent" />
                </div>
                <span className="text-xs font-medium text-textMuted uppercase tracking-wider">Entries</span>
              </div>
              <div className="text-4xl font-light text-white">{entries.length}</div>
              <div className="text-xs text-textMuted">Total journal entries</div>
            </div>

            <MoodPrediction />

            <div className="fade-in-up mt-6">
              <MoodGlobe emotion={commonEmotion} />
            </div>

            <div className="fade-in-up mt-6">
              <WeeklySummary />
            </div>
          </div>
        </div>

        {/* Chart Section */}
        <div className="fade-in-up fade-in-up-delay-2">
          <MoodChart data={trends} />
        </div>

        {/* History Section */}
        <div className="fade-in-up fade-in-up-delay-3">
          <h3 className="text-xl font-semibold text-white mb-6 flex items-center gap-2">
            <Clock size={20} className="text-primary" />
            Recent Entries
          </h3>
          
          {entries.length === 0 ? (
            <div className="glass-panel p-12 rounded-3xl text-center border border-white/[0.05]">
              <div className="text-5xl mb-4">🎙️</div>
              <p className="text-white font-medium mb-2">Your journal is empty</p>
              <p className="text-textMuted text-sm">Record your first voice entry above to get started</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {entries.map((entry, index) => {
                const style = getEmotionStyle(entry.emotion_label);
                return (
                  <div
                    key={entry.id}
                    className={`emotion-card glass-panel p-5 rounded-2xl border border-white/[0.06] group ${style.glow} shadow-lg`}
                    style={{ animationDelay: `${index * 0.05}s` }}
                  >
                    {/* Emotion gradient overlay */}
                    <div className={`absolute inset-0 bg-gradient-to-br ${style.gradient} rounded-2xl opacity-50`}></div>
                    
                    <div className="relative z-10">
                      <div className="flex justify-between items-start mb-3">
                        <div>
                          <div className="text-xs text-textMuted mb-2">
                            {new Date(entry.created_at + (entry.created_at.endsWith('Z') ? '' : 'Z')).toLocaleString('en-IN', {
                              weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata'
                            })}
                          </div>
                          <div className="flex items-center gap-2">
                            {entry.emotion_label ? (
                              <>
                                <span className="text-xl">{style.emoji}</span>
                                <span className={`px-2.5 py-1 rounded-lg text-xs font-medium capitalize border ${style.badge}`}>
                                  {entry.emotion_label}
                                </span>
                              </>
                            ) : (
                              <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-white/5 text-textMuted border border-white/10 animate-pulse">
                                Processing...
                              </span>
                            )}
                            {entry.valence_score !== null && (
                              <span className={`text-xs font-mono ${getValenceColor(entry.valence_score)}`}>
                                {entry.valence_score > 0 ? '+' : ''}{entry.valence_score.toFixed(2)}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all duration-300">
                          <button 
                            onClick={() => setExpandedAudioId(expandedAudioId === entry.id ? null : entry.id)}
                            className={`p-2 rounded-xl transition-all duration-300 ${expandedAudioId === entry.id ? 'bg-primary/20 text-primary' : 'hover:bg-primary/10 text-textMuted hover:text-primary'}`}
                            title="Play audio"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                          </button>
                          <button 
                            onClick={() => handleDelete(entry.id)}
                            className="p-2 hover:bg-red-500/20 rounded-xl transition-all duration-300 text-textMuted hover:text-red-400"
                            title="Delete entry"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>
                      
                      <p className={`text-sm text-white/70 leading-relaxed ${expandedAudioId === entry.id ? '' : 'line-clamp-3'}`}>
                        {entry.transcript ? (
                          <span className="italic">"{entry.transcript}"</span>
                        ) : (
                          <span className="text-textMuted/50 flex items-center gap-2">
                            <Activity size={14} className="animate-spin" />
                            Transcribing audio...
                          </span>
                        )}
                      </p>
                      
                      {/* Audio Player Expansion */}
                      {expandedAudioId === entry.id && (
                        <div className="mt-4 pt-4 border-t border-white/10">
                          <AudioPlayer audioUrl={`http://localhost:8000/api/v1/journals/${entry.id}/audio`} />
                          <VoiceBiomarkers entryId={entry.id} />
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>

      {/* Floating Chat Widget */}
      <JournalChat />
    </div>
  );
}
