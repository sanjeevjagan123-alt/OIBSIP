"""SQLite Database Manager for user persistence."""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path
from typing import Any, Generator


class DatabaseManager:
    """Thread-safe SQLite database manager for user authentication data."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    @contextlib.contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager yielding an open connection and ensuring it closes afterwards."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self) -> None:
        """Initialize database schema and tables if they do not exist."""
        if self.db_path != Path(":memory:"):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS rooms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (created_by) REFERENCES users(id)
                );
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rooms_name ON rooms(name);")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS room_members (
                    room_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (room_id, user_id),
                    FOREIGN KEY (room_id) REFERENCES rooms(id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER NOT NULL,
                    target_type TEXT NOT NULL CHECK(target_type IN ('room', 'user')),
                    target_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sender_id) REFERENCES users(id)
                );
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_target ON messages(target_type, target_id, id DESC);")

            conn.commit()

    def create_user(self, username: str, password_hash: str, salt: str) -> dict[str, Any]:
        """Insert a new user into the database. Raise ValueError on duplicate username."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?);",
                    (username.strip(), password_hash, salt),
                )
                conn.commit()
                user_id = cursor.lastrowid
                return {
                    "id": user_id,
                    "username": username.strip(),
                }
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Username '{username}' already exists.") from exc

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """Retrieve user record by username (case-insensitive)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, password_hash, salt, created_at FROM users WHERE username = ?;",
                (username.strip(),),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return {
                "id": row["id"],
                "username": row["username"],
                "password_hash": row["password_hash"],
                "salt": row["salt"],
                "created_at": str(row["created_at"]),
            }

    def create_room(self, name: str, created_by: int | None = None) -> dict[str, Any]:
        """Create a new chat room."""
        clean_name = name.strip()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO rooms (name, created_by) VALUES (?, ?);",
                    (clean_name, created_by),
                )
                conn.commit()
                room_id = cursor.lastrowid
                return {"id": room_id, "name": clean_name}
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Room '{clean_name}' already exists.") from exc

    def get_room_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a room by name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, created_by, created_at FROM rooms WHERE name = ?;",
                (name.strip(),),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return {
                "id": row["id"],
                "name": row["name"],
                "created_by": row["created_by"],
                "created_at": str(row["created_at"]),
            }

    def list_rooms(self) -> list[dict[str, Any]]:
        """List all rooms with member counts."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT r.id, r.name, r.created_by, r.created_at, COUNT(rm.user_id) AS member_count
                FROM rooms r
                LEFT JOIN room_members rm ON r.id = rm.room_id
                GROUP BY r.id
                ORDER BY r.name COLLATE NOCASE;
                """
            )
            rows = cursor.fetchall()
            rooms = []
            for row in rows:
                rooms.append({
                    "id": row["id"],
                    "name": row["name"],
                    "created_by": row["created_by"],
                    "created_at": str(row["created_at"]),
                    "member_count": row["member_count"],
                })
            return rooms

    def get_room_members(self, room_id: int) -> list[dict[str, Any]]:
        """Return list of members (id, username) for a given room id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT u.id, u.username
                FROM room_members rm
                JOIN users u ON rm.user_id = u.id
                WHERE rm.room_id = ?
                ORDER BY u.username COLLATE NOCASE;
                """,
                (room_id,)
            )
            rows = cursor.fetchall()
            return [{"id": r["id"], "username": r["username"]} for r in rows]

    def join_room(self, room_id: int, user_id: int) -> None:
        """Add a user to a room."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO room_members (room_id, user_id) VALUES (?, ?);",
                (room_id, user_id),
            )
            conn.commit()

    def leave_room(self, room_id: int, user_id: int) -> None:
        """Remove a user from a room."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM room_members WHERE room_id = ? AND user_id = ?;",
                (room_id, user_id),
            )
            conn.commit()

    def save_message(self, sender_id: int, target_type: str, target_id: int, content: str) -> dict[str, Any]:
        """Save a chat message to the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO messages (sender_id, target_type, target_id, content) VALUES (?, ?, ?, ?);",
                (sender_id, target_type, target_id, content),
            )
            conn.commit()
            msg_id = cursor.lastrowid
            cursor.execute("SELECT timestamp FROM messages WHERE id = ?;", (msg_id,))
            row = cursor.fetchone()
            return {
                "id": msg_id,
                "sender_id": sender_id,
                "target_type": target_type,
                "target_id": target_id,
                "content": content,
                "timestamp": str(row["timestamp"]) if row else "",
            }

    def get_messages(self, target_type: str, target_id: int, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent messages for a room or user conversation.

        For rooms this returns messages where target_type='room' and target_id=room_id.
        For user conversations this returns messages where target_type='user' and
        (sender_id = target_id AND target_id = requester) OR (sender_id = requester AND target_id = target_id).
        Note: Use get_direct_messages_between for user-to-user conversations when requester identity is known.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT m.id, m.sender_id, u.username AS sender_username, m.target_type, m.target_id, m.content, m.timestamp
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.target_type = ? AND m.target_id = ?
                ORDER BY m.id DESC
                LIMIT ?;
                """,
                (target_type, target_id, limit),
            )
            rows = cursor.fetchall()
            messages = []
            for row in reversed(rows):
                messages.append({
                    "message_id": row["id"],
                    "sender_id": row["sender_id"],
                    "sender_username": row["sender_username"],
                    "target_type": row["target_type"],
                    "target_id": row["target_id"],
                    "content": row["content"],
                    "timestamp": str(row["timestamp"]),
                })
            return messages

    def get_direct_messages_between(self, user_a_id: int, user_b_id: int, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve messages exchanged between two users (both directions), ordered chronologically up to `limit`.

        Returns messages where target_type='user' and ((sender_id = user_a_id AND target_id = user_b_id)
        OR (sender_id = user_b_id AND target_id = user_a_id)).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT m.id, m.sender_id, u.username AS sender_username, m.target_type, m.target_id, m.content, m.timestamp
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.target_type = 'user' AND (
                    (m.sender_id = ? AND m.target_id = ?) OR (m.sender_id = ? AND m.target_id = ?)
                )
                ORDER BY m.id DESC
                LIMIT ?;
                """,
                (user_a_id, user_b_id, user_b_id, user_a_id, limit),
            )
            rows = cursor.fetchall()
            messages = []
            for row in reversed(rows):
                messages.append({
                    "message_id": row["id"],
                    "sender_id": row["sender_id"],
                    "sender_username": row["sender_username"],
                    "target_type": row["target_type"],
                    "target_id": row["target_id"],
                    "content": row["content"],
                    "timestamp": str(row["timestamp"]),
                })
            return messages

