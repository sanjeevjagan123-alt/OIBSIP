"""Tests for Stage 13 – Message Search and Typing Indicator.

These integration tests exercise the new ``ACTION_SEARCH_MESSAGES`` and ``ACTION_TYPING``
protocol actions, ensuring proper authorization, case‑insensitive search, limit handling,
and event broadcasting for both rooms and direct messages.
"""

from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from client.core.client import ChatClient
from common.config_loader import AppConfig
from common.protocol_constants import (
    ACTION_TYPING,
    EVENT_TYPING_UPDATE,
    EVENT_ERROR,
    ERROR_UNAUTHORIZED,
)
from server.core.server import ChatServer


class SearchAndTypingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Use a temporary directory for the SQLite DB
        cls.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.db_path = Path(cls.temp_dir.name) / "test_search_typing.db"
        # Use a high rate‑limit to avoid throttling in fast tests
        cls.config = AppConfig(
            host="127.0.0.1",
            port=8778,
            database_path=str(cls.db_path),
            rate_limit_per_second=1000,
            rate_limit_burst=1000,
        )
        import logging
        cls.logger = logging.getLogger("test_search_typing")
        cls.logger.setLevel(logging.DEBUG)
        cls.server = ChatServer(config=cls.config, logger=cls.logger)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        # Allow server to start up
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server_thread.join(timeout=2.0)
        cls.temp_dir.cleanup()

    def setUp(self) -> None:
        # Three clients for various scenarios
        self.a = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        self.b = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        self.c = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        for cl in (self.a, self.b, self.c):
            cl.connect()
            cl.start_listener()

    def tearDown(self) -> None:
        for cl in (self.a, self.b, self.c):
            try:
                cl.disconnect()
            except Exception:
                pass

    # ---------- Helper utilities ----------
    def _register_and_login(self, client: ChatClient, username: str) -> None:
        client.register(username, "Pass123")
        client.login(username, "Pass123")

    # ---------- Tests ----------
    def test_room_message_search(self) -> None:
        self._register_and_login(self.a, "search_user_a")
        self._register_and_login(self.b, "search_user_b")

        # Create and join a room
        self.a.create_room("SearchRoom")
        self.b.join_room("SearchRoom")
        time.sleep(0.05)  # allow join to propagate

        # Send messages with varying content
        self.a.send_chat_message("room", "SearchRoom", "First message")
        time.sleep(0.05)
        self.b.send_chat_message("room", "SearchRoom", "search test")
        time.sleep(0.05)
        self.a.send_chat_message("room", "SearchRoom", "Searchable content")
        time.sleep(0.2)

        # Search for the substring "search"
        resp = self.a.search_messages("room", "SearchRoom", "search", limit=10)
        self.assertEqual(resp.get("status"), "success")
        msgs = resp.get("payload", {}).get("messages", [])
        # Expect two matching messages ordered chronologically
        contents = [m.get("content") for m in msgs]
        self.assertEqual(contents, ["search test", "Searchable content"])

    def test_dm_message_search_both_directions(self) -> None:
        self._register_and_login(self.a, "dm_user_a")
        self._register_and_login(self.b, "dm_user_b")

        # Exchange direct messages
        self.a.send_chat_message("user", "dm_user_b", "Alpha")
        time.sleep(0.05)
        self.b.send_chat_message("user", "dm_user_a", "Beta")
        time.sleep(0.05)
        self.a.send_chat_message("user", "dm_user_b", "Gamma")
        time.sleep(0.2)

        # Search for substring "a" (case‑insensitive) – should match all three
        resp = self.a.search_messages("user", "dm_user_b", "a", limit=10)
        self.assertEqual(resp.get("status"), "success")
        msgs = resp.get("payload", {}).get("messages", [])
        contents = [m.get("content") for m in msgs]
        self.assertEqual(contents, ["Alpha", "Beta", "Gamma"])

    def test_case_insensitive_search(self) -> None:
        self._register_and_login(self.a, "case_user_a")
        self._register_and_login(self.b, "case_user_b")
        self.a.create_room("CaseRoom")
        self.b.join_room("CaseRoom")
        time.sleep(0.05)
        self.a.send_chat_message("room", "CaseRoom", "MiXeD CaSe TeSt")
        time.sleep(0.2)
        resp = self.b.search_messages("room", "CaseRoom", "case", limit=5)
        self.assertEqual(resp.get("status"), "success")
        msgs = resp.get("payload", {}).get("messages", [])
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].get("content"), "MiXeD CaSe TeSt")

    def test_search_authorization(self) -> None:
        # A and B exchange DMs, C attempts to search
        self._register_and_login(self.a, "auth_user_a")
        self._register_and_login(self.b, "auth_user_b")
        self._register_and_login(self.c, "auth_user_c")
        self.a.send_chat_message("user", "auth_user_b", "Secret A->B")
        time.sleep(0.05)
        self.b.send_chat_message("user", "auth_user_a", "Secret B->A")
        time.sleep(0.2)

        # C searches the conversation between A and B – should receive empty list
        resp = self.c.search_messages("user", "auth_user_b", "secret", limit=10)
        self.assertEqual(resp.get("status"), "success")
        msgs = resp.get("payload", {}).get("messages", [])
        self.assertEqual(msgs, [])

        # Test room‑level authorization: C is not a member of the room
        self.a.create_room("SecretRoom")
        self.b.join_room("SecretRoom")
        time.sleep(0.05)
        self.a.send_chat_message("room", "SecretRoom", "Room secret")
        time.sleep(0.2)
        resp2 = self.c.search_messages("room", "SecretRoom", "secret", limit=10)
        self.assertEqual(resp2.get("status"), "success")
        msgs2 = resp2.get("payload", {}).get("messages", [])
        # C is not a member, should see no messages
        self.assertEqual(msgs2, [])

    def test_search_limit_and_invalid_input(self) -> None:
        self._register_and_login(self.a, "limit_user_a")
        self._register_and_login(self.b, "limit_user_b")
        self.a.create_room("LimitRoom")
        self.b.join_room("LimitRoom")
        for i in range(8):
            self.a.send_chat_message("room", "LimitRoom", f"msg{i}")
            time.sleep(0.01)
        time.sleep(0.2)
        # Request only last 5 messages
        resp = self.a.search_messages("room", "LimitRoom", "msg", limit=5)
        self.assertEqual(resp.get("status"), "success")
        msgs = resp.get("payload", {}).get("messages", [])
        self.assertEqual(len(msgs), 5)
        self.assertEqual([m.get("content") for m in msgs], [f"msg{i}" for i in range(3, 8)])
        # Invalid limit – negative -> defaults to 50
        resp2 = self.a.search_messages("room", "LimitRoom", "msg", limit=-1)
        self.assertEqual(resp2.get("status"), "success")

    def test_typing_indicator_room(self) -> None:
        self._register_and_login(self.a, "typing_user_a")
        self._register_and_login(self.b, "typing_user_b")
        self.a.create_room("TypingRoom")
        self.b.join_room("TypingRoom")
        time.sleep(0.05)
        events: list[dict] = []

        def capture(frame: dict) -> None:
            if frame.get("event") == EVENT_TYPING_UPDATE:
                events.append(frame)

        self.b.add_event_callback(capture)
        # User A starts typing, then stops
        self.a.send_typing("room", "TypingRoom", True)
        time.sleep(0.1)
        self.a.send_typing("room", "TypingRoom", False)
        time.sleep(0.1)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["payload"]["username"], "typing_user_a")
        self.assertTrue(events[0]["payload"]["is_typing"])
        self.assertFalse(events[1]["payload"]["is_typing"])

    def test_typing_indicator_dm(self) -> None:
        self._register_and_login(self.a, "dm_typing_a")
        self._register_and_login(self.b, "dm_typing_b")
        events: list[dict] = []

        def capture(frame: dict) -> None:
            if frame.get("event") == EVENT_TYPING_UPDATE:
                events.append(frame)

        self.b.add_event_callback(capture)
        self.a.send_typing("user", "dm_typing_b", True)
        time.sleep(0.1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["username"], "dm_typing_a")
        self.assertTrue(events[0]["payload"]["is_typing"])

    def test_unauthenticated_typing_and_search(self) -> None:
        # Connect client without login
        client = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        client.connect()
        client.start_listener()
        # Typing should be rejected
        resp = client.send_typing("room", "general", True)
        self.assertEqual(resp.get("event"), EVENT_ERROR)
        self.assertEqual(resp.get("error_code"), ERROR_UNAUTHORIZED)
        # Search should be rejected
        resp2 = client.search_messages("room", "general", "test", limit=5)
        self.assertEqual(resp2.get("event"), EVENT_ERROR)
        self.assertEqual(resp2.get("error_code"), ERROR_UNAUTHORIZED)
        client.disconnect()


if __name__ == "__main__":
    unittest.main()