import { Message, Room, User } from '../types';

const API_BASE = '/api';

export async function registerUser(username: string, password: string): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || 'Registration failed');
  }
  return data;
}

export async function loginUser(username: string, password: string): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || 'Login failed');
  }
  return data;
}

export async function fetchUsers(): Promise<User[]> {
  const res = await fetch(`${API_BASE}/users`);
  if (!res.ok) throw new Error('Failed to fetch users');
  return res.json();
}

export async function fetchRooms(): Promise<Room[]> {
  const res = await fetch(`${API_BASE}/rooms`);
  if (!res.ok) throw new Error('Failed to fetch rooms');
  return res.json();
}

export async function createRoom(name: string, description: string, username: string): Promise<Room> {
  const res = await fetch(`${API_BASE}/rooms`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description, username }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || 'Failed to create room');
  }
  return data;
}

export async function fetchMessages(
  targetType: 'room' | 'user',
  targetId: string,
  currentUser: string
): Promise<Message[]> {
  const params = new URLSearchParams({
    target_type: targetType,
    target_id: targetId,
    current_user: currentUser,
  });
  const res = await fetch(`${API_BASE}/messages?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch message history');
  return res.json();
}

export async function searchMessages(
  q: string,
  targetType?: string,
  targetId?: string,
  currentUser?: string
): Promise<Message[]> {
  const params = new URLSearchParams({ q });
  if (targetType) params.append('target_type', targetType);
  if (targetId) params.append('target_id', targetId);
  if (currentUser) params.append('current_user', currentUser);

  const res = await fetch(`${API_BASE}/messages/search?${params.toString()}`);
  if (!res.ok) throw new Error('Search failed');
  return res.json();
}
