"""Tests for protocol frame encoding and decoding."""

from __future__ import annotations

import unittest

from client.core.protocol import decode_frame, encode_frame


class ProtocolFrameTests(unittest.TestCase):
    """Verify TCP JSON frame round-tripping."""

    def test_basic_json_payload_round_trip(self) -> None:
        payload = {"action": "ping", "msg_id": "req-1", "payload": {"text": "hello"}}
        self.assertEqual(decode_frame(encode_frame(payload)), payload)

    def test_nested_json_payload_round_trip(self) -> None:
        payload = {
            "event": "response",
            "status": "success",
            "payload": {
                "user": {"name": "alice", "roles": ["admin", "user"]},
                "flags": {"online": True, "typing": False},
            },
        }
        self.assertEqual(decode_frame(encode_frame(payload)), payload)


if __name__ == "__main__":
    unittest.main()
