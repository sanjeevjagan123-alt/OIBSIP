import React from 'react';
import { Hash, Plus, MessageSquare, Search, LogOut, User, Users, Radio } from 'lucide-react';
import { ActiveTarget, Room, User as UserType } from '../types';

interface SidebarProps {
  currentUser: UserType;
  rooms: Room[];
  users: UserType[];
  onlineUsers: string[];
  activeTarget: ActiveTarget;
  unreadCounts: Record<string, number>;
  onSelectTarget: (target: ActiveTarget) => void;
  onOpenCreateRoom: () => void;
  onOpenSearch: () => void;
  onOpenUsersModal: () => void;
  onLogout: () => void;
  isMobileOpen: boolean;
  onCloseMobile: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentUser,
  rooms,
  users,
  onlineUsers,
  activeTarget,
  unreadCounts,
  onSelectTarget,
  onOpenCreateRoom,
  onOpenSearch,
  onOpenUsersModal,
  onLogout,
  isMobileOpen,
  onCloseMobile,
}) => {
  const otherUsers = users.filter(u => u.username.toLowerCase() !== currentUser.username.toLowerCase());

  return (
    <>
      {/* Mobile backdrop */}
      {isMobileOpen && (
        <div
          id="sidebar-mobile-backdrop"
          onClick={onCloseMobile}
          className="fixed inset-0 bg-black/60 z-30 md:hidden backdrop-blur-sm"
        />
      )}

      <aside
        id="app-sidebar"
        className={`fixed md:static inset-y-0 left-0 z-40 w-72 bg-[#0d1527] border-r border-slate-800/80 flex flex-col transition-transform duration-200 ease-in-out ${
          isMobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        {/* Workspace Brand / Header */}
        <div className="p-4 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 font-bold text-base shadow-sm">
              🌴
            </div>
            <div>
              <h2 className="text-sm font-bold text-white tracking-tight flex items-center gap-1.5">
                Oasis Hub
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
              </h2>
              <p className="text-[11px] text-slate-400">
                {onlineUsers.length} online now
              </p>
            </div>
          </div>

          <button
            id="btn-global-search"
            onClick={onOpenSearch}
            title="Search messages"
            className="p-2 rounded-lg bg-slate-800/60 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
          >
            <Search className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable Channels & DMs */}
        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-6">
          {/* Channels Section */}
          <div>
            <div className="flex items-center justify-between px-2 mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
              <span className="flex items-center gap-1.5">
                <Hash className="w-3.5 h-3.5 text-slate-500" /> Channels ({rooms.length})
              </span>
              <button
                id="btn-create-room"
                onClick={onOpenCreateRoom}
                title="Create Room"
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="space-y-0.5">
              {rooms.map((room) => {
                const isActive = activeTarget.type === 'room' && activeTarget.id.toLowerCase() === room.name.toLowerCase();
                const unreadKey = `room:${room.name.toLowerCase()}`;
                const unread = unreadCounts[unreadKey] || 0;

                return (
                  <button
                    key={`room-${room.id}`}
                    id={`room-btn-${room.name}`}
                    onClick={() => {
                      onSelectTarget({
                        type: 'room',
                        id: room.name,
                        displayName: `#${room.name}`,
                        description: room.description
                      });
                      onCloseMobile();
                    }}
                    className={`w-full flex items-center justify-between px-2.5 py-2 rounded-xl text-xs font-medium transition-all group cursor-pointer ${
                      isActive
                        ? 'bg-blue-600/20 text-blue-300 border border-blue-500/30'
                        : 'text-slate-300 hover:bg-slate-800/50 hover:text-white'
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <Hash className={`w-4 h-4 shrink-0 ${isActive ? 'text-blue-400' : 'text-slate-500 group-hover:text-slate-400'}`} />
                      <span className="truncate">{room.name}</span>
                    </div>
                    {unread > 0 && (
                      <span className="px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-blue-500 text-white shrink-0">
                        {unread}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Direct Messages Section */}
          <div>
            <div className="flex items-center justify-between px-2 mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
              <span className="flex items-center gap-1.5">
                <MessageSquare className="w-3.5 h-3.5 text-slate-500" /> Direct Messages
              </span>
              <button
                id="btn-open-users-modal"
                onClick={onOpenUsersModal}
                title="Browse all members"
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
              >
                <Users className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="space-y-0.5">
              {otherUsers.length === 0 ? (
                <div className="px-2 py-3 text-[11px] text-slate-500 text-center">
                  No other members registered yet.
                </div>
              ) : (
                otherUsers.map((u) => {
                  const isOnline = onlineUsers.some(name => name.toLowerCase() === u.username.toLowerCase());
                  const isActive = activeTarget.type === 'user' && activeTarget.id.toLowerCase() === u.username.toLowerCase();
                  const unreadKey = `user:${u.username.toLowerCase()}`;
                  const unread = unreadCounts[unreadKey] || 0;

                  return (
                    <button
                      key={`user-${u.id}`}
                      id={`user-dm-btn-${u.username}`}
                      onClick={() => {
                        onSelectTarget({
                          type: 'user',
                          id: u.username,
                          displayName: `@${u.username}`,
                          description: isOnline ? 'Active right now' : 'Offline',
                          isOnline: isOnline
                        });
                        onCloseMobile();
                      }}
                      className={`w-full flex items-center justify-between px-2.5 py-2 rounded-xl text-xs font-medium transition-all group cursor-pointer ${
                        isActive
                          ? 'bg-blue-600/20 text-blue-300 border border-blue-500/30'
                          : 'text-slate-300 hover:bg-slate-800/50 hover:text-white'
                      }`}
                    >
                      <div className="flex items-center gap-2.5 truncate">
                        <div className="relative shrink-0">
                          <div className="w-6 h-6 rounded-lg bg-slate-700/80 flex items-center justify-center text-[10px] font-bold text-slate-200 uppercase">
                            {u.username.charAt(0)}
                          </div>
                          <span
                            className={`absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full ring-2 ring-[#0d1527] ${
                              isOnline ? 'bg-emerald-400' : 'bg-slate-500'
                            }`}
                          />
                        </div>
                        <span className="truncate">{u.username}</span>
                      </div>
                      {unread > 0 && (
                        <span className="px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-blue-500 text-white shrink-0">
                          {unread}
                        </span>
                      )}
                    </button>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Current User Bar / Footer */}
        <div className="p-3 bg-[#0a101f] border-t border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-2.5 truncate">
            <div className="relative shrink-0">
              <div className="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center text-xs font-bold text-white uppercase shadow-sm">
                {currentUser.username.charAt(0)}
              </div>
              <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-400 ring-2 ring-[#0a101f]" />
            </div>
            <div className="truncate">
              <p className="text-xs font-semibold text-white truncate">{currentUser.username}</p>
              <p className="text-[10px] text-emerald-400 flex items-center gap-1">
                <Radio className="w-2.5 h-2.5 animate-pulse" /> Online
              </p>
            </div>
          </div>

          <button
            id="btn-logout"
            onClick={onLogout}
            title="Sign out"
            className="p-2 rounded-lg text-slate-400 hover:text-red-400 hover:bg-slate-800/80 transition-colors cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </aside>
    </>
  );
};
