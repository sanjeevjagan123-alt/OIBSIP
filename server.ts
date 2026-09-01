import express from 'express';
import http from 'http';
import { Server as SocketIOServer } from 'socket.io';
import cors from 'cors';
import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = 3000;
const HOST = '0.0.0.0';
const DATA_DIR = path.join(__dirname, 'data');
const DB_FILE = path.join(DATA_DIR, 'chat_app_db.json');

// Ensure data directory exists
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

// Database Interfaces
export interface UserRecord {
  id: number;
  username: string;
  password_hash: string;
  salt: string;
  created_at: string;
}

export interface RoomRecord {
  id: number;
  name: string;
  description?: string;
  created_by: number;
  created_at: string;
}

export interface MessageRecord {
  id: number;
  sender_id: number;
  sender_username: string;
  target_type: 'room' | 'user';
  target_id: string; // room name or recipient username
  content: string;
  delivery_state: 'sent' | 'delivered';
  timestamp: string;
}

interface DatabaseSchema {
  users: UserRecord[];
  rooms: RoomRecord[];
  room_members: { room_name: string; username: string; joined_at: string }[];
  messages: MessageRecord[];
  nextUserId: number;
  nextRoomId: number;
  nextMessageId: number;
}

// Initialize / Load Database
function loadDb(): DatabaseSchema {
  if (fs.existsSync(DB_FILE)) {
    try {
      const data = fs.readFileSync(DB_FILE, 'utf-8');
      return JSON.parse(data);
    } catch (e) {
      console.error('Error loading DB file, resetting to default:', e);
    }
  }

  // Initial default seed
  const defaultDb: DatabaseSchema = {
    users: [],
    rooms: [
      { id: 1, name: 'general', description: 'General Oasis discussion and welcome hub', created_by: 0, created_at: new Date().toISOString() },
      { id: 2, name: 'announcements', description: 'Important updates and news', created_by: 0, created_at: new Date().toISOString() },
      { id: 3, name: 'dev-chat', description: 'Engineering, code discussions and technical chat', created_by: 0, created_at: new Date().toISOString() },
      { id: 4, name: 'oasis-lounge', description: 'Casual hangout, emojis and fun', created_by: 0, created_at: new Date().toISOString() }
    ],
    room_members: [],
    messages: [
      {
        id: 1,
        sender_id: 0,
        sender_username: 'System',
        target_type: 'room',
        target_id: 'general',
        content: 'Welcome to Oasis Chat Application! 🌴 Feel free to create an account, join rooms, direct message friends, and chat in real time.',
        delivery_state: 'delivered',
        timestamp: new Date(Date.now() - 3600000).toISOString()
      },
      {
        id: 2,
        sender_id: 0,
        sender_username: 'System',
        target_type: 'room',
        target_id: 'announcements',
        content: '🚀 Oasis Chat is live with real-time socket communication, typing indicators, delivery receipts, and full message history search!',
        delivery_state: 'delivered',
        timestamp: new Date(Date.now() - 1800000).toISOString()
      }
    ],
    nextUserId: 1,
    nextRoomId: 5,
    nextMessageId: 3
  };

  saveDb(defaultDb);
  return defaultDb;
}

let db = loadDb();

function saveDb(dataToSave: DatabaseSchema = db) {
  try {
    fs.writeFileSync(DB_FILE, JSON.stringify(dataToSave, null, 2), 'utf-8');
  } catch (e) {
    console.error('Failed to save DB:', e);
  }
}

// Password hashing matching PBKDF2-HMAC-SHA256 (100,000 iterations)
function hashPassword(password: string, salt?: string): { hash: string; salt: string } {
  const finalSalt = salt || crypto.randomBytes(16).toString('hex');
  const hash = crypto.pbkdf2Sync(password, finalSalt, 100000, 32, 'sha256').toString('hex');
  return { hash, salt: finalSalt };
}

function verifyPassword(password: string, hash: string, salt: string): boolean {
  const computed = crypto.pbkdf2Sync(password, salt, 100000, 32, 'sha256').toString('hex');
  return crypto.timingSafeEqual(Buffer.from(computed, 'hex'), Buffer.from(hash, 'hex'));
}

// Online Socket / Presence tracking
interface OnlineClient {
  socketId: string;
  userId: number;
  username: string;
  activeTarget: { type: 'room' | 'user'; id: string } | null;
}

