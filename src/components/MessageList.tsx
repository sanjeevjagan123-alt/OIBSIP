import React, { useEffect, useRef } from 'react';
import { Check, CheckCheck, User } from 'lucide-react';
import { Message, User as UserType } from '../types';

interface MessageListProps {
  messages: Message[];
  currentUser: UserType;
  typingUsers: string[];
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  currentUser,
  typingUsers,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, typingUsers]);

  const formatTime = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <div id="message-list-container" className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.length === 0 ? (
        <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500">
          <div className="w-12 h-12 rounded-2xl bg-slate-800/80 border border-slate-700/50 flex items-center justify-center text-2xl mb-3">
            💬
          </div>
          <p className="text-sm font-medium text-slate-300">No messages here yet</p>
          <p className="text-xs text-slate-500 mt-1 max-w-xs">
            Start the conversation! Say hello or use emojis like <code className="bg-slate-800 px-1 py-0.5 rounded text-blue-400">:smile:</code>, <code className="bg-slate-800 px-1 py-0.5 rounded text-blue-400">:fire:</code>, or <code className="bg-slate-800 px-1 py-0.5 rounded text-blue-400">:rocket:</code>.
          </p>
        </div>
      ) : (
        messages.map((msg, index) => {
          const isMe = msg.sender_username.toLowerCase() === currentUser.username.toLowerCase();
          const isSystem = msg.sender_username.toLowerCase() === 'system';

          if (isSystem) {
            return (
              <div key={`msg-${msg.id || index}`} className="flex items-center justify-center my-4">
                <div className="px-4 py-1.5 rounded-full bg-slate-800/90 border border-slate-700/60 text-xs text-slate-300 shadow-sm flex items-center gap-2 max-w-lg text-center">
                  <span>✨</span>
                  <span>{msg.content}</span>
                  <span className="text-[10px] text-slate-500">{formatTime(msg.timestamp)}</span>
                </div>
              </div>
            );
          }

          return (
            <div
              key={`msg-${msg.id || index}`}
              id={`message-item-${msg.id}`}
              className={`flex gap-3 max-w-[85%] md:max-w-[70%] group ${
                isMe ? 'ml-auto flex-row-reverse' : ''
              }`}
            >
              {/* Avatar */}
              <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700/80 flex items-center justify-center text-xs font-bold text-slate-200 shrink-0 uppercase shadow-sm">
                {msg.sender_username.charAt(0)}
              </div>

              {/* Message Bubble */}
              <div className="space-y-1">
                <div className={`flex items-center gap-2 text-[11px] ${isMe ? 'justify-end' : ''}`}>
                  <span className={`font-semibold ${isMe ? 'text-blue-400' : 'text-slate-300'}`}>
                    {isMe ? 'You' : msg.sender_username}
                  </span>
                  <span className="text-slate-500 text-[10px]">{formatTime(msg.timestamp)}</span>
                </div>

                <div
                  className={`p-3.5 rounded-2xl text-sm leading-relaxed shadow-md break-words whitespace-pre-wrap ${
                    isMe
                      ? 'bg-blue-600 text-white rounded-tr-none'
                      : 'bg-[#141f36] text-slate-100 border border-slate-700/60 rounded-tl-none'
                  }`}
                >
                  {msg.content}
                </div>

                {/* Delivery status indicator */}
                {isMe && (
                  <div className="flex items-center justify-end gap-1 text-[10px] text-slate-500 pr-1">
                    {msg.delivery_state === 'delivered' ? (
                      <span className="flex items-center gap-0.5 text-blue-400 font-medium">
                        <CheckCheck className="w-3.5 h-3.5" />
                        Delivered
                      </span>
                    ) : (
                      <span className="flex items-center gap-0.5 text-slate-500">
                        <Check className="w-3.5 h-3.5" />
                        Sent
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })
      )}

      {/* Typing indicator */}
      {typingUsers.length > 0 && (
        <div id="typing-indicator" className="flex items-center gap-2 text-xs text-blue-400 italic px-2 py-1 bg-blue-950/30 rounded-lg w-fit border border-blue-900/40">
          <div className="flex gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
          <span>
            {typingUsers.join(', ')} {typingUsers.length === 1 ? 'is' : 'are'} typing...
          </span>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};
