import React, { useState, useRef, useEffect } from 'react';
import { Play, Pause, Volume2, VolumeX } from 'lucide-react';
import { apiClient } from '../api/client';

interface AudioPlayerProps {
  entryId: number;
}

export default function AudioPlayer({ entryId }: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const progressRef = useRef<HTMLDivElement | null>(null);

  // Fetch the audio stream URL when component mounts
  useEffect(() => {
    const fetchAudioUrl = async () => {
      try {
        // We use blob URL to securely stream the decrypted audio
        const response = await apiClient.get(`/journals/${entryId}/audio`, {
          responseType: 'blob'
        });
        const url = URL.createObjectURL(response.data);
        setAudioUrl(url);
      } catch (err) {
        console.error('Failed to load audio', err);
        setError('Audio not available');
      }
    };
    fetchAudioUrl();

    // Cleanup blob URL on unmount
    return () => {
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entryId]);

  // Handle play/pause
  const togglePlay = () => {
    if (!audioRef.current) return;
    
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  // Handle audio time update
  const handleTimeUpdate = () => {
    if (!audioRef.current) return;
    const current = audioRef.current.currentTime;
    const total = audioRef.current.duration;
    setProgress((current / total) * 100);
  };

  // Handle audio load metadata (to get duration)
  const handleLoadedMetadata = () => {
    if (!audioRef.current) return;
    setDuration(audioRef.current.duration);
  };

  // Handle clicking on progress bar to seek
  const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!audioRef.current || !progressRef.current) return;
    const rect = progressRef.current.getBoundingClientRect();
    const pos = (e.clientX - rect.left) / rect.width;
    audioRef.current.currentTime = pos * audioRef.current.duration;
  };

  // Format time (seconds to mm:ss)
  const formatTime = (timeInSeconds: number) => {
    if (isNaN(timeInSeconds)) return "00:00";
    const m = Math.floor(timeInSeconds / 60);
    const s = Math.floor(timeInSeconds % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  // Handle mute toggle
  const toggleMute = () => {
    if (!audioRef.current) return;
    audioRef.current.muted = !isMuted;
    setIsMuted(!isMuted);
  };

  if (error) {
    return <div className="text-xs text-red-400 mt-2">{error}</div>;
  }

  if (!audioUrl) {
    return (
      <div className="flex items-center gap-2 mt-3 text-xs text-textMuted animate-pulse">
        <div className="w-4 h-4 rounded-full border-2 border-primary/50 border-t-transparent animate-spin"></div>
        Loading audio...
      </div>
    );
  }

  return (
    <div className="mt-3 bg-white/5 border border-white/10 rounded-xl p-3 flex flex-col gap-2 transition-all">
      <audio 
        ref={audioRef} 
        src={audioUrl} 
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={() => setIsPlaying(false)}
        className="hidden"
      />
      
      <div className="flex items-center gap-3">
        {/* Play/Pause Button */}
        <button 
          onClick={togglePlay}
          className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary hover:bg-primary/30 transition-colors shrink-0"
        >
          {isPlaying ? <Pause size={14} className="fill-current" /> : <Play size={14} className="fill-current ml-0.5" />}
        </button>
        
        {/* Progress Bar Container */}
        <div 
          ref={progressRef}
          onClick={handleProgressClick}
          className="flex-1 h-1.5 bg-white/10 rounded-full cursor-pointer relative group overflow-hidden"
        >
          {/* Active Progress */}
          <div 
            className="absolute top-0 left-0 h-full bg-gradient-to-r from-primary to-secondary rounded-full transition-all duration-100 ease-linear group-hover:from-primary/80 group-hover:to-secondary/80"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Time display */}
        <div className="text-xs text-textMuted font-mono shrink-0 min-w-[36px] text-right">
          {audioRef.current ? formatTime(audioRef.current.currentTime) : "00:00"}
        </div>
        
        {/* Mute toggle */}
        <button 
          onClick={toggleMute}
          className="text-textMuted hover:text-white transition-colors shrink-0"
        >
          {isMuted ? <VolumeX size={14} /> : <Volume2 size={14} />}
        </button>
      </div>
    </div>
  );
}
