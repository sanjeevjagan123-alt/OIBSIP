"""TCP listener and lifecycle management for the chat server."""

from __future__ import annotations

import signal
import socket
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from common.config_loader import AppConfig
from server.core.client_handler import ClientHandler

if TYPE_CHECKING:
    import logging


@dataclass
class ChatServer:
    """Bind, listen, accept connections, and shut down cleanly."""

    config: AppConfig
    logger: logging.Logger
    _server_socket: socket.socket | None = field(default=None, init=False, repr=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _accept_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _client_handlers: list[ClientHandler] = field(default_factory=list, init=False, repr=False)

    def run(self) -> None:
        """Start the listener and block until shutdown."""

        self._install_signal_handlers()
        self._create_listener()
        self.logger.info("Server listening on %s:%s", self.config.host, self.config.port)
        try:
            self._accept_loop()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Stop accepting connections and close the listening socket."""

        if self._stop_event.is_set():
            return

        self._stop_event.set()
        for handler in list(self._client_handlers):
            handler.close()
        self._client_handlers.clear()

        if self._server_socket is not None:
            try:
                self._server_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None
        self.logger.info("Server shut down cleanly")

    def _install_signal_handlers(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            self.logger.debug("Skipping signal handler registration (not in main thread)")
            return

        def handle_signal(signum: int, _frame: object) -> None:
            self.logger.info("Received signal %s; shutting down", signum)
            self.shutdown()

        try:
            signal.signal(signal.SIGINT, handle_signal)
        except ValueError:
            pass

        try:
            signal.signal(signal.SIGTERM, handle_signal)
        except (AttributeError, ValueError):
            self.logger.debug("SIGTERM not available in this environment")

    def _create_listener(self) -> None:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.config.host, self.config.port))
        server_socket.listen()
        server_socket.settimeout(1.0)
        self._server_socket = server_socket

    def _accept_loop(self) -> None:
        assert self._server_socket is not None
        while not self._stop_event.is_set():
            try:
                client_socket, client_address = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self.logger.info("Accepted connection from %s:%s", *client_address)
            handler = ClientHandler(client_socket, client_address, self.config, self.logger)
            self._client_handlers.append(handler)
            handler.start()

        self.logger.debug("Accept loop exited")

