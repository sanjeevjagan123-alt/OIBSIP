"""Server-side state tests for authentication flows (registry and default room membership)."""

from __future__ import annotations

import logging
import queue
import tempfile
import threading
import time
import unittest
from pathlib import Path

from client.core.client import ChatClient
from common.config_loader import AppConfig
from server.core.server import ChatServer


class AuthServerStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.db_path = Path(cls.temp_dir.name) / "test_auth_state.db"
        cls.config = AppConfig(host="127.0.0.1", port=8768, database_path=str(cls.db_path), log_level="DEBUG")
        cls.logger = logging.getLogger("test_auth_state")
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

    def test_login_register_updates_registry_and_rooms(self) -> None:
        username = "state_user"
        password = "StatePass123"
        client = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        client.connect()
        try:
            reg = client.register(username, password)
            self.assertEqual(reg.get("status"), "success")
            login = client.login(username, password)
            self.assertEqual(login.get("status"), "success")
            self.assertIsNotNone(client.current_user)

            # Verify server registry has this client handler
            handler = self.server.client_registry.get_client_by_username(username)
            self.assertIsNotNone(handler)

            # Verify the user is a member of #general in the room manager memory
            uid = client.current_user.get("user_id")
            rooms = self.server.room_manager._rooms
            self.assertIn("general", rooms)
            self.assertIn(uid, rooms["general"])
        finally:
            client.disconnect()

    def test_presence_online_offline_and_unexpected_disconnect(self) -> None:
        observer = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        user_client = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        events: queue.Queue[dict] = queue.Queue()

        observer.connect()
        user_client.connect()
        try:
            observer.register("presence_observer", "Pass12345")
            observer.login("presence_observer", "Pass12345")
            observer.start_listener()
            observer.add_event_callback(lambda event: events.put(event))

            user_client.register("presence_user", "Pass12345")
            user_client.login("presence_user", "Pass12345")

            online_evt = None
            for _ in range(20):
                evt = events.get(timeout=1.0)
                if evt.get("event") == "presence_update" and evt.get("payload", {}).get("username") == "presence_user":
                    online_evt = evt
                    break
            self.assertIsNotNone(online_evt)
            self.assertEqual(online_evt["payload"]["state"], "online")

            user_client.close()

            offline_evt = None
            for _ in range(20):
                evt = events.get(timeout=1.0)
                if evt.get("event") == "presence_update" and evt.get("payload", {}).get("username") == "presence_user":
                    offline_evt = evt
                    break
            self.assertIsNotNone(offline_evt)
            self.assertEqual(offline_evt["payload"]["state"], "offline")
        finally:
            observer.disconnect()
            user_client.close()


if __name__ == "__main__":
    unittest.main()
