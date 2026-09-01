import { io, Socket } from 'socket.io-client';

let socket: Socket | null = null;

export function getSocket(): Socket {
  if (!socket) {
    socket = io('/', {
      transports: ['websocket', 'polling'],
      autoConnect: true,
    });
  }
  return socket;
}

export const EMOJI_MAP: Record<string, string> = {
  ':smile:': '😊',
  ':laughing:': '😆',
  ':heart:': '❤️',
  ':thumbsup:': '👍',
  ':thumbsdown:': '👎',
  ':sad:': '😢',
  ':wink:': '😉',
  ':fire:': '🔥',
  ':clap:': '👏',
  ':thinking:': '🤔',
  ':rocket:': '🚀',
  ':tada:': '🎉',
  ':sparkles:': '✨',
  ':100:': '💯',
  ':wave:': '👋',
  ':eyes:': '👀',
  ':cool:': '😎',
  ':star:': '⭐',
  ':check:': '✅',
  ':palm_tree:': '🌴',
};

export function replaceEmojiShortcodes(text: string): string {
  let result = text;
  for (const [code, emoji] of Object.entries(EMOJI_MAP)) {
    result = result.split(code).join(emoji);
  }
  return result;
}
