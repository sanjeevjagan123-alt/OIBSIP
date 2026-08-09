"""Protocol framing helpers for TCP JSON messages."""

from __future__ import annotations

import json
import socket
import struct
from typing import Any

from common.protocol_constants import DEFAULT_ENCODING, FRAME_HEADER_SIZE, MAX_PAYLOAD_BYTES


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


def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """Read exactly `num_bytes` from the socket or raise ConnectionError / ProtocolError on EOF."""

    buf = bytearray()
    while len(buf) < num_bytes:
        chunk = sock.recv(num_bytes - len(buf))
        if not chunk:
            if len(buf) == 0:
                raise ConnectionError("Connection closed by peer.")
            raise ProtocolError("Connection closed before full frame payload was received.")
        buf.extend(chunk)
    return bytes(buf)


def send_frame(sock: socket.socket, message: dict[str, Any]) -> None:
    """Encode a message and send it completely over a socket stream."""

    data = encode_frame(message)
    sock.sendall(data)


def recv_frame(sock: socket.socket, max_payload_bytes: int = MAX_PAYLOAD_BYTES) -> dict[str, Any]:
    """Read a length-prefixed JSON frame from a socket stream."""

    header = recv_exact(sock, FRAME_HEADER_SIZE)
    payload_length = struct.unpack("!I", header)[0]
    if payload_length > max_payload_bytes:
        raise ProtocolError(f"Payload length ({payload_length}) exceeds maximum allowed limit ({max_payload_bytes}).")
    payload = recv_exact(sock, payload_length)
    return decode_frame(header + payload)

