"""Unit tests for RoomManager behavior."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
import logging
from pathlib import Path

from server.database.db import DatabaseManager
from server.logic.client_registry import ClientRegistry
from server.logic.rooms import RoomManager


class RoomManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "test_rooms.db"
        self.db = DatabaseManager(self.db_path)
        self.db.init_db()
        self.registry = ClientRegistry()
        self.logger = logging.getLogger("test_rooms")
        self.logger.addHandler(logging.NullHandler())
        self.rm = RoomManager(db=self.db, client_registry=self.registry, logger=self.logger)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_init_default_room_creates_general(self) -> None:
        self.rm.init_default_room("general")
        room = self.db.get_room_by_name("general")
        self.assertIsNotNone(room)
        self.assertIn("general", self.rm._rooms)

    def test_create_join_leave_room_updates_db_and_memory(self) -> None:
        created = self.rm.create_room("TestRoom", created_by=None)
        self.assertEqual(created["name"], "TestRoom")

        # create a user record to join
        user = self.db.create_user("user1", "hash", "salt")
        user_id = user["id"]

        # join room
        self.rm.join_room("TestRoom", user_id)
        self.assertIn(user_id, self.rm._rooms["testroom"])

        # verify DB row exists
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM room_members rm JOIN rooms r ON rm.room_id=r.id WHERE r.name=? AND rm.user_id=?;", ("TestRoom", user_id))
        row = cur.fetchone()
        conn.close()
        self.assertIsNotNone(row)

        # leave room
        self.rm.leave_room("TestRoom", user_id)
        self.assertNotIn(user_id, self.rm._rooms.get("testroom", set()))


if __name__ == "__main__":
    unittest.main()
