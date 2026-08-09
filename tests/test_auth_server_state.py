"""Server-side state tests for authentication flows (registry and default room membership)."""

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


if __name__ == "__main__":
    unittest.main()