const onlineUsers = new Map<string, OnlineClient>(); // key: socketId
const userSocketMap = new Map<string, Set<string>>(); // key: lowercase username -> Set of socketIds

// Express app setup
const app = express();
const server = http.createServer(app);
const io = new SocketIOServer(server, {
  cors: { origin: '*' }
});

app.use(cors());
app.use(express.json());

// API Routes
// 1. Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', time: new Date().toISOString() });
});

// 2. Auth: Register
app.post('/api/auth/register', (req, res) => {
  const { username, password } = req.body;
  if (!username || typeof username !== 'string' || username.trim().length < 2) {
    return res.status(400).json({ error: 'Username must be at least 2 characters.' });
  }
  if (!password || typeof password !== 'string' || password.length < 3) {
    return res.status(400).json({ error: 'Password must be at least 3 characters.' });
  }

  const cleanUsername = username.trim();
  const existing = db.users.find(u => u.username.toLowerCase() === cleanUsername.toLowerCase());
  if (existing) {
    return res.status(409).json({ error: `Username '${cleanUsername}' is already taken.` });
  }

  const { hash, salt } = hashPassword(password);
  const newUser: UserRecord = {
    id: db.nextUserId++,
    username: cleanUsername,
    password_hash: hash,
    salt: salt,
    created_at: new Date().toISOString()
  };

  db.users.push(newUser);

  // Auto-join default rooms
  for (const r of db.rooms) {
    db.room_members.push({
      room_name: r.name,
      username: cleanUsername,
      joined_at: new Date().toISOString()
    });
  }

  saveDb();

  return res.status(201).json({
    id: newUser.id,
    username: newUser.username,
    created_at: newUser.created_at
  });
});

// 3. Auth: Login
app.post('/api/auth/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password are required.' });
  }

  const cleanUsername = username.trim();
  const user = db.users.find(u => u.username.toLowerCase() === cleanUsername.toLowerCase());
  if (!user) {
    return res.status(401).json({ error: 'Invalid username or password.' });
  }

  const isValid = verifyPassword(password, user.password_hash, user.salt);
  if (!isValid) {
    return res.status(401).json({ error: 'Invalid username or password.' });
  }

  return res.json({
    id: user.id,
    username: user.username,
    created_at: user.created_at
  });
});

// 4. Users list
app.get('/api/users', (req, res) => {
  const users = db.users.map(u => ({
    id: u.id,
    username: u.username,
    created_at: u.created_at,
    isOnline: userSocketMap.has(u.username.toLowerCase()) && (userSocketMap.get(u.username.toLowerCase())?.size ?? 0) > 0
  }));
  res.json(users);
});

// 5. Rooms: List
app.get('/api/rooms', (req, res) => {
  const roomsWithCounts = db.rooms.map(r => {
    const memberCount = db.room_members.filter(m => m.room_name.toLowerCase() === r.name.toLowerCase()).length;
    return {
      ...r,
      member_count: Math.max(memberCount, 1)
    };
  });
  res.json(roomsWithCounts);
});

// 6. Rooms: Create
app.post('/api/rooms', (req, res) => {
  const { name, description, username } = req.body;
  if (!name || typeof name !== 'string' || name.trim().length < 2) {
    return res.status(400).json({ error: 'Room name must be at least 2 characters.' });
  }

  const cleanName = name.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '-');
  const existing = db.rooms.find(r => r.name.toLowerCase() === cleanName);
  if (existing) {
    return res.status(409).json({ error: `Room '#${cleanName}' already exists.` });
  }

  const creator = db.users.find(u => u.username.toLowerCase() === (username || '').toLowerCase());
  const newRoom: RoomRecord = {
    id: db.nextRoomId++,
    name: cleanName,
    description: (description || '').trim() || `Channel for #${cleanName}`,
    created_by: creator ? creator.id : 0,
    created_at: new Date().toISOString()
  };

  db.rooms.push(newRoom);
  if (username) {
    db.room_members.push({
      room_name: cleanName,
      username: username.trim(),
      joined_at: new Date().toISOString()
    });
  }
  saveDb();

  io.emit('room_update', { action: 'created', room: newRoom });

  return res.status(201).json(newRoom);
});

