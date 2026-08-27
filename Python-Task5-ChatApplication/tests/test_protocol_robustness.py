"""Protocol robustness tests for Stage 10.

These tests exercise partial frame delivery, malformed payloads, oversized payloads,
connection interruptions during header/payload, and multiple back-to-back frames.

They use the repository's actual protocol helpers and server APIs.
"""

from __future__ import annotations

import socket
import struct
import threading
import time
import unittest

from client.core.protocol import (
    encode_frame,
    recv_frame,
    ProtocolError,
)
from client.core.client import ChatClient
from common.config_loader import AppConfig
from server.core.server import ChatServer


class ProtocolRobustnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = AppConfig(host="127.0.0.1", port=8770, database_path="data/test_stage10_proto.db", log_level="DEBUG", rate_limit_per_second=1000, rate_limit_burst=1000)
        # Ensure fresh database for this test run
        from pathlib import Path

        Path(cls.config.database_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            Path(cls.config.database_path).unlink()
        except Exception:
            pass

        import logging

        cls.logger = logging.getLogger("test_server_proto")
        cls.logger.setLevel(logging.DEBUG)
        cls.server = ChatServer(config=cls.config, logger=cls.logger)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server_thread.join(timeout=2.0)

    def test_partial_header_then_close_server_survives(self) -> None:
        # Connect and send only 2 bytes of the 4-byte header, then close.
        sock = socket.create_connection((self.config.host, self.config.port), timeout=2.0)
        try:
            sock.sendall(b"\x00\x01")
            sock.close()
        finally:
            try:
                sock.close()
            except Exception:
                pass

        # Ensure a new well-formed client can still connect and PING
        client = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        client.connect()
        try:
            resp = client.ping()
            self.assertEqual(resp.get("event"), "response")
        finally:
            client.disconnect()

    def test_partial_payload_then_close_server_survives(self) -> None:
        # Build a valid frame and send only the header + partial payload then close
        payload = {"action": "ping", "payload": {}}
        data = encode_frame(payload)
        sock = socket.create_connection((self.config.host, self.config.port), timeout=2.0)
        try:
            # send header + half of payload
            header = data[:4]
            body = data[4:]
            half = len(body) // 2
            sock.sendall(header + body[:half])
            sock.close()
        finally:
            try:
                sock.close()
            except Exception:
                pass

        # Server should still accept a new client
        client = ChatClient(host=self.config.host, port=self.config.port, timeout=3.0)
        client.connect()
        try:
            resp = client.ping()
            self.assertEqual(resp.get("event"), "response")
        finally:
            client.disconnect()

    def test_invalid_json_payload_returns_error(self) -> None:
        # Send a frame with valid header length but invalid JSON bytes
        bad_payload = b"{not: valid JSON}\n"
        header = struct.pack("!I", len(bad_payload))
        sock = socket.create_connection((self.config.host, self.config.port), timeout=2.0)
        try:
            sock.sendall(header + bad_payload)
            # Read server response (should be an error frame)
            resp = recv_frame(sock)
            self.assertEqual(resp.get("event"), "error")
        finally:
            sock.close()

    def test_oversized_payload_rejected(self) -> None:
        # Send a header that exceeds server's allowed payload -> server will respond with error
        huge = 1024 * 1024 * 20  # 20MB
        header = struct.pack("!I", huge)
        sock = socket.create_connection((self.config.host, self.config.port), timeout=2.0)
        try:
            sock.sendall(header)
            # Server should send an error frame (or close); try reading a frame and accept ProtocolError
            try:
                resp = recv_frame(sock)
                self.assertEqual(resp.get("event"), "error")
            except ProtocolError:
                # If server closes instead of sending an error, that's acceptable for this test
                pass
        finally:
            sock.close()

    def test_multiple_frames_back_to_back(self) -> None:
        # Send two PING frames in a single send and read two responses
        sock = socket.create_connection((self.config.host, self.config.port), timeout=2.0)
        try:
            data = encode_frame({"action": "ping", "payload": {}}) + encode_frame({"action": "ping", "payload": {}})
            sock.sendall(data)
            resp1 = recv_frame(sock)
            resp2 = recv_frame(sock)
            self.assertEqual(resp1.get("event"), "response")
            self.assertEqual(resp2.get("event"), "response")
        finally:
            sock.close()


if __name__ == "__main__":
    unittest.main()
