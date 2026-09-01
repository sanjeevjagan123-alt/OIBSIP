export interface User {
  id: number;
  username: string;
  created_at: string;
  isOnline?: boolean;
}

export interface Room {
  id: number;
  name: string;
  description?: string;
  created_by: number;
  created_at: string;
  member_count?: number;
  unreadCount?: number;
}

export interface Message {
  id: number;
  sender_id: number;
  sender_username: string;
  target_type: 'room' | 'user';
  target_id: string;
  content: string;
  delivery_state: 'sent' | 'delivered';
  timestamp: string;
}

export type TargetType = 'room' | 'user';

export interface ActiveTarget {
  type: TargetType;
  id: string; // room name or recipient username
  displayName: string;
  description?: string;
  isOnline?: boolean;
}
