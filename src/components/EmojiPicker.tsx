import React from 'react';
import { EMOJI_MAP } from '../services/socket';

interface EmojiPickerProps {
  onSelectEmoji: (emoji: string) => void;
  onClose: () => void;
}

const COMMON_EMOJIS = [
  '😊', '😂', '😆', '😍', '😎', '🥳', '🤔', '😭', '🔥', '👍',
  '👎', '❤️', '👏', '🎉', '🚀', '✨', '💯', '👋', '👀', '⭐',
  '✅', '🌴', '🤝', '⚡', '☕', '💡', '🏆', '🎯', '🎈', '🍕'
];

export const EmojiPicker: React.FC<EmojiPickerProps> = ({ onSelectEmoji, onClose }) => {
  return (
    <div
      id="emoji-picker-dropdown"
      className="absolute bottom-20 left-4 z-50 w-72 bg-[#111a2e] border border-slate-700/80 rounded-2xl p-3 shadow-2xl backdrop-blur-xl"
    >
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800 text-xs font-semibold text-slate-300">
        <span>Emoji Picker & Shortcodes</span>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-white text-xs px-1 cursor-pointer"
        >
          ✕
        </button>
      </div>

      <div className="grid grid-cols-6 gap-1.5 mb-3 max-h-40 overflow-y-auto">
        {COMMON_EMOJIS.map((emoji, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => onSelectEmoji(emoji)}
            className="w-9 h-9 flex items-center justify-center text-lg hover:bg-slate-800 rounded-xl transition-transform hover:scale-110 cursor-pointer"
          >
            {emoji}
          </button>
        ))}
      </div>

      <div className="pt-2 border-t border-slate-800/80">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
          Popular Shortcodes
        </p>
        <div className="grid grid-cols-2 gap-1 text-[11px] text-slate-400">
          {Object.entries(EMOJI_MAP).slice(0, 8).map(([code, emoji]) => (
            <div
              key={code}
              onClick={() => onSelectEmoji(emoji)}
              className="flex items-center justify-between px-1.5 py-1 rounded-lg hover:bg-slate-800/80 cursor-pointer"
            >
              <span className="font-mono text-blue-400 text-[10px]">{code}</span>
              <span>{emoji}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
