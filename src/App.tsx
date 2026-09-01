import React, { useState, useEffect, useCallback } from 'react';
import { AuthView } from './components/AuthView';
import { Sidebar } from './components/Sidebar';
import { ChatHeader } from './components/ChatHeader';
import { MessageList } from './components/MessageList';
import { MessageInput } from './components/MessageInput';
import { EmojiPicker } from './components/EmojiPicker';
import { SearchModal } from './components/SearchModal';
import { CreateRoomModal } from './components/CreateRoomModal';
import { UsersModal } from './components/UsersModal';
import { getSocket } from './services/socket';
import { fetchMessages, fetchRooms, fetchUsers } from './services/api';
import { ActiveTarget, Message, Room, User } from './types';

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('oasis_user');
    if (saved) {
      try { return JSON.parse(saved); } catch { return null; }
    }
    return null;
  });

  const [rooms, setRooms] = useState<Room[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [onlineUsers, setOnlineUsers] = useState<string[]>([]);
  const [activeTarget, setActiveTarget] = useState<ActiveTarget>({
    type: 'room',
    id: 'general',
    displayName: '#general',
    description: 'General Oasis discussion and welcome hub',
  });

  const [messages, setMessages] = useState<Message[]>([]);
  const [typingUsers, setTypingUsers] = useState<string[]>([]);
  const [unreadCounts, setUnreadCounts] = useState<Record<string, number>>({});

  // Modals & toggles
  const [isEmojiPickerOpen, setIsEmojiPickerOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isCreateRoomOpen, setIsCreateRoomOpen] = useState(false);
  const [isUsersModalOpen, setIsUsersModalOpen] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);

  // Audio chime
  const playNotificationSound = useCallback(() => {
    if (!notificationsEnabled) return;
    try {
      const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
      osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15); // A5
      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.25);
    } catch {
      // ignore audio context failures
    }
  }, [notificationsEnabled]);

  // Load initial rooms & users
  const refreshRoomsAndUsers = useCallback(async () => {
    try {
      const [roomsData, usersData] = await Promise.all([fetchRooms(), fetchUsers()]);
      setRooms(roomsData);
      setUsers(usersData);
    } catch (e) {
      console.error('Failed to load rooms and users:', e);
    }
  }, []);

  useEffect(() => {
    refreshRoomsAndUsers();
  }, [refreshRoomsAndUsers]);

  // Load message history when active target changes
  useEffect(() => {
    if (!currentUser) return;
    let isCancelled = false;

    fetchMessages(activeTarget.type, activeTarget.id, currentUser.username)
      .then((data) => {
        if (!isCancelled) {
          setMessages(data);
          // Clear unread for this target
          const targetKey = `${activeTarget.type}:${activeTarget.id.toLowerCase()}`;
          setUnreadCounts(prev => ({ ...prev, [targetKey]: 0 }));

          // Mark delivered for pending messages
          const pendingIds = data
            .filter(m => m.sender_username.toLowerCase() !== currentUser.username.toLowerCase() && m.delivery_state === 'sent')
            .map(m => m.id);
          if (pendingIds.length > 0) {
            getSocket().emit('mark_delivered', { message_ids: pendingIds });
          }
        }
      })
      .catch((err) => console.error('Failed to load message history:', err));

    return () => {
      isCancelled = true;
    };
  }, [activeTarget, currentUser]);

  // Socket.io event wiring
  useEffect(() => {
    if (!currentUser) return;
    const socket = getSocket();

    // Authenticate
    socket.emit('authenticate', { username: currentUser.username, userId: currentUser.id });
    socket.emit('set_active_target', { target_type: activeTarget.type, target_id: activeTarget.id });

    const handlePresence = (data: { online_users: string[] }) => {
      setOnlineUsers(data.online_users);
    };

    const handleNewMessage = (msg: Message) => {
      // Check if message belongs to current conversation
      const isCurrentRoom = activeTarget.type === 'room' && msg.target_type === 'room' && msg.target_id.toLowerCase() === activeTarget.id.toLowerCase();
      const isCurrentDM = activeTarget.type === 'user' && msg.target_type === 'user' && (
        (msg.sender_username.toLowerCase() === activeTarget.id.toLowerCase() && msg.target_id.toLowerCase() === currentUser.username.toLowerCase()) ||
        (msg.sender_username.toLowerCase() === currentUser.username.toLowerCase() && msg.target_id.toLowerCase() === activeTarget.id.toLowerCase())
      );

      if (isCurrentRoom || isCurrentDM) {
        setMessages(prev => [...prev, msg]);
        if (msg.sender_username.toLowerCase() !== currentUser.username.toLowerCase()) {
          playNotificationSound();
          if (msg.delivery_state === 'sent') {
            socket.emit('mark_delivered', { message_ids: [msg.id] });
          }
        }
      } else {
        // Increment unread count for other channel / DM
        const targetKey = msg.target_type === 'room'
          ? `room:${msg.target_id.toLowerCase()}`
          : `user:${msg.sender_username.toLowerCase()}`;
        setUnreadCounts(prev => ({
          ...prev,
          [targetKey]: (prev[targetKey] || 0) + 1
        }));
        playNotificationSound();
      }
    };

    const handleTypingUpdate = (data: {
      sender_username: string;
      target_type: 'room' | 'user';
      target_id: string;
      is_typing: boolean;
    }) => {
      if (data.sender_username.toLowerCase() === currentUser.username.toLowerCase()) return;

      const matchesTarget = (
        (activeTarget.type === 'room' && data.target_type === 'room' && data.target_id.toLowerCase() === activeTarget.id.toLowerCase()) ||
        (activeTarget.type === 'user' && data.target_type === 'user' && data.sender_username.toLowerCase() === activeTarget.id.toLowerCase())
      );

      if (matchesTarget) {
        setTypingUsers(prev => {
          if (data.is_typing) {
            return prev.includes(data.sender_username) ? prev : [...prev, data.sender_username];
          } else {
            return prev.filter(u => u !== data.sender_username);
          }
        });
      }
    };

    const handleDeliveryUpdate = (data: { message_ids: number[]; state: 'delivered' }) => {
      setMessages(prev =>
        prev.map(m => (data.message_ids.includes(m.id) ? { ...m, delivery_state: 'delivered' } : m))
      );
    };

    const handleRoomUpdate = () => {
      refreshRoomsAndUsers();
    };

    socket.on('presence_update', handlePresence);
    socket.on('new_message', handleNewMessage);
    socket.on('typing_update', handleTypingUpdate);
    socket.on('delivery_update', handleDeliveryUpdate);
    socket.on('room_update', handleRoomUpdate);

    return () => {
      socket.off('presence_update', handlePresence);
      socket.off('new_message', handleNewMessage);
      socket.off('typing_update', handleTypingUpdate);
      socket.off('delivery_update', handleDeliveryUpdate);
      socket.off('room_update', handleRoomUpdate);
    };
  }, [currentUser, activeTarget, playNotificationSound, refreshRoomsAndUsers]);

  const handleSendMessage = (content: string) => {
    if (!currentUser) return;
    const socket = getSocket();
    socket.emit('send_message', {
      sender_username: currentUser.username,
      target_type: activeTarget.type,
      target_id: activeTarget.id,
      content,
    });
  };

  const handleTyping = (isTyping: boolean) => {
    if (!currentUser) return;
    const socket = getSocket();
    socket.emit('typing', {
      sender_username: currentUser.username,
      target_type: activeTarget.type,
      target_id: activeTarget.id,
      is_typing: isTyping,
    });
  };

  const handleSelectTarget = (target: ActiveTarget) => {
    setActiveTarget(target);
    setTypingUsers([]);
    setIsEmojiPickerOpen(false);
    const socket = getSocket();
    socket.emit('set_active_target', { target_type: target.type, target_id: target.id });
  };

  const handleAuthSuccess = (user: User) => {
    setCurrentUser(user);
    localStorage.setItem('oasis_user', JSON.stringify(user));
    refreshRoomsAndUsers();
  };

  const handleLogout = () => {
    setCurrentUser(null);
    localStorage.removeItem('oasis_user');
  };

  if (!currentUser) {
    return <AuthView onSuccess={handleAuthSuccess} />;
  }

  const isTargetUserOnline = activeTarget.type === 'user'
    ? onlineUsers.some(name => name.toLowerCase() === activeTarget.id.toLowerCase())
    : false;

  const currentRoom = rooms.find(r => r.name.toLowerCase() === activeTarget.id.toLowerCase());

  return (
    <div className="h-full flex flex-col md:flex-row bg-[#0b1120] text-slate-100 overflow-hidden font-sans select-none">
      {/* Sidebar */}
      <Sidebar
        currentUser={currentUser}
        rooms={rooms}
        users={users}
        onlineUsers={onlineUsers}
        activeTarget={activeTarget}
        unreadCounts={unreadCounts}
        onSelectTarget={handleSelectTarget}
        onOpenCreateRoom={() => setIsCreateRoomOpen(true)}
        onOpenSearch={() => setIsSearchOpen(true)}
        onOpenUsersModal={() => setIsUsersModalOpen(true)}
        onLogout={handleLogout}
        isMobileOpen={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
      />

      {/* Main Chat Workspace */}
      <main className="flex-1 flex flex-col min-w-0 bg-[#0b1120] relative h-full">
        <ChatHeader
          activeTarget={activeTarget}
          isOnline={isTargetUserOnline}
          memberCount={currentRoom?.member_count || (activeTarget.type === 'room' ? 3 : undefined)}
          notificationsEnabled={notificationsEnabled}
          onToggleNotifications={() => setNotificationsEnabled(prev => !prev)}
          onOpenSearch={() => setIsSearchOpen(true)}
          onOpenUsersModal={() => setIsUsersModalOpen(true)}
          onToggleMobileSidebar={() => setIsMobileSidebarOpen(prev => !prev)}
        />

        {/* Message stream */}
        <MessageList
          messages={messages}
          currentUser={currentUser}
          typingUsers={typingUsers}
        />

        {/* Emoji picker popover */}
        {isEmojiPickerOpen && (
          <EmojiPicker
            onSelectEmoji={(emoji) => {
              // Append to input or send
              handleSendMessage(emoji);
              setIsEmojiPickerOpen(false);
            }}
            onClose={() => setIsEmojiPickerOpen(false)}
          />
        )}

        {/* Bottom Message Input Bar */}
        <MessageInput
          onSendMessage={handleSendMessage}
          onTyping={handleTyping}
          onToggleEmojiPicker={() => setIsEmojiPickerOpen(prev => !prev)}
          isEmojiPickerOpen={isEmojiPickerOpen}
        />
      </main>

      {/* Modals */}
      {isSearchOpen && (
        <SearchModal
          currentUser={currentUser}
          activeTarget={activeTarget}
          onClose={() => setIsSearchOpen(false)}
          onSelectResult={handleSelectTarget}
        />
      )}

      {isCreateRoomOpen && (
        <CreateRoomModal
          currentUser={currentUser}
          onClose={() => setIsCreateRoomOpen(false)}
          onRoomCreated={(newRoom) => {
            refreshRoomsAndUsers();
            handleSelectTarget({
              type: 'room',
              id: newRoom.name,
              displayName: `#${newRoom.name}`,
              description: newRoom.description,
            });
          }}
        />
      )}

      {isUsersModalOpen && (
        <UsersModal
          currentUser={currentUser}
          users={users}
          onlineUsers={onlineUsers}
          onClose={() => setIsUsersModalOpen(false)}
          onStartDirectMessage={handleSelectTarget}
        />
      )}
    </div>
  );
};

export default App;
