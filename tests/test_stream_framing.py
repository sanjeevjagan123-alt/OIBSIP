"""Unit tests for socket stream protocol framing."""

from __future__ import annotations

import socket
import struct
import unittest

from client.core.protocol import ProtocolError, decode_frame, encode_frame, recv_exact, recv_frame, send_frame


class StreamFramingTests(unittest.TestCase):
    """Verify socket stream frame sending, receiving, and error handling."""

    def setUp(self) -> None:
        self.server_sock, self.client_sock = socket.socketpair()

    def tearDown(self) -> None:
        self.server_sock.close()
        self.client_sock.close()

    def test_send_and_recv_frame_roundtrip(self) -> None:
        message = {"action": "ping", "payload": {"foo": "bar"}}
        send_frame(self.client_sock, message)
        received = recv_frame(self.server_sock)
        self.assertEqual(received, message)

    def test_partial_recv_exact(self) -> None:
        data = b"Hello, World!"
        # Send data in two separate chunks
        self.client_sock.sendall(data[:5])
        self.client_sock.sendall(data[5:])
        result = recv_exact(self.server_sock, len(data))
        self.assertEqual(result, data)

    def test_oversized_payload_raises_error(self) -> None:
        # Header specifying a payload size of 1000 bytes
        header = struct.pack("!I", 1000)
        self.client_sock.sendall(header)
        # Attempting to receive with max_payload_bytes = 500 should raise ProtocolError
        with self.assertRaises(ProtocolError):
            recv_frame(self.server_sock, max_payload_bytes=500)

    def test_connection_closed_on_header_raises_connection_error(self) -> None:
        self.client_sock.close()
        with self.assertRaises(ConnectionError):
            recv_exact(self.server_sock, 4)


if __name__ == "__main__":
    unittest.main()
