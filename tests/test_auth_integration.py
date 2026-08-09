"""Integration tests for TCP registration and authentication flows."""

from __future__ import annotations

import logging
import tempfile
import threading
import time
import unittest
from pathlib import Path

from client.core.client import ChatClient
from common.config_loader import AppConfig
from common.protocol_constants import (
    ERROR_INVALID_CREDENTIALS,
    ERROR_USER_EXISTS,
    EVENT_ERROR,
    EVENT_RESPONSE,
    STATUS_ERROR,
    STATUS_SUCCESS,
)
from server.core.server import ChatServer


class AuthIntegrationTests(unittest.TestCase):
    """End-to-end integration tests for user registration and login over TCP."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.db_path = Path(cls.temp_dir.name) / "test_auth_integration.db"
        cls.config = AppConfig(
            host="127.0.0.1",
            port=8767,
            database_path=str(cls.db_path),
            log_level="DEBUG",
            password_iterations=10000,
        )
        cls.logger = logging.getLogger("test_auth_server")
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

    def test_registration_flow(self) -> None:
        with ChatClient(host=self.config.host, port=self.config.port, timeout=3.0) as client:
            # Register new user
            resp = client.register("alice_test", "Password123!")
            self.assertEqual(resp.get("event"), EVENT_RESPONSE)
            self.assertEqual(resp.get("status"), STATUS_SUCCESS)
            self.assertEqual(resp.get("payload", {}).get("username"), "alice_test")

            # Duplicate registration returns USER_EXISTS
            dup_resp = client.register("alice_test", "Password123!")
            self.assertEqual(dup_resp.get("event"), EVENT_ERROR)
            self.assertEqual(dup_resp.get("status"), STATUS_ERROR)
            self.assertEqual(dup_resp.get("error_code"), ERROR_USER_EXISTS)

    def test_login_flow(self) -> None:
        # First register user
        with ChatClient(host=self.config.host, port=self.config.port, timeout=3.0) as client:
            client.register("bob_test", "MyPass456")

        # Now attempt login
        with ChatClient(host=self.config.host, port=self.config.port, timeout=3.0) as client:
            # Valid login
            login_resp = client.login("bob_test", "MyPass456")
            self.assertEqual(login_resp.get("event"), EVENT_RESPONSE)
            self.assertEqual(login_resp.get("status"), STATUS_SUCCESS)
            self.assertEqual(client.current_user.get("username"), "bob_test")

            # Invalid password
            bad_pass_resp = client.login("bob_test", "WrongPassword")
            self.assertEqual(bad_pass_resp.get("event"), EVENT_ERROR)
            self.assertEqual(bad_pass_resp.get("status"), STATUS_ERROR)
            self.assertEqual(bad_pass_resp.get("error_code"), ERROR_INVALID_CREDENTIALS)

            # Unknown user
            unknown_user_resp = client.login("unknown_user", "MyPass456")
            self.assertEqual(unknown_user_resp.get("event"), EVENT_ERROR)
            self.assertEqual(unknown_user_resp.get("status"), STATUS_ERROR)
            self.assertEqual(unknown_user_resp.get("error_code"), ERROR_INVALID_CREDENTIALS)

    def test_concurrent_user_sessions(self) -> None:
        # Register user 1 and user 2
        client1 = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        client2 = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        client1.connect()
        client2.connect()

        try:
            client1.register("user_one", "PassOne123")
            client2.register("user_two", "PassTwo456")

            res1 = client1.login("user_one", "PassOne123")
            res2 = client2.login("user_two", "PassTwo456")

            self.assertEqual(res1.get("status"), STATUS_SUCCESS)
            self.assertEqual(res2.get("status"), STATUS_SUCCESS)
            self.assertEqual(client1.current_user.get("username"), "user_one")
            self.assertEqual(client2.current_user.get("username"), "user_two")
        finally:
            client1.disconnect()
            client2.disconnect()


if __name__ == "__main__":
    unittest.main()
