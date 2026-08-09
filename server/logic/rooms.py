"""Thread-safe room manager for chat channels and message broadcasting."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from client.core.protocol import send_frame

if TYPE_CHECKING:
    from server.database.db import DatabaseManager
    from server.logic.client_registry import ClientRegistry


class RoomManager:
    """Manages chat room states, memberships, and message broadcasting."""

    def __init__(self, db: DatabaseManager, client_registry: ClientRegistry, logger: logging.Logger) -> None:
        self.db = db
        self.client_registry = client_registry
        self.logger = logger
        self._rooms: dict[str, set[int]] = {}
        self._lock = threading.RLock()

    def get_rooms(self) -> list[dict[str, Any]]:
        """Return available rooms and member counts."""
        # Prefer DB definitive list, but augment with in-memory counts when available
        rooms = self.db.list_rooms()
        with self._lock:
            updated = []
            for r in rooms:
                name_key = r["name"].lower()
                member_set = self._rooms.get(name_key)
                if member_set is not None:
                    r = dict(r)
                    r["member_count"] = max(r.get("member_count", 0), len(member_set))
                updated.append(r)
            return updated

    def init_default_room(self, default_name: str = "general") -> None:
        """Ensure the default public room exists in database and memory."""
        with self._lock:
            room = self.db.get_room_by_name(default_name)
            if room is None:
                room = self.db.create_room(default_name, created_by=None)
            room_name = room["name"].lower()
            if room_name not in self._rooms:
                self._rooms[room_name] = set()

    def create_room(self, name: str, created_by: int) -> dict[str, Any]:
        """Create a new room in DB and initialize in-memory membership."""
        clean_name = name.strip().lower()
        with self._lock:
            room = self.db.create_room(name, created_by=created_by)
            if clean_name not in self._rooms:
                self._rooms[clean_name] = set()
            return room

    def join_room(self, room_name: str, user_id: int) -> dict[str, Any]:
        """Add a user to a room in DB and memory."""
        clean_name = room_name.strip().lower()
        with self._lock:
            room = self.db.get_room_by_name(clean_name)
            if room is None:
                raise ValueError(f"Room '{room_name}' does not exist.")
            self.db.join_room(room["id"], user_id)
            if clean_name not in self._rooms:
                self._rooms[clean_name] = set()
            self._rooms[clean_name].add(user_id)
            return room

    def leave_room(self, room_name: str, user_id: int) -> None:
        """Remove a user from a room in DB and memory."""
        clean_name = room_name.strip().lower()
        with self._lock:
            room = self.db.get_room_by_name(clean_name)
            if room is not None:
                self.db.leave_room(room["id"], user_id)
            if clean_name in self._rooms:
                self._rooms[clean_name].discard(user_id)

    def remove_user_from_all_rooms(self, user_id: int) -> None:
        """Unregister user from all in-memory rooms on disconnect."""
        with self._lock:
            for member_set in self._rooms.values():
                member_set.discard(user_id)

    def broadcast_to_room(
        self,
        room_name: str,
        message_frame: dict[str, Any],
        exclude_user_id: int | None = None,
    ) -> None:
        """Broadcast a message frame to all connected members of a room. Socket writes occur OUTSIDE the lock."""
        clean_name = room_name.strip().lower()
        target_handlers = []

        with self._lock:
            member_ids = set(self._rooms.get(clean_name, set()))
            if exclude_user_id is not None:
                member_ids.discard(exclude_user_id)

            for uid in member_ids:
                handler = self.client_registry.get_client(uid)
                if handler is not None:
                    target_handlers.append(handler)

        # Transmit frame over sockets outside of lock section
        for handler in target_handlers:
            try:
                send_frame(handler.client_socket, message_frame)
            except (OSError, ConnectionError) as exc:
                self.logger.warning("Failed to broadcast message to client: %s", exc)