// 7. Messages: History
app.get('/api/messages', (req, res) => {
  const { target_type, target_id, current_user } = req.query;

  if (!target_type || !target_id) {
    return res.status(400).json({ error: 'target_type and target_id are required.' });
  }

  const tType = target_type as 'room' | 'user';
  const tId = (target_id as string).trim();
  const cUser = (current_user as string || '').trim();

  let filtered: MessageRecord[] = [];

  if (tType === 'room') {
    filtered = db.messages.filter(
      m => m.target_type === 'room' && m.target_id.toLowerCase() === tId.toLowerCase()
    );
  } else if (tType === 'user') {
    // Direct message: between current_user and target_id
    filtered = db.messages.filter(m => {
      if (m.target_type !== 'user') return false;
      const isFromMeToThem = m.sender_username.toLowerCase() === cUser.toLowerCase() && m.target_id.toLowerCase() === tId.toLowerCase();
      const isFromThemToMe = m.sender_username.toLowerCase() === tId.toLowerCase() && m.target_id.toLowerCase() === cUser.toLowerCase();
      return isFromMeToThem || isFromThemToMe;
    });
  }

  res.json(filtered.slice(-100)); // last 100 messages
});

// 8. Messages: Search
app.get('/api/messages/search', (req, res) => {
  const { q, target_type, target_id, current_user } = req.query;
  const query = (q as string || '').toLowerCase().trim();

  if (!query) {
    return res.json([]);
  }

  const tType = target_type as string | undefined;
  const tId = (target_id as string || '').toLowerCase().trim();
  const cUser = (current_user as string || '').toLowerCase().trim();

  const results = db.messages.filter(m => {
    const matchContent = m.content.toLowerCase().includes(query) || m.sender_username.toLowerCase().includes(query);
    if (!matchContent) return false;

    if (tType === 'room' && tId) {
      return m.target_type === 'room' && m.target_id.toLowerCase() === tId;
    }
    if (tType === 'user' && tId && cUser) {
      if (m.target_type !== 'user') return false;
      const isFromMeToThem = m.sender_username.toLowerCase() === cUser && m.target_id.toLowerCase() === tId;
      const isFromThemToMe = m.sender_username.toLowerCase() === tId && m.target_id.toLowerCase() === cUser;
      return isFromMeToThem || isFromThemToMe;
    }

    // Global search for user accessible messages
    if (m.target_type === 'room') return true;
    if (m.target_type === 'user' && cUser) {
      return m.sender_username.toLowerCase() === cUser || m.target_id.toLowerCase() === cUser;
    }
    return false;
  });

  res.json(results.slice(-50));
});

// Broadcast online presence helper
function broadcastPresence() {
  const onlineList = Array.from(new Set(Array.from(onlineUsers.values()).map(u => u.username)));
  io.emit('presence_update', { online_users: onlineList });
}

