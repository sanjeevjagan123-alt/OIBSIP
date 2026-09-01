import React, { useState } from 'react';
import { LogIn, UserPlus, Sparkles, MessageSquare } from 'lucide-react';
import { loginUser, registerUser } from '../services/api';
import { User } from '../types';

interface AuthViewProps {
  onSuccess: (user: User) => void;
}

export const AuthView: React.FC<AuthViewProps> = ({ onSuccess }) => {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!username.trim() || !password.trim()) {
      setError('Please fill in all fields.');
      return;
    }

    setLoading(true);
    try {
      if (isRegister) {
        const user = await registerUser(username, password);
        onSuccess(user);
      } else {
        const user = await loginUser(username, password);
        onSuccess(user);
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Authentication error occurred');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleQuickGuest = async () => {
    setError(null);
    setLoading(true);
    const randomSuffix = Math.floor(1000 + Math.random() * 9000);
    const guestName = `Explorer_${randomSuffix}`;
    const guestPass = 'oasis123';
    try {
      const user = await registerUser(guestName, guestPass);
      onSuccess(user);
    } catch {
      try {
        const user = await loginUser(guestName, guestPass);
        onSuccess(user);
      } catch (err: unknown) {
        if (err instanceof Error) setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#0b1120] via-[#0f172a] to-[#111a2e] p-4 text-slate-100">
      <div id="auth-card" className="w-full max-w-md bg-[#111a2e]/90 border border-slate-700/60 rounded-2xl p-8 shadow-2xl backdrop-blur-xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-600/20 border border-blue-500/30 text-blue-400 mb-4 shadow-lg shadow-blue-500/10">
            <MessageSquare className="w-7 h-7" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center justify-center gap-2">
            Oasis Chat
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-400/30">v2.0</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time messaging, channels, direct messages & presence
          </p>
        </div>

        {/* Tab switch */}
        <div className="flex bg-slate-900/80 p-1 rounded-xl mb-6 border border-slate-800">
          <button
            id="tab-login"
            type="button"
            onClick={() => { setIsRegister(false); setError(null); }}
            className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all ${
              !isRegister ? 'bg-blue-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Sign In
          </button>
          <button
            id="tab-register"
            type="button"
            onClick={() => { setIsRegister(true); setError(null); }}
            className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all ${
              isRegister ? 'bg-blue-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Create Account
          </button>
        </div>

        {/* Error message */}
        {error && (
          <div id="auth-error" className="mb-5 p-3 rounded-lg bg-red-950/50 border border-red-500/40 text-red-200 text-xs flex items-center gap-2">
            <span className="font-semibold">Error:</span> {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5" htmlFor="auth-username">
              Username
            </label>
            <input
              id="auth-username"
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. alex_rivera"
              className="w-full px-3.5 py-2.5 bg-slate-900/90 border border-slate-700/80 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5" htmlFor="auth-password">
              Password
            </label>
            <input
              id="auth-password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-3.5 py-2.5 bg-slate-900/90 border border-slate-700/80 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-colors"
            />
          </div>

          <button
            id="auth-submit-btn"
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-2.5 px-4 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 disabled:opacity-50 text-white font-medium text-sm rounded-xl transition-all shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2 cursor-pointer"
          >
            {loading ? (
              <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : isRegister ? (
              <>
                <UserPlus className="w-4 h-4" />
                <span>Register & Join Oasis</span>
              </>
            ) : (
              <>
                <LogIn className="w-4 h-4" />
                <span>Sign In</span>
              </>
            )}
          </button>
        </form>

        {/* Quick Guest Join */}
        <div className="mt-6 pt-5 border-t border-slate-800/80">
          <button
            id="auth-quick-guest-btn"
            type="button"
            onClick={handleQuickGuest}
            disabled={loading}
            className="w-full py-2.5 px-4 bg-slate-800/90 hover:bg-slate-700/90 text-slate-200 hover:text-white text-xs font-medium rounded-xl border border-slate-700/60 transition-all flex items-center justify-center gap-2 cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>Generate Quick Guest Identity</span>
          </button>
          <p className="text-[11px] text-center text-slate-500 mt-2">
            No email verification required. Hashed with PBKDF2.
          </p>
        </div>
      </div>
    </div>
  );
};
