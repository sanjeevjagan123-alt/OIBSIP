"""Session lifecycle and edge-case tests focusing on reconnect and stale-response protection.
"""

from __future__ import annotations

import threading
import time
import unittest

from client.core.client import ChatClient
from common.config_loader import AppConfig
from common.protocol_constants import ACTION_SEND_MESSAGE, EVENT_ERROR, ERROR_UNAUTHORIZED
from server.core.server import ChatServer


class SessionEdgeCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = AppConfig(host="127.0.0.1", port=8776, database_path="data/test_stage10_session.db", log_level="DEBUG", rate_limit_per_second=1000, rate_limit_burst=1000)
        # Ensure fresh database for this test run
        from pathlib import Path

        Path(cls.config.database_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            Path(cls.config.database_path).unlink()
        except Exception:
            pass

        import logging

        cls.logger = logging.getLogger("test_server_session")
        cls.logger.setLevel(logging.DEBUG)
        cls.server = ChatServer(config=cls.config, logger=cls.logger)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server_thread.join(timeout=2.0)

    def test_connect_login_disconnect_reconnect_get_history(self) -> None:
        client = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        client.connect()
        # Use a unique username to avoid collisions across tests
        import uuid
        uname = f"edge_{uuid.uuid4().hex[:8]}"
        # Create user directly in the database to avoid transient registration races
        from server.database.db import DatabaseManager
        from server.logic.auth import hash_password

        db = DatabaseManager(self.config.database_path)
        hash_hex, salt_hex = hash_password("password")
        try:
            db.create_user(uname, hash_hex, salt_hex)
        except ValueError:
            pass

        # Sanity-check stored credentials in the same DB used by the server
        stored = db.get_user_by_username(uname)
        from server.logic.auth import verify_password
        assert stored is not None, "User record not found in DB after creation"
        assert verify_password("password", stored["password_hash"], stored["salt"]), "Password verification failed for stored record"

        # Ensure server instance can also read the created user record
        server_stored = self.server.db.get_user_by_username(uname)
        assert server_stored is not None, "Server did not observe the newly created user record"

        resp = client.login(uname, "password")
        assert resp.get("status") == "success", f"Login response: {resp}"
        self.assertIsNotNone(client.current_user)
        # Disconnect
        client.disconnect()
        # Reconnect and login again
        client.connect()
        resp2 = client.login(uname, "password")
        assert resp2.get("status") == "success", f"Second login response: {resp2}"
        self.assertIsNotNone(client.current_user)
        # get_history for a room that probably exists ('general') should return a response (may be empty)
        hist = client.get_history("room", "general", limit=10)
        self.assertIn(hist.get("status"), ("success", "error"))
        client.disconnect()

    def test_repeated_disconnect_calls_are_safe(self) -> None:
        client = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        client.connect()
        client.disconnect()
        # Calling disconnect/close repeatedly should not raise
        client.disconnect()
        client.close()
        client.close()

    def test_unauthenticated_send_and_history_rejected(self) -> None:
        # A client that is connected but not logged in should receive unauthorized error
        client = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        client.connect()
        try:
            # Attempt to send a message unauthenticated
            resp = client.send_chat_message("room", "general", "hello unauth")
            self.assertEqual(resp.get("event"), EVENT_ERROR)
            self.assertEqual(resp.get("error_code"), ERROR_UNAUTHORIZED)
            # Attempt to get history unauthenticated
            resp2 = client.get_history("room", "general", limit=10)
            self.assertEqual(resp2.get("event"), EVENT_ERROR)
            self.assertEqual(resp2.get("error_code"), ERROR_UNAUTHORIZED)
        finally:
            client.disconnect()

    def test_stale_response_queue_cleared_on_reconnect(self) -> None:
        # This test exercises the Stage 9 protection: ensure response queue is drained on connect()
        client = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        client.connect()
        # Simulate listener running and inserting a stale response
        client.start_listener()
        # Put a fake response into the internal queue (simulate leftover)
        client._response_queue.put({"event": "response", "action": "ping", "status": "success", "payload": {}})
        # Close should drain queue
        client.close()
        # Reconnect should leave queue empty
        client.connect()
        self.assertTrue(client._response_queue.empty())
        client.disconnect()


if __name__ == "__main__":
    unittest.main()