// Socket.IO Real-Time Handlers
io.on('connection', (socket) => {
  // 1. Authenticate / Identify socket
  socket.on('authenticate', (data: { username: string; userId?: number }) => {
    const { username } = data;
    if (!username) return;

    const cleanUsername = username.trim();
    const user = db.users.find(u => u.username.toLowerCase() === cleanUsername.toLowerCase());

    const client: OnlineClient = {
      socketId: socket.id,
      userId: user ? user.id : 0,
      username: cleanUsername,
      activeTarget: null
    };

    onlineUsers.set(socket.id, client);

    const userKey = cleanUsername.toLowerCase();
    if (!userSocketMap.has(userKey)) {
      userSocketMap.set(userKey, new Set());
    }
    userSocketMap.get(userKey)!.add(socket.id);

    // Join all default rooms by default
    db.rooms.forEach(r => {
      socket.join(`room:${r.name.toLowerCase()}`);
    });

    broadcastPresence();

    socket.emit('authenticated', {
      success: true,
      username: cleanUsername,
      online_users: Array.from(new Set(Array.from(onlineUsers.values()).map(u => u.username)))
    });
  });

  // 2. Room Switch / Target Focus
  socket.on('set_active_target', (data: { target_type: 'room' | 'user'; target_id: string }) => {
    const client = onlineUsers.get(socket.id);
    if (client) {
      client.activeTarget = data;
      if (data.target_type === 'room') {
        socket.join(`room:${data.target_id.toLowerCase()}`);
      }
    }
  });

  // 3. Send Message
  socket.on('send_message', (payload: {
    sender_username: string;
    target_type: 'room' | 'user';
    target_id: string;
    content: string;
  }) => {
    const { sender_username, target_type, target_id, content } = payload;
    if (!sender_username || !content || !content.trim()) return;

    const sender = db.users.find(u => u.username.toLowerCase() === sender_username.toLowerCase());
    const senderId = sender ? sender.id : 0;
    const cleanContent = content.trim().slice(0, 4096);

    // Check if direct recipient is online to determine delivery state
    let deliveryState: 'sent' | 'delivered' = 'sent';
    if (target_type === 'room') {
      deliveryState = 'delivered';
    } else {
      const recipientSockets = userSocketMap.get(target_id.toLowerCase());
      if (recipientSockets && recipientSockets.size > 0) {
        deliveryState = 'delivered';
      }
    }

    const newMessage: MessageRecord = {
      id: db.nextMessageId++,
      sender_id: senderId,
      sender_username: sender ? sender.username : sender_username,
      target_type,
      target_id: target_id.trim(),
      content: cleanContent,
      delivery_state: deliveryState,
      timestamp: new Date().toISOString()
    };

    db.messages.push(newMessage);
    saveDb();

    if (target_type === 'room') {
      // Broadcast to room channel
      io.to(`room:${target_id.toLowerCase()}`).emit('new_message', newMessage);
    } else {
      // Direct message: send to all recipient sockets AND sender sockets
      const recipientSockets = userSocketMap.get(target_id.toLowerCase());
      if (recipientSockets) {
        recipientSockets.forEach(sId => {
          io.to(sId).emit('new_message', newMessage);
        });
      }

      const senderSockets = userSocketMap.get(sender_username.toLowerCase());
      if (senderSockets) {
        senderSockets.forEach(sId => {
          io.to(sId).emit('new_message', newMessage);
        });
      }
    }
  });

  // 4. Typing indicators
  socket.on('typing', (data: {
    sender_username: string;
    target_type: 'room' | 'user';
    target_id: string;
    is_typing: boolean;
  }) => {
    const { sender_username, target_type, target_id, is_typing } = data;

    if (target_type === 'room') {
      socket.to(`room:${target_id.toLowerCase()}`).emit('typing_update', {
        sender_username,
        target_type,
        target_id,
        is_typing
      });
    } else {
      const recipientSockets = userSocketMap.get(target_id.toLowerCase());
      if (recipientSockets) {
        recipientSockets.forEach(sId => {
          io.to(sId).emit('typing_update', {
            sender_username,
            target_type,
            target_id,
            is_typing
          });
        });
      }
    }
  });

  // 5. Message Delivered / Read Acknowledgment
  socket.on('mark_delivered', (data: { message_ids: number[] }) => {
    if (!data.message_ids || !Array.isArray(data.message_ids)) return;

    let updated = false;
    data.message_ids.forEach(mId => {
      const msg = db.messages.find(m => m.id === mId);
      if (msg && msg.delivery_state === 'sent') {
        msg.delivery_state = 'delivered';
        updated = true;
      }
    });

    if (updated) {
      saveDb();
      io.emit('delivery_update', { message_ids: data.message_ids, state: 'delivered' });
    }
  });

  // 6. Disconnect
  socket.on('disconnect', () => {
    const client = onlineUsers.get(socket.id);
    if (client) {
      const userKey = client.username.toLowerCase();
      const sockets = userSocketMap.get(userKey);
      if (sockets) {
        sockets.delete(socket.id);
        if (sockets.size === 0) {
          userSocketMap.delete(userKey);
        }
      }
      onlineUsers.delete(socket.id);
      broadcastPresence();
    }
  });
});

// Start Server & Vite Integration
async function startServer() {
  const isProduction = process.env.NODE_ENV === 'production';

  if (!isProduction) {
    // Development mode: Vite middleware
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true, hmr: false }
    });
    app.use(vite.middlewares);
  } else {
    // Production mode: Serve built dist files
    const distPath = path.join(__dirname, 'dist');
    if (fs.existsSync(distPath)) {
      app.use(express.static(distPath));
      app.get('*', (req, res) => {
        res.sendFile(path.join(distPath, 'index.html'));
      });
    }
  }

  server.listen(PORT, HOST, () => {
    console.log(`🌴 Oasis Chat Server running at http://${HOST}:${PORT}`);
  });
}

startServer().catch(err => {
  console.error('Failed to start Oasis server:', err);
  process.exit(1);
});
