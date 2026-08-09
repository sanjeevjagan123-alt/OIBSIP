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
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);"
            )
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
