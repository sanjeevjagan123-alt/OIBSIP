import React, { useState, useEffect } from 'react';
import { Search, X, Hash, User, Calendar, ArrowRight } from 'lucide-react';
import { searchMessages } from '../services/api';
import { ActiveTarget, Message, User as UserType } from '../types';

interface SearchModalProps {
  currentUser: UserType;
  activeTarget: ActiveTarget;
  onClose: () => void;
  onSelectResult: (target: ActiveTarget) => void;
}

export const SearchModal: React.FC<SearchModalProps> = ({
  currentUser,
  activeTarget,
  onClose,
  onSelectResult,
}) => {
  const [query, setQuery] = useState('');
  const [scope, setScope] = useState<'current' | 'all'>('current');
  const [results, setResults] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const targetType = scope === 'current' ? activeTarget.type : undefined;
        const targetId = scope === 'current' ? activeTarget.id : undefined;
        const data = await searchMessages(query, targetType, targetId, currentUser.username);
        setResults(data);
      } catch (e) {
        console.error('Search error:', e);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query, scope, activeTarget, currentUser.username]);

  const handleSelect = (msg: Message) => {
    if (msg.target_type === 'room') {
      onSelectResult({
        type: 'room',
        id: msg.target_id,
        displayName: `#${msg.target_id}`,
      });
    } else {
      const otherUser = msg.sender_username.toLowerCase() === currentUser.username.toLowerCase()
        ? msg.target_id
        : msg.sender_username;
      onSelectResult({
        type: 'user',
        id: otherUser,
        displayName: `@${otherUser}`,
      });
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div
        id="search-modal-card"
        className="w-full max-w-xl bg-[#111a2e] border border-slate-700/80 rounded-2xl shadow-2xl flex flex-col max-h-[85vh] overflow-hidden"
      >
        {/* Search header & input */}
        <div className="p-4 border-b border-slate-800 flex items-center gap-3">
          <Search className="w-5 h-5 text-blue-400 shrink-0" />
          <input
            id="search-query-input"
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`Search messages in ${scope === 'current' ? activeTarget.displayName : 'all conversations'}...`}
            className="flex-1 bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none"
          />
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scope selector */}
        <div className="px-4 py-2 bg-slate-900/60 border-b border-slate-800 flex gap-2">
          <button
            onClick={() => setScope('current')}
            className={`px-3 py-1 text-xs rounded-lg font-medium transition-all ${
              scope === 'current'
                ? 'bg-blue-600/30 text-blue-300 border border-blue-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Current ({activeTarget.displayName})
          </button>
          <button
            onClick={() => setScope('all')}
            className={`px-3 py-1 text-xs rounded-lg font-medium transition-all ${
              scope === 'all'
                ? 'bg-blue-600/30 text-blue-300 border border-blue-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            All Channels & DMs
          </button>
        </div>

        {/* Results list */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {loading ? (
            <div className="py-12 flex flex-col items-center justify-center text-slate-500 gap-2">
              <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-xs">Searching message records...</p>
            </div>
          ) : results.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-xs">
              {query ? 'No matching messages found.' : 'Type keywords to search message history.'}
            </div>
          ) : (
            results.map((msg) => (
              <div
                key={`search-res-${msg.id}`}
                onClick={() => handleSelect(msg)}
                className="p-3 rounded-xl bg-slate-900/80 hover:bg-slate-800/80 border border-slate-800/80 hover:border-blue-500/40 transition-all cursor-pointer group"
              >
                <div className="flex items-center justify-between text-[11px] mb-1">
                  <div className="flex items-center gap-1.5 font-semibold text-slate-300">
                    <span className="text-blue-400">{msg.sender_username}</span>
                    <span className="text-slate-600">•</span>
                    <span className="text-slate-400 flex items-center gap-1">
                      {msg.target_type === 'room' ? (
                        <>
                          <Hash className="w-3 h-3 text-slate-500" />
                          {msg.target_id}
                        </>
                      ) : (
                        <>
                          <User className="w-3 h-3 text-slate-500" />
                          Direct
                        </>
                      )}
                    </span>
                  </div>
                  <span className="text-slate-500 text-[10px]">
                    {new Date(msg.timestamp).toLocaleDateString()} {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                <p className="text-xs text-slate-200 line-clamp-2">{msg.content}</p>

                <div className="mt-2 flex items-center justify-end text-[10px] text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity gap-1">
                  <span>Jump to message</span>
                  <ArrowRight className="w-3 h-3" />
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
