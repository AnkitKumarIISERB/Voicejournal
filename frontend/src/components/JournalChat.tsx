import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, Send, Bot, User, Sparkles, Volume2, VolumeX, Mic } from 'lucide-react';
import { apiClient } from '../api/client';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export default function JournalChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [selectedVoice, setSelectedVoice] = useState('en-US-JennyNeural');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const getAvatarForVoice = (voiceId: string) => {
    switch(voiceId) {
      case 'en-US-JennyNeural': return '/avatars/avatar_jenny.png';
      case 'en-US-AriaNeural': return '/avatars/avatar_aria.png';
      case 'en-GB-SoniaNeural': return '/avatars/avatar_sonia.png';
      case 'en-US-SteffanNeural': return '/avatars/avatar_steffan.png';
      case 'hi-IN-SwaraNeural': return '/avatars/avatar_kiaa.png';
      case 'hi-IN-MadhurNeural': return '/avatars/avatar_veer.png';
      default: return '/avatars/avatar_jenny.png';
    }
  };

  const getNameForVoice = (voiceId: string) => {
    switch(voiceId) {
      case 'en-US-JennyNeural': return 'Jenny';
      case 'en-US-AriaNeural': return 'Aria';
      case 'en-GB-SoniaNeural': return 'Sonia';
      case 'en-US-SteffanNeural': return 'Steffan';
      case 'hi-IN-SwaraNeural': return 'Kiaa';
      case 'hi-IN-MadhurNeural': return 'Veer';
      default: return 'Journal AI';
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const SUGGESTIONS = [
    "How was I feeling last week?",
    "What's my most common emotion?",
    "Am I getting better over time?",
    "When was I happiest this month?",
  ];

  const startListening = () => {
    const SpeechRecognition = window.SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Your browser doesn't support voice input. Try Chrome or Safari.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    
    recognition.onstart = () => setIsListening(true);
    
    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setInput(transcript);
      // Auto send after speaking
      handleSend(transcript);
    };
    
    recognition.onerror = () => setIsListening(false);
    recognition.onend = () => setIsListening(false);
    
    recognition.start();
  };

  const handleSend = async (text?: string) => {
    const question = text || input.trim();
    if (!question) return;

    setMessages(prev => [...prev, { role: 'user', content: question }]);
    setInput('');
    setIsLoading(true);

    try {
      // Pass previous messages for memory context
      const res = await apiClient.post('/journals/chat', { 
        question, 
        voice_id: selectedVoice,
        chat_history: messages 
      });
      const answer = res.data.answer;
      const ttsText = res.data.tts_text || answer;
      setMessages(prev => [...prev, { role: 'assistant', content: answer }]);

      // Play voice if enabled
      if (voiceEnabled) {
        setIsSpeaking(true);
        try {
          const ttsRes = await apiClient.post('/journals/chat/tts', { text: ttsText, voice_id: selectedVoice }, { responseType: 'blob' });
          const url = URL.createObjectURL(ttsRes.data);
          
          if (audioRef.current) {
            audioRef.current.pause();
          }
          
          const audio = new Audio(url);
          audioRef.current = audio;
          audio.onended = () => setIsSpeaking(false);
          audio.play();
        } catch (err) {
          console.error("TTS failed:", err);
          setIsSpeaking(false);
        }
      }

    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I couldn\'t process your question right now. Please try again.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleVoice = () => {
    if (voiceEnabled && audioRef.current) {
      audioRef.current.pause();
      setIsSpeaking(false);
    }
    setVoiceEnabled(!voiceEnabled);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-gradient-to-r from-primary to-secondary shadow-lg shadow-primary/30 flex items-center justify-center text-white hover:scale-110 transition-transform z-50 group"
        title="Chat with your journal (Shift+C)"
      >
        <MessageSquare size={22} />
        <span className="absolute -top-1 -right-1 w-4 h-4 bg-green-400 rounded-full border-2 border-background animate-pulse"></span>
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 w-96 h-[500px] bg-surface/95 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl shadow-black/50 flex flex-col z-50 fade-in-up overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-white/10 flex items-center justify-between bg-gradient-to-r from-primary/10 to-secondary/10">
        <div className="flex items-center gap-3">
          <div className="relative w-10 h-10 flex items-center justify-center">
            {isSpeaking && (
              <>
                <div className="avatar-pulse-ring"></div>
                <div className="avatar-pulse-ring"></div>
                <div className="avatar-pulse-ring"></div>
              </>
            )}
            <img 
              src={getAvatarForVoice(selectedVoice)} 
              alt="AI Avatar" 
              className={`w-full h-full rounded-full object-cover border-2 border-primary/30 shadow-lg relative z-10 ${isSpeaking ? 'animate-avatar-float animate-avatar-glow' : ''}`}
            />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white">{getNameForVoice(selectedVoice)}</h4>
            <span className="text-xs text-primary">{isSpeaking ? 'Speaking...' : 'Online'}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {voiceEnabled && (
            <select
              value={selectedVoice}
              onChange={(e) => setSelectedVoice(e.target.value)}
              className="bg-black/20 text-xs text-white/80 border border-white/10 rounded-md px-1 py-1 focus:outline-none focus:border-primary/50"
            >
              <option value="en-US-JennyNeural">Jenny (Sweet)</option>
              <option value="en-US-AriaNeural">Aria (Calm)</option>
              <option value="en-GB-SoniaNeural">Sonia (British)</option>
              <option value="en-US-SteffanNeural">Steffan (Calm)</option>
              <option value="hi-IN-SwaraNeural">Kiaa (Indian)</option>
              <option value="hi-IN-MadhurNeural">Veer (Indian)</option>
            </select>
          )}
          <button
            onClick={toggleVoice}
            className={`p-1.5 rounded-lg transition-colors ${voiceEnabled ? 'text-primary bg-primary/20' : 'text-white/40 hover:text-white/60 hover:bg-white/10'}`}
            title={voiceEnabled ? "Mute Voice" : "Enable Voice"}
          >
            {voiceEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
          </button>
          <button
            onClick={() => setIsOpen(false)}
            className="text-textMuted hover:text-white transition-colors text-lg ml-1"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-hide">
        {messages.length === 0 && (
          <div className="text-center py-6">
            <Sparkles size={32} className="text-primary mx-auto mb-3 opacity-50" />
            <p className="text-sm text-textMuted mb-4">Ask me anything about your mood journal!</p>
            <div className="space-y-2">
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(s)}
                  className="block w-full text-left px-3 py-2 text-xs text-white/60 bg-white/5 hover:bg-white/10 rounded-lg transition-colors border border-white/5 hover:border-primary/30"
                >
                  💬 {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.role === 'assistant' && (
              <div className="w-7 h-7 shrink-0 mt-1">
                <img 
                  src={getAvatarForVoice(selectedVoice)} 
                  alt="AI Avatar" 
                  className="w-full h-full rounded-full object-cover border border-primary/30"
                />
              </div>
            )}
            <div
              className={`max-w-[80%] px-3 py-2 rounded-2xl text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-primary/20 text-white rounded-br-md'
                  : 'bg-white/5 text-white/80 rounded-bl-md border border-white/5'
              }`}
            >
              {msg.content}
            </div>
            {msg.role === 'user' && (
              <div className="w-6 h-6 rounded-full bg-secondary/20 flex items-center justify-center shrink-0 mt-1">
                <User size={12} className="text-secondary" />
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-2 items-start">
            <div className="w-7 h-7 shrink-0">
              <img 
                src={getAvatarForVoice(selectedVoice)} 
                alt="AI Avatar" 
                className="w-full h-full rounded-full object-cover border border-primary/30 animate-pulse"
              />
            </div>
            <div className="bg-white/5 px-4 py-3 rounded-2xl rounded-bl-md border border-white/5">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-primary/50 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                <div className="w-2 h-2 bg-primary/50 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                <div className="w-2 h-2 bg-primary/50 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-white/10">
        <div className="flex items-center gap-2">
          <button
            onClick={startListening}
            disabled={isLoading || isSpeaking}
            className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-colors ${
              isListening 
                ? 'bg-red-500/20 text-red-400 animate-pulse' 
                : 'bg-white/5 text-white/60 hover:bg-white/10 hover:text-white'
            }`}
            title="Voice Input"
          >
            <Mic size={14} />
          </button>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder={isListening ? "Listening..." : "Ask about your mood..."}
            className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-primary/50"
            disabled={isLoading || isListening}
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || isLoading}
            className="w-9 h-9 rounded-xl bg-primary/20 flex items-center justify-center text-primary hover:bg-primary/30 disabled:opacity-30 transition-colors shrink-0"
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
