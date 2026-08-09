"""Protocol framing helpers for TCP JSON messages."""

from __future__ import annotations

import json
import struct
from typing import Any

from common.protocol_constants import DEFAULT_ENCODING, FRAME_HEADER_SIZE


class ProtocolError(ValueError):
    """Raised when a frame cannot be encoded or decoded."""


def encode_frame(message: dict[str, Any]) -> bytes:
    """Serialize a JSON message with a 4-byte length prefix."""

    payload = json.dumps(message, separators=(",", ":")).encode(DEFAULT_ENCODING)
    header = struct.pack("!I", len(payload))
    return header + payload


def decode_frame(data: bytes) -> dict[str, Any]:
    """Decode a single length-prefixed JSON frame."""

    if len(data) < FRAME_HEADER_SIZE:
        raise ProtocolError("Frame is too short to contain a header.")

    payload_length = struct.unpack("!I", data[:FRAME_HEADER_SIZE])[0]
    payload = data[FRAME_HEADER_SIZE:]
    if len(payload) != payload_length:
        raise ProtocolError("Frame payload length does not match header.")

    try:
        decoded = payload.decode(DEFAULT_ENCODING)
        message = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("Frame payload is not valid UTF-8 JSON.") from exc

    if not isinstance(message, dict):
        raise ProtocolError("Decoded frame must be a JSON object.")
    return message
