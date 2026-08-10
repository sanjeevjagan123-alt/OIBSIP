"""Database concurrency test for Stage 10.

Use the real DatabaseManager APIs to concurrently insert messages and verify persistence.
"""

from __future__ import annotations

import threading
import time
import unittest

from server.database.db import DatabaseManager


class DBConcurrencyTests(unittest.TestCase):
    def test_concurrent_message_inserts(self) -> None:
        db_path = "data/test_stage10_db_concurrency.db"
        # Ensure fresh database for this test run
        from pathlib import Path

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            Path(db_path).unlink()
        except Exception:
            pass

        db = DatabaseManager(db_path)
        db.init_db()

        # Create users
        users = []
        for i in range(3):
            uname = f"db_user_{i}"
            try:
                u = db.create_user(uname, "hash", "salt")
            except ValueError:
                # If already exists, fetch
                u = db.get_user_by_username(uname)
            users.append(u)

        # Create room
        try:
            room = db.create_room("concurrent_room", created_by=users[0]["id"]) 
        except ValueError:
            room = db.get_room_by_name("concurrent_room")

        room_id = room["id"]

        num_threads = 5
        messages_per_thread = 20

        def worker(thread_idx: int) -> None:
            # Round-robin senders
            for m in range(messages_per_thread):
                sender = users[(thread_idx + m) % len(users)]
                db.save_message(sender_id=sender["id"], target_type="room", target_id=room_id, content=f"t{thread_idx}-m{m}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Allow SQLite finalize
        time.sleep(0.1)

        messages = db.get_messages("room", room_id, limit=10000)
        expected = num_threads * messages_per_thread
        self.assertEqual(len(messages), expected)
        # Check for a few sample messages
        contents = {m["content"] for m in messages}
        self.assertIn("t0-m0", contents)
        self.assertIn("t1-m0", contents)
        self.assertIn("t4-m19", contents)


if __name__ == "__main__":
    unittest.main()
