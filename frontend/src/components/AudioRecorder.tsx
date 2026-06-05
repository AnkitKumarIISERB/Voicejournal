import React, { useState, useRef, useEffect } from 'react';
import { Mic, Square, Loader2, Waves } from 'lucide-react';
import { apiClient } from '../api/client';

interface AudioRecorderProps {
  onUploadSuccess: (entryId: number) => void;
}

export default function AudioRecorder({ onUploadSuccess }: AudioRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [duration, setDuration] = useState(0);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<BlobPart[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  
  // Waveform visualization
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      stopRecording();
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      if (audioContextRef.current?.state !== 'closed') audioContextRef.current?.close();
    };
  }, []);

  const drawWaveform = () => {
    if (!canvasRef.current || !analyserRef.current) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const analyser = analyserRef.current;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      animationFrameRef.current = requestAnimationFrame(draw);
      analyser.getByteFrequencyData(dataArray);

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const barCount = 64;
      const barWidth = canvas.width / barCount;
      const gap = 2;
      const centerY = canvas.height / 2;

      for (let i = 0; i < barCount; i++) {
        const dataIndex = Math.floor(i * bufferLength / barCount);
        const value = dataArray[dataIndex] / 255;
        const barHeight = Math.max(2, value * centerY * 0.9);

        // Gradient color based on intensity
        const hue = 260 - value * 30; // violet to blue
        const alpha = 0.4 + value * 0.6;
        
        ctx.fillStyle = `hsla(${hue}, 80%, 65%, ${alpha})`;
        
        // Mirror bars from center
        const x = i * barWidth + gap / 2;
        const w = barWidth - gap;
        
        // Top bar (going up from center)
        ctx.beginPath();
        ctx.roundRect(x, centerY - barHeight, w, barHeight, 2);
        ctx.fill();
        
        // Bottom bar (mirror going down)
        ctx.beginPath();
        ctx.roundRect(x, centerY, w, barHeight, 2);
        ctx.fill();
      }
    };

    draw();
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      // Audio Context for visualization
      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      const analyser = audioCtx.createAnalyser();
      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);
      analyser.fftSize = 256;
      
      audioContextRef.current = audioCtx;
      analyserRef.current = analyser;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        await uploadAudio(audioBlob);
        
        // Cleanup stream tracks
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
      setDuration(0);
      
      timerRef.current = setInterval(() => {
        setDuration((prev) => prev + 1);
      }, 1000);

      drawWaveform();

    } catch (error) {
      console.error('Error accessing microphone:', error);
      alert('Could not access microphone. Please ensure permissions are granted.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
    setIsRecording(false);
  };

  const uploadAudio = async (blob: Blob) => {
    setIsUploading(true);
    try {
      const formData = new FormData();
      // Fastapi expects standard upload file name
      formData.append('file', blob, 'journal.webm');

      const response = await apiClient.post('/journals/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      onUploadSuccess(response.data.entry_id);
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Failed to upload audio. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  // Idle waveform bars
  const idleBars = Array.from({ length: 32 }, (_, i) => {
    const center = 16;
    const dist = Math.abs(i - center) / center;
    const height = 4 + (1 - dist) * 24;
    return { height, delay: i * 0.06 };
  });

  return (
    <div className="glass-panel p-8 rounded-3xl flex flex-col items-center justify-center w-full relative overflow-hidden">
      {/* Subtle top glow */}
      <div className="absolute top-0 left-1/4 right-1/4 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent"></div>
      
      {/* Waveform area */}
      <div className="relative w-full h-28 mb-8 rounded-2xl overflow-hidden flex items-center justify-center bg-white/[0.02] border border-white/[0.05]">
        {isRecording ? (
          <canvas ref={canvasRef} width={500} height={112} className="w-full h-full" />
        ) : (
          <div className="flex items-end gap-[3px] h-12">
            {idleBars.map((bar, i) => (
              <div
                key={i}
                className="waveform-bar w-[6px] rounded-full"
                style={{
                  '--bar-height': `${bar.height}px`,
                  '--delay': `${bar.delay}s`,
                  animationDelay: `${bar.delay}s`,
                } as React.CSSProperties}
              ></div>
            ))}
          </div>
        )}

        {/* Recording indicator */}
        {isRecording && (
          <div className="absolute top-3 right-3 flex items-center gap-2 px-2.5 py-1 rounded-full bg-red-500/20 border border-red-500/30">
            <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div>
            <span className="text-red-300 text-xs font-medium">REC</span>
          </div>
        )}
      </div>
      
      {/* Controls */}
      <div className="flex items-center gap-8">
        <div className="text-3xl font-light tracking-[0.2em] text-white/80 font-mono w-24 text-center tabular-nums">
          {formatTime(duration)}
        </div>
        
        {isUploading ? (
          <div className="w-20 h-20 rounded-full bg-surface border border-white/10 flex items-center justify-center">
            <Loader2 className="animate-spin text-primary" size={28} />
          </div>
        ) : isRecording ? (
          <button 
            onClick={stopRecording}
            className="w-20 h-20 rounded-full bg-gradient-to-br from-red-500 to-rose-600 hover:from-red-400 hover:to-rose-500 flex items-center justify-center transition-all duration-300 hover:scale-105 active:scale-95 shadow-xl shadow-red-500/25 relative"
          >
            {/* Pulsating danger rings */}
            <div className="pulse-ring w-20 h-20 -top-0 -left-0 !border-red-400/40" style={{ position: 'absolute' }}></div>
            <Square size={22} fill="currentColor" className="text-white" />
          </button>
        ) : (
          <div className="relative">
            {/* Pulsating rings behind button */}
            <div className="pulse-ring w-20 h-20 top-0 left-0" style={{ position: 'absolute' }}></div>
            <div className="pulse-ring pulse-ring-delay w-20 h-20 top-0 left-0" style={{ position: 'absolute' }}></div>
            <div className="pulse-ring pulse-ring-delay-2 w-20 h-20 top-0 left-0" style={{ position: 'absolute' }}></div>
            <button 
              onClick={startRecording}
              className="w-20 h-20 rounded-full bg-gradient-to-br from-primary via-violet-500 to-secondary hover:opacity-90 flex items-center justify-center transition-all duration-300 hover:scale-110 active:scale-95 shadow-xl shadow-primary/30 relative z-10"
            >
              <Mic size={28} className="text-white" />
            </button>
          </div>
        )}

        {/* Empty spacer to balance layout */}
        <div className="w-24"></div>
      </div>
      
      <p className="mt-6 text-sm text-textMuted text-center">
        {isUploading ? (
          <span className="flex items-center justify-center gap-2">
            <Waves size={16} className="text-primary animate-pulse" />
            Analyzing your voice with WavLM...
          </span>
        ) : isRecording ? (
          <span className="text-white/60">Speak freely. Your thoughts are encrypted.</span>
        ) : (
          'Tap to start your audio journal'
        )}
      </p>
    </div>
  );
}
