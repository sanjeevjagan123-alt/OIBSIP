"""Thread-safe registry mapping active user sessions to ClientHandler instances."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.core.client_handler import ClientHandler


class ClientRegistry:
    """Registry maintaining active connected client handlers indexed by user ID."""

    def __init__(self) -> None:
        self._clients_by_id: dict[int, ClientHandler] = {}
        self._lock = threading.RLock()

    def register_client(self, user_id: int, handler: ClientHandler) -> None:
        """Register an active authenticated user session."""
        with self._lock:
            self._clients_by_id[user_id] = handler

    def unregister_client(self, user_id: int) -> None:
        """Remove a user session upon disconnect."""
        with self._lock:
            self._clients_by_id.pop(user_id, None)

    def get_client(self, user_id: int) -> ClientHandler | None:
        """Retrieve client handler by user ID."""
        with self._lock:
            return self._clients_by_id.get(user_id)

    def get_client_by_username(self, username: str) -> ClientHandler | None:
        """Retrieve client handler by username (case-insensitive)."""
        clean_user = username.strip().lower()
        with self._lock:
            for handler in self._clients_by_id.values():
                if handler.authenticated_user and handler.authenticated_user.get("username", "").lower() == clean_user:
                    return handler
        return None

    def get_all_clients(self) -> list[ClientHandler]:
        """Return a thread-safe snapshot of all active client handlers."""
        with self._lock:
            return list(self._clients_by_id.values())
