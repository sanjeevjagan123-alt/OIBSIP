"""Server survivability integration tests.

Ensure malformed client input does not kill the server and a subsequent valid client can connect.
"""

from __future__ import annotations

import socket
import struct
import threading
import time
import unittest

from client.core.client import ChatClient
from client.core.protocol import encode_frame, recv_frame
from common.config_loader import AppConfig
from server.core.server import ChatServer


class ServerSurvivabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = AppConfig(host="127.0.0.1", port=8772, database_path="data/test_stage10_survive.db", log_level="DEBUG", rate_limit_per_second=1000, rate_limit_burst=1000)
        # Ensure fresh database for this test run
        from pathlib import Path

        Path(cls.config.database_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            Path(cls.config.database_path).unlink()
        except Exception:
            pass

        import logging

        cls.logger = logging.getLogger("test_server_survive")
        cls.logger.setLevel(logging.DEBUG)
        cls.server = ChatServer(config=cls.config, logger=cls.logger)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server_thread.join(timeout=2.0)

    def test_malformed_request_then_valid_client(self) -> None:
        # Connect raw and send a malformed frame (invalid JSON)
        sock = socket.create_connection((self.config.host, self.config.port), timeout=2.0)
        try:
            bad = b"not-json"
            header = struct.pack("!I", len(bad))
            sock.sendall(header + bad)
            # Server should respond with an error frame or close; attempt to read
            try:
                resp = recv_frame(sock)
                # Accept either an error frame or some response; ensure server didn't crash
                self.assertIn(resp.get("event"), ("error", "response"))
            except Exception:
                # If server closed the connection that's acceptable for survivability
                pass
        finally:
            sock.close()

        # Now a fresh valid client should still be able to connect and PING
        client = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        client.connect()
        try:
            resp = client.ping()
            self.assertEqual(resp.get("event"), "response")
            self.assertEqual(resp.get("payload", {}).get("message"), "pong")
        finally:
            client.disconnect()


if __name__ == "__main__":
    unittest.main()
