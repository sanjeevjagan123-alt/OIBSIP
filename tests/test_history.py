"""Tests for Stage 9: Persistent message history (rooms and direct messages)."""

from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from client.core.client import ChatClient
from common.config_loader import AppConfig
from server.core.server import ChatServer


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.db_path = Path(cls.temp_dir.name) / "test_history.db"
        cls.config = AppConfig(host="127.0.0.1", port=8772, database_path=str(cls.db_path), log_level="DEBUG")
        import logging
        cls.logger = logging.getLogger("test_history")
        cls.logger.setLevel(logging.DEBUG)
        cls.server = ChatServer(config=cls.config, logger=cls.logger)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server_thread.join(timeout=2.0)
        cls.temp_dir.cleanup()

    def setUp(self) -> None:
        self.a = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        self.b = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        self.c = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        self.a.connect(); self.b.connect(); self.c.connect()
        self.a.start_listener(); self.b.start_listener(); self.c.start_listener()

    def tearDown(self) -> None:
        try:
            self.a.disconnect()
        finally:
            try:
                self.b.disconnect()
            finally:
                try:
                    self.c.disconnect()
                finally:
                    pass

    def test_room_history_and_ordering(self):
        self.a.register("hist_room_a", "Pass123")
        self.b.register("hist_room_b", "Pass123")
        self.a.login("hist_room_a", "Pass123")
        self.b.login("hist_room_b", "Pass123")

        # create and join a new room
        self.a.create_room("HistoryRoom")
        self.b.join_room("HistoryRoom")

        # send messages from both users
        self.a.send_chat_message("room", "HistoryRoom", "First message")
        time.sleep(0.05)
        self.b.send_chat_message("room", "HistoryRoom", "Second message")
        time.sleep(0.05)
        self.a.send_chat_message("room", "HistoryRoom", "Third message")
        time.sleep(0.2)

        # retrieve history and verify chronological order
        hist = self.a.get_history("room", "HistoryRoom", limit=50)
        self.assertEqual(hist.get("status"), "success")
        msgs = hist.get("payload", {}).get("messages", [])
        contents = [m.get("content") for m in msgs]
        self.assertEqual(contents, ["First message", "Second message", "Third message"])

    def test_direct_message_history_both_directions(self):
        self.a.register("hist_user_a", "Pass123")
        self.b.register("hist_user_b", "Pass123")
        self.a.login("hist_user_a", "Pass123")
        self.b.login("hist_user_b", "Pass123")

        # exchange DMs both directions
        self.a.send_chat_message("user", "hist_user_b", "Hi from A")
        time.sleep(0.05)
        self.b.send_chat_message("user", "hist_user_a", "Reply from B")
        time.sleep(0.05)
        self.a.send_chat_message("user", "hist_user_b", "Another from A")
        time.sleep(0.2)

        # retrieve conversation history from A's perspective
        hist_a = self.a.get_history("user", "hist_user_b", limit=50)
        self.assertEqual(hist_a.get("status"), "success")
        msgs_a = hist_a.get("payload", {}).get("messages", [])
        contents_a = [m.get("content") for m in msgs_a]
        self.assertEqual(contents_a, ["Hi from A", "Reply from B", "Another from A"]) 

        # retrieve conversation history from B's perspective, should be same
        hist_b = self.b.get_history("user", "hist_user_a", limit=50)
        msgs_b = hist_b.get("payload", {}).get("messages", [])
        contents_b = [m.get("content") for m in msgs_b]
        self.assertEqual(contents_b, contents_a)

    def test_private_access_control(self):
        # A and B exchange, C should not see their conversation
        self.a.register("pa_user_a", "Pass123")
        self.b.register("pa_user_b", "Pass123")
        self.c.register("pa_user_c", "Pass123")
        self.a.login("pa_user_a", "Pass123")
        self.b.login("pa_user_b", "Pass123")
        self.c.login("pa_user_c", "Pass123")

        self.a.send_chat_message("user", "pa_user_b", "Secret A->B")
        time.sleep(0.05)
        self.b.send_chat_message("user", "pa_user_a", "Secret B->A")
        time.sleep(0.2)

        # C requests history with B: should NOT include A<->B messages
        hist_c = self.c.get_history("user", "pa_user_b", limit=50)
        self.assertEqual(hist_c.get("status"), "success")
        msgs_c = hist_c.get("payload", {}).get("messages", [])
        contents_c = [m.get("content") for m in msgs_c]
        # C has not exchanged with B so should see empty list
        self.assertEqual(contents_c, [])

    def test_bounded_history_retrieval(self):
        self.a.register("bound_a", "Pass123")
        self.b.register("bound_b", "Pass123")
        self.a.login("bound_a", "Pass123")
        self.b.login("bound_b", "Pass123")

        # Send 10 messages to a room
        self.a.create_room("BoundRoom")
        for i in range(10):
            self.a.send_chat_message("room", "BoundRoom", f"m{i}")
            time.sleep(0.05)
        time.sleep(0.2)

        # Request only last 5 messages
        hist = self.a.get_history("room", "BoundRoom", limit=5)
        msgs = hist.get("payload", {}).get("messages", [])
        contents = [m.get("content") for m in msgs]
        self.assertEqual(len(contents), 5)
        # Ensure they are the most recent 5 in chronological order
        self.assertEqual(contents, [f"m{i}" for i in range(5, 10)])

    def test_persistence_across_reconnect(self):
        self.a.register("persist_a", "Pass123")
        self.b.register("persist_b", "Pass123")
        self.a.login("persist_a", "Pass123")
        self.b.login("persist_b", "Pass123")

        self.a.send_chat_message("user", "persist_b", "Persist msg")
        time.sleep(0.1)

        # disconnect and reconnect client A
        self.a.disconnect()
        time.sleep(0.05)
        self.a.connect(); self.a.start_listener()
        self.a.login("persist_a", "Pass123")

        hist = self.a.get_history("user", "persist_b", limit=50)
        msgs = hist.get("payload", {}).get("messages", [])
        contents = [m.get("content") for m in msgs]
        self.assertIn("Persist msg", contents)


if __name__ == "__main__":
    unittest.main()
