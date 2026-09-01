import React, { useState, useRef, useEffect } from 'react';
import { Send, Smile, Sparkles } from 'lucide-react';
import { replaceEmojiShortcodes } from '../services/socket';

interface MessageInputProps {
  onSendMessage: (content: string) => void;
  onTyping: (isTyping: boolean) => void;
  onToggleEmojiPicker: () => void;
  isEmojiPickerOpen: boolean;
}

export const MessageInput: React.FC<MessageInputProps> = ({
  onSendMessage,
  onTyping,
  onToggleEmojiPicker,
  isEmojiPickerOpen,
}) => {
  const [text, setText] = useState('');
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    // Realtime shortcode transform on space or punctuation
    const transformed = replaceEmojiShortcodes(val);
    setText(transformed);

    // Typing throttle
    onTyping(true);
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
    typingTimeoutRef.current = setTimeout(() => {
      onTyping(false);
    }, 2000);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    if (!text.trim()) return;
    const finalContent = replaceEmojiShortcodes(text.trim());
    onSendMessage(finalContent);
    setText('');
    onTyping(false);
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
  };

  return (
    <div id="message-input-bar" className="p-4 bg-[#0d1527] border-t border-slate-800/80">
      <div className="flex items-center gap-2 bg-[#141f36] border border-slate-700/80 rounded-2xl px-3 py-2 focus-within:ring-2 focus-within:ring-blue-500/50 focus-within:border-blue-500 transition-all shadow-inner">
        {/* Emoji trigger */}
        <button
          id="btn-emoji-picker"
          type="button"
          onClick={onToggleEmojiPicker}
          title="Insert Emoji"
          className={`p-1.5 rounded-xl transition-colors cursor-pointer ${
            isEmojiPickerOpen ? 'bg-blue-600/20 text-blue-400' : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
          }`}
        >
          <Smile className="w-5 h-5" />
        </button>

        {/* Text Input */}
        <input
          id="message-text-input"
          type="text"
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Message... (try :smile: :fire: :heart: :rocket:)"
          className="flex-1 bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none px-2"
        />

        {/* Send Button */}
        <button
          id="btn-send-message"
          type="button"
          onClick={handleSend}
          disabled={!text.trim()}
          className="p-2 rounded-xl bg-blue-600 hover:bg-blue-500 active:bg-blue-700 disabled:opacity-30 disabled:hover:bg-blue-600 text-white transition-all shadow-md shadow-blue-600/20 cursor-pointer"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
      <div className="flex items-center justify-between mt-1.5 px-2 text-[10px] text-slate-500">
        <span>Press <kbd className="bg-slate-800 px-1 py-0.5 rounded text-slate-400 border border-slate-700">Enter</kbd> to send</span>
        <span>Supports shortcodes like <code>:smile:</code> <code>:fire:</code> <code>:thumbsup:</code></span>
      </div>
    </div>
  );
};
