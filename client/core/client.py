"""TCP client for connecting to the chat server and exchanging framed JSON messages."""

from __future__ import annotations

import socket
from typing import Any, Self

from client.core.protocol import recv_frame, send_frame
from common.protocol_constants import (
    ACTION_DISCONNECT,
    ACTION_LOGIN,
    ACTION_PING,
    ACTION_REGISTER,
    STATUS_SUCCESS,
)


class ChatClient:
    """Synchronous TCP client communicating with the server using framed JSON."""

    def __init__(self, host: str, port: int, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket: socket.socket | None = None
        self.current_user: dict[str, Any] | None = None

    @property
    def is_connected(self) -> bool:
        """Return True if socket exists and is connected."""
        return self._socket is not None

    def connect(self) -> None:
        """Establish TCP connection to the server."""
        if self._socket is not None:
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.host, self.port))
            self._socket = sock
        except Exception:
            sock.close()
            raise

    def send_request(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a framed JSON request and return the server's framed JSON response."""
        if self._socket is None:
            raise ConnectionError("Client is not connected to the server.")

        message = {
            "action": action,
            "payload": payload if payload is not None else {},
        }
        send_frame(self._socket, message)
        return recv_frame(self._socket)

    def ping(self) -> dict[str, Any]:
        """Send a PING request to the server and return the response."""
        return self.send_request(ACTION_PING)

    def register(self, username: str, password: str) -> dict[str, Any]:
        """Send a user registration request."""
        payload = {"username": username, "password": password}
        return self.send_request(ACTION_REGISTER, payload)

    def login(self, username: str, password: str) -> dict[str, Any]:
        """Send a user login request and update current_user on success."""
        payload = {"username": username, "password": password}
        response = self.send_request(ACTION_LOGIN, payload)
        if response.get("status") == STATUS_SUCCESS:
            self.current_user = response.get("payload")
        return response

    def disconnect(self) -> None:
        """Send a disconnect action if connected, then close the socket."""
        if self._socket is not None:
            try:
                message = {"action": ACTION_DISCONNECT}
                send_frame(self._socket, message)
                # Read optional server disconnect acknowledgment response
                recv_frame(self._socket)
            except (OSError, ConnectionError):
                pass
            finally:
                self.close()

    def close(self) -> None:
        """Close the underlying TCP socket."""
        self.current_user = None
        if self._socket is not None:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.disconnect()
