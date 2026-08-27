"""Integration test for ChatClient and ChatServer PING-PONG communication."""

from __future__ import annotations

import logging
import threading
import time
import unittest

from client.core.client import ChatClient
from common.config_loader import AppConfig
from common.protocol_constants import ACTION_PING, ERROR_INVALID_REQUEST, EVENT_ERROR, EVENT_RESPONSE, STATUS_ERROR, STATUS_SUCCESS
from server.core.server import ChatServer


class ClientServerIntegrationTests(unittest.TestCase):
    """End-to-end integration tests verifying TCP client-server communication."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.config = AppConfig(
            host="127.0.0.1",
            port=8766,
            database_path="data/test_chat.db",
            log_level="DEBUG",
        )
        cls.logger = logging.getLogger("test_server")
        cls.logger.setLevel(logging.DEBUG)
        cls.server = ChatServer(config=cls.config, logger=cls.logger)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        # Allow server thread time to bind and enter listen loop
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server_thread.join(timeout=2.0)

    def test_ping_pong_exchange(self) -> None:
        """Verify client connects, sends PING, receives PONG, and closes cleanly."""
        client = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        client.connect()
        try:
            response = client.ping()
            self.assertEqual(response.get("event"), EVENT_RESPONSE)
            self.assertEqual(response.get("action"), ACTION_PING)
            self.assertEqual(response.get("status"), STATUS_SUCCESS)
            self.assertEqual(response.get("payload", {}).get("message"), "pong")
        finally:
            client.disconnect()

    def test_unknown_action_response(self) -> None:
        """Verify server responds with ERROR_INVALID_REQUEST for unknown action."""
        with ChatClient(host=self.config.host, port=self.config.port, timeout=3.0) as client:
            response = client.send_request(action="invalid_action_foo")
            self.assertEqual(response.get("event"), EVENT_ERROR)
            self.assertEqual(response.get("status"), STATUS_ERROR)
            self.assertEqual(response.get("error_code"), ERROR_INVALID_REQUEST)


if __name__ == "__main__":
    unittest.main()
