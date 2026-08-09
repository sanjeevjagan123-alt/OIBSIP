"""Unit tests for DatabaseManager SQLite operations."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from server.database.db import DatabaseManager


class DatabaseManagerTests(unittest.TestCase):
    """Verify SQLite table initialization, user creation, and lookups."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "test_chat.db"
        self.db = DatabaseManager(self.db_path)
        self.db.init_db()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_init_db_creates_tables(self) -> None:
        user = self.db.get_user_by_username("nonexistent")
        self.assertIsNone(user)

    def test_create_and_get_user(self) -> None:
        created = self.db.create_user("alice", "hash123", "salt456")
        self.assertEqual(created["username"], "alice")
        self.assertIn("id", created)

        fetched = self.db.get_user_by_username("alice")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["id"], created["id"])
        self.assertEqual(fetched["username"], "alice")
        self.assertEqual(fetched["password_hash"], "hash123")
        self.assertEqual(fetched["salt"], "salt456")

    def test_get_user_case_insensitive(self) -> None:
        self.db.create_user("Bob_Builder", "hash789", "salt789")
        fetched = self.db.get_user_by_username("bob_builder")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["username"], "Bob_Builder")

    def test_duplicate_username_raises_error(self) -> None:
        self.db.create_user("Charlie", "hash1", "salt1")
        with self.assertRaises(ValueError):
            self.db.create_user("charlie", "hash2", "salt2")


if __name__ == "__main__":
    unittest.main()
