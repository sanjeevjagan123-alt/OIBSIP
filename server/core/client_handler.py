"""Session handler for individual client socket connections."""

from __future__ import annotations

import socket
import threading
from typing import TYPE_CHECKING, Any

from client.core.protocol import ProtocolError, recv_frame, send_frame
from common.protocol_constants import (
    ACTION_DISCONNECT,
    ACTION_PING,
    ERROR_INVALID_REQUEST,
    EVENT_ERROR,
    EVENT_RESPONSE,
    STATUS_ERROR,
    STATUS_SUCCESS,
)

if TYPE_CHECKING:
    import logging
    from common.config_loader import AppConfig


class ClientHandler(threading.Thread):
    """Manages the request/response lifecycle for a single connected client."""

    def __init__(
        self,
        client_socket: socket.socket,
        client_address: tuple[str, int],
        config: AppConfig,
        logger: logging.Logger,
    ) -> None:
        super().__init__(daemon=True)
        self.client_socket = client_socket
        self.client_address = client_address
        self.config = config
        self.logger = logger
        self._stop_event = threading.Event()

    def run(self) -> None:
        """Continuously receive and handle framed JSON messages from the client."""
        self.logger.info("Started connection session for %s:%s", *self.client_address)
        try:
            while not self._stop_event.is_set():
                try:
                    request = recv_frame(self.client_socket, max_payload_bytes=self.config.max_payload_bytes)
                except ConnectionError:
                    self.logger.info("Client %s:%s disconnected.", *self.client_address)
                    break
                except ProtocolError as exc:
                    self.logger.warning(
                        "Protocol error from %s:%s: %s", self.client_address[0], self.client_address[1], exc
                    )
                    error_resp = {
                        "event": EVENT_ERROR,
                        "status": STATUS_ERROR,
                        "error_code": ERROR_INVALID_REQUEST,
                        "message": str(exc),
                    }
                    try:
                        send_frame(self.client_socket, error_resp)
                    except OSError:
                        pass
                    break

                self.logger.debug("Received request from %s:%s: %s", self.client_address[0], self.client_address[1], request)
                response = self._route_request(request)
                if response is not None:
                    send_frame(self.client_socket, response)

                if request.get("action") == ACTION_DISCONNECT:
                    self.logger.info("Client %s:%s requested disconnect.", *self.client_address)
                    break
        except OSError as exc:
            self.logger.debug("Socket exception in session %s:%s: %s", self.client_address[0], self.client_address[1], exc)
        finally:
            self.close()
            self.logger.info("Session closed for %s:%s", *self.client_address)

    def _route_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Dispatch incoming action to appropriate logic handler."""
        action = request.get("action")
        if action == ACTION_PING:
            return {
                "event": EVENT_RESPONSE,
                "action": ACTION_PING,
                "status": STATUS_SUCCESS,
                "payload": {"message": "pong"},
            }
        elif action == ACTION_DISCONNECT:
            return {
                "event": EVENT_RESPONSE,
                "action": ACTION_DISCONNECT,
                "status": STATUS_SUCCESS,
                "payload": {"message": "Disconnected cleanly"},
            }
        else:
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": f"Unsupported or unknown action '{action}'.",
            }

    def close(self) -> None:
        """Cleanly close client socket connection."""
        self._stop_event.set()
        try:
            self.client_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.client_socket.close()
        except OSError:
            pass
