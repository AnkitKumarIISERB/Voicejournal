import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { apiClient } from '../api/client';
import { Mic, ArrowRight, Shield, Brain, BarChart3 } from 'lucide-react';

export default function Login() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      if (isLogin) {
        // OAuth2 Password Flow requires form data, not JSON
        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);

        const response = await apiClient.post('/auth/login', formData, {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        });
        login(response.data.access_token, response.data.refresh_token);
      } else {
        await apiClient.post('/auth/register', { email, password });
        setIsLogin(true);
        setError('Registration successful! Please login.');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'An error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background relative overflow-hidden noise-overlay">
      {/* Animated floating orbs */}
      <div className="orb orb-1" style={{ top: '10%', left: '15%' }}></div>
      <div className="orb orb-2" style={{ bottom: '15%', right: '10%' }}></div>
      <div className="orb orb-3" style={{ top: '60%', left: '60%' }}></div>

      {/* Grid pattern overlay */}
      <div className="absolute inset-0 opacity-[0.02]" style={{
        backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
        backgroundSize: '60px 60px'
      }}></div>

      <div className="relative z-10 w-full max-w-5xl mx-auto px-6 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
        
        {/* Left side - Hero */}
        <div className="hidden lg:block fade-in-up">
          <div className="mb-8">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-medium mb-6">
              <span className="glow-dot bg-green-400 text-green-400"></span>
              AI-Powered Emotion Intelligence
            </div>
            <h1 className="text-5xl font-bold text-white leading-tight mb-4">
              Your voice tells a<br />
              <span className="gradient-text">deeper story</span>
            </h1>
            <p className="text-lg text-textMuted leading-relaxed">
              VoiceJournal uses WavLM neural networks to decode emotions from your voice, 
              tracking your mental wellness journey with clinical precision.
            </p>
          </div>

          {/* Feature pills */}
          <div className="space-y-4">
            {[
              { icon: Brain, label: 'WavLM Acoustic Analysis', desc: 'F1 Score: 0.80+', color: 'text-violet-400' },
              { icon: Shield, label: 'AES-256 Encrypted', desc: 'HIPAA-ready architecture', color: 'text-blue-400' },
              { icon: BarChart3, label: 'Clinical Insights', desc: 'Real-time risk detection', color: 'text-rose-400' },
            ].map((feature, i) => (
              <div key={i} className={`fade-in-up fade-in-up-delay-${i + 1} flex items-center gap-4 p-3 rounded-xl bg-white/[0.03] border border-white/[0.05] hover:bg-white/[0.06] transition-all duration-300`}>
                <div className={`w-10 h-10 rounded-lg bg-white/[0.05] flex items-center justify-center ${feature.color}`}>
                  <feature.icon size={20} />
                </div>
                <div>
                  <div className="text-white text-sm font-medium">{feature.label}</div>
                  <div className="text-textMuted text-xs">{feature.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right side - Auth card */}
        <div className="fade-in-up fade-in-up-delay-2">
          <div className="glass-panel p-8 rounded-3xl relative overflow-hidden">
            {/* Top glow line */}
            <div className="absolute top-0 left-1/4 right-1/4 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent"></div>
            
            {/* Shimmer overlay */}
            <div className="absolute inset-0 shimmer rounded-3xl"></div>

            <div className="relative z-10">
              <div className="flex flex-col items-center mb-8">
                {/* Animated mic icon with rings */}
                <div className="relative mb-6">
                  <div className="pulse-ring w-20 h-20 -top-1 -left-1"></div>
                  <div className="pulse-ring pulse-ring-delay w-20 h-20 -top-1 -left-1"></div>
                  <div className="w-[72px] h-[72px] bg-gradient-to-br from-primary via-violet-500 to-secondary rounded-2xl flex items-center justify-center shadow-2xl shadow-primary/30 relative">
                    <Mic size={32} className="text-white" />
                  </div>
                </div>
                <h2 className="text-2xl font-bold text-white tracking-tight">
                  {isLogin ? 'Welcome back' : 'Get started'}
                </h2>
                <p className="text-textMuted mt-1.5 text-sm">
                  {isLogin ? 'Sign in to your journal' : 'Create your free account'}
                </p>
              </div>

              {error && (
                <div className={`p-3 rounded-xl mb-6 text-sm backdrop-blur-sm ${error.includes('successful') ? 'bg-green-500/10 text-green-300 border border-green-500/20' : 'bg-red-500/10 text-red-300 border border-red-500/20'}`}>
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-textMuted mb-2 uppercase tracking-wider">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="input-field"
                    required
                    placeholder="you@example.com"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-textMuted mb-2 uppercase tracking-wider">Password</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="input-field"
                    required
                    placeholder="••••••••"
                    minLength={8}
                  />
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="btn-primary w-full mt-6 flex items-center justify-center gap-2 py-3.5"
                >
                  {isLoading ? (
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  ) : (
                    <>
                      {isLogin ? 'Sign In' : 'Create Account'}
                      <ArrowRight size={18} />
                    </>
                  )}
                </button>
              </form>

              <div className="mt-6 text-center">
                <button
                  onClick={() => {
                    setIsLogin(!isLogin);
                    setError('');
                  }}
                  className="text-textMuted hover:text-primary transition-colors text-sm"
                >
                  {isLogin ? "Don't have an account? " : 'Already have an account? '}
                  <span className="text-primary font-medium">{isLogin ? 'Sign up' : 'Sign in'}</span>
                </button>
              </div>

              {/* Bottom trust badge */}
              <div className="mt-8 pt-6 border-t border-white/[0.06] flex items-center justify-center gap-6 text-[11px] text-textMuted/60">
                <span className="flex items-center gap-1"><Shield size={12} /> E2E Encrypted</span>
                <span>•</span>
                <span>Zero Cloud</span>
                <span>•</span>
                <span>$0 Cost</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
