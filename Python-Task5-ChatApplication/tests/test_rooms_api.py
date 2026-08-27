"""API-level tests for room creation, listing, membership, and notifications."""

from __future__ import annotations

import logging
import tempfile
import threading
import time
import unittest
from pathlib import Path

from client.core.client import ChatClient
from common.config_loader import AppConfig
from server.core.server import ChatServer
from common.protocol_constants import EVENT_NEW_MESSAGE, EVENT_ROOM_UPDATE


class RoomsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.db_path = Path(cls.temp_dir.name) / "test_rooms_api.db"
        cls.config = AppConfig(host="127.0.0.1", port=8770, database_path=str(cls.db_path), log_level="DEBUG")
        cls.logger = logging.getLogger("test_rooms_api")
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
        self.client_a = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        self.client_b = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        self.client_a.connect(); self.client_b.connect()
        self.client_a.start_listener(); self.client_b.start_listener()
        self.events_a = []
        self.events_b = []
        self.client_a.add_event_callback(lambda f: self.events_a.append(f))
        self.client_b.add_event_callback(lambda f: self.events_b.append(f))

    def tearDown(self) -> None:
        try:
            self.client_a.disconnect()
        finally:
            try:
                self.client_b.disconnect()
            finally:
                pass

    def test_room_create_list_join_leave_and_members(self) -> None:
        # Register and login
        self.client_a.register("room_user_a", "Pass123")
        self.client_b.register("room_user_b", "Pass123")
        self.client_a.login("room_user_a", "Pass123")
        self.client_b.login("room_user_b", "Pass123")

        # Create a new room
        resp = self.client_a.create_room("DevRoom")
        self.assertEqual(resp.get("status"), "success")

        # Duplicate creation fails
        dup = self.client_a.create_room("DevRoom")
        self.assertEqual(dup.get("status"), "error")

        # List rooms
        rooms_resp = self.client_a.get_rooms()
        self.assertEqual(rooms_resp.get("status"), "success")
        rooms = rooms_resp.get("payload", {}).get("rooms", [])
        names = [r.get("name") for r in rooms]
        self.assertIn("DevRoom", names)

        # Join room B
        jresp = self.client_b.join_room("DevRoom")
        self.assertEqual(jresp.get("status"), "success")

        # Member list
        members = self.client_a.get_room_members("DevRoom")
        self.assertEqual(members.get("status"), "success")
        member_names = [m.get("username") for m in members.get("payload", {}).get("members", [])]
        self.assertIn("room_user_b", member_names)

        # Broadcast a message from A
        msg = "Hello Devs"
        self.client_a.send_chat_message("room", "DevRoom", msg)

        # B should receive new_message
        time.sleep(0.2)
        found = any(f.get("event") == EVENT_NEW_MESSAGE and f.get("payload", {}).get("content") == msg for f in self.events_b)
        self.assertTrue(found)

        # B leaves room
        lresp = self.client_b.leave_room("DevRoom")
        self.assertEqual(lresp.get("status"), "success")

        # A should receive room_update about user_left
        time.sleep(0.2)
        found_leave = any(f.get("event") == EVENT_ROOM_UPDATE and f.get("payload", {}).get("action") == "user_left" for f in self.events_a)
        self.assertTrue(found_leave)

    def test_direct_message_delivery_and_history(self) -> None:
        self.client_a.register("dm_user_a", "Pass123")
        self.client_b.register("dm_user_b", "Pass123")
        self.client_a.login("dm_user_a", "Pass123")
        self.client_b.login("dm_user_b", "Pass123")

        # A sends DM to B
        self.client_a.send_chat_message("user", "dm_user_b", "Private hi")
        time.sleep(0.2)
        found = any(f.get("event") == EVENT_NEW_MESSAGE and f.get("payload", {}).get("content") == "Private hi" for f in self.events_b)
        self.assertTrue(found)

        # History for DM
        hist = self.client_a.get_history("user", "dm_user_b", limit=10)
        self.assertEqual(hist.get("status"), "success")
        msgs = hist.get("payload", {}).get("messages", [])
        contents = [m.get("content") for m in msgs]
        self.assertIn("Private hi", contents)


if __name__ == "__main__":
    unittest.main()
