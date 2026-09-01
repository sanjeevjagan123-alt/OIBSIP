import React from 'react';
import { Menu, Hash, User, Search, Bell, BellOff, Users } from 'lucide-react';
import { ActiveTarget } from '../types';

interface ChatHeaderProps {
  activeTarget: ActiveTarget;
  isOnline?: boolean;
  memberCount?: number;
  notificationsEnabled: boolean;
  onToggleNotifications: () => void;
  onOpenSearch: () => void;
  onOpenUsersModal: () => void;
  onToggleMobileSidebar: () => void;
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({
  activeTarget,
  isOnline,
  memberCount,
  notificationsEnabled,
  onToggleNotifications,
  onOpenSearch,
  onOpenUsersModal,
  onToggleMobileSidebar,
}) => {
  return (
    <header id="chat-header" className="h-16 border-b border-slate-800/80 bg-[#0d1527]/90 backdrop-blur-md px-4 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-3 truncate">
        {/* Mobile menu trigger */}
        <button
          id="btn-mobile-sidebar-toggle"
          onClick={onToggleMobileSidebar}
          className="md:hidden p-2 rounded-lg bg-slate-800/80 text-slate-300 hover:text-white cursor-pointer"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Channel / User Icon */}
        <div className="w-10 h-10 rounded-xl bg-slate-800/90 border border-slate-700/60 flex items-center justify-center text-slate-200 shrink-0">
          {activeTarget.type === 'room' ? (
            <Hash className="w-5 h-5 text-blue-400" />
          ) : (
            <div className="relative">
              <span className="text-sm font-bold uppercase text-blue-400">
                {activeTarget.id.charAt(0)}
              </span>
              <span
                className={`absolute -bottom-1 -right-1 w-2.5 h-2.5 rounded-full ring-2 ring-[#0d1527] ${
                  isOnline ? 'bg-emerald-400' : 'bg-slate-500'
                }`}
              />
            </div>
          )}
        </div>

        {/* Title and details */}
        <div className="truncate">
          <div className="flex items-center gap-2">
            <h1 id="active-target-title" className="text-base font-bold text-white tracking-tight truncate">
              {activeTarget.displayName}
            </h1>
            {activeTarget.type === 'room' && (
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700/50">
                Channel
              </span>
            )}
            {activeTarget.type === 'user' && (
              <span
                className={`text-[11px] px-2 py-0.5 rounded-full border ${
                  isOnline
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                    : 'bg-slate-800 text-slate-400 border-slate-700/50'
                }`}
              >
                {isOnline ? 'Online' : 'Offline'}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 truncate">
            {activeTarget.description || (activeTarget.type === 'room' ? `${memberCount || 1} members participating` : 'Direct message')}
          </p>
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-1.5">
        <button
          id="btn-header-search"
          onClick={onOpenSearch}
          title="Search in this conversation"
          className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
        >
          <Search className="w-4 h-4" />
        </button>

        <button
          id="btn-header-members"
          onClick={onOpenUsersModal}
          title="View members"
          className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
        >
          <Users className="w-4 h-4" />
        </button>

        <button
          id="btn-toggle-notifications"
          onClick={onToggleNotifications}
          title={notificationsEnabled ? 'Notifications enabled' : 'Notifications muted'}
          className={`p-2 rounded-xl transition-colors cursor-pointer ${
            notificationsEnabled
              ? 'text-blue-400 hover:bg-blue-600/10'
              : 'text-slate-500 hover:bg-slate-800'
          }`}
        >
          {notificationsEnabled ? <Bell className="w-4 h-4" /> : <BellOff className="w-4 h-4" />}
        </button>
      </div>
    </header>
  );
};
