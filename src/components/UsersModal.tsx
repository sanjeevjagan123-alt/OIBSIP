import React from 'react';
import { Users, X, MessageSquare, Radio } from 'lucide-react';
import { ActiveTarget, User } from '../types';

interface UsersModalProps {
  currentUser: User;
  users: User[];
  onlineUsers: string[];
  onClose: () => void;
  onStartDirectMessage: (target: ActiveTarget) => void;
}

export const UsersModal: React.FC<UsersModalProps> = ({
  currentUser,
  users,
  onlineUsers,
  onClose,
  onStartDirectMessage,
}) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div
        id="users-directory-modal"
        className="w-full max-w-md bg-[#111a2e] border border-slate-700/80 rounded-2xl shadow-2xl p-6 max-h-[80vh] flex flex-col"
      >
        <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-blue-600/20 text-blue-400">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Community Members</h2>
              <p className="text-xs text-slate-400">{users.length} registered members</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
          {users.map((u) => {
            const isMe = u.username.toLowerCase() === currentUser.username.toLowerCase();
            const isOnline = onlineUsers.some(name => name.toLowerCase() === u.username.toLowerCase());

            return (
              <div
                key={`user-card-${u.id}`}
                className="flex items-center justify-between p-2.5 rounded-xl bg-slate-900/60 hover:bg-slate-800/80 border border-slate-800 transition-all"
              >
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <div className="w-9 h-9 rounded-xl bg-slate-700 flex items-center justify-center text-xs font-bold text-white uppercase shadow-sm">
                      {u.username.charAt(0)}
                    </div>
                    <span
                      className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full ring-2 ring-[#111a2e] ${
                        isOnline ? 'bg-emerald-400' : 'bg-slate-500'
                      }`}
                    />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-white flex items-center gap-1.5">
                      {u.username}
                      {isMe && (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-blue-600/30 text-blue-300 font-normal">
                          You
                        </span>
                      )}
                    </p>
                    <p className="text-[10px] text-slate-400 flex items-center gap-1">
                      <span className={`w-1.5 h-1.5 rounded-full ${isOnline ? 'bg-emerald-400' : 'bg-slate-500'}`} />
                      {isOnline ? 'Active right now' : 'Offline'}
                    </p>
                  </div>
                </div>

                {!isMe && (
                  <button
                    onClick={() => {
                      onStartDirectMessage({
                        type: 'user',
                        id: u.username,
                        displayName: `@${u.username}`,
                        isOnline: isOnline,
                      });
                      onClose();
                    }}
                    className="py-1.5 px-3 rounded-lg bg-blue-600/20 hover:bg-blue-600 text-blue-300 hover:text-white text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer"
                  >
                    <MessageSquare className="w-3.5 h-3.5" />
                    <span>Message</span>
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
