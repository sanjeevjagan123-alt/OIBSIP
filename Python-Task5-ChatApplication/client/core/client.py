"""TCP client for connecting to the chat server and exchanging framed JSON messages."""

from __future__ import annotations

import queue
import socket
import threading
from typing import Any, Callable, Self

from client.core.protocol import recv_frame, send_frame, ProtocolError
from common.protocol_constants import (
    ACTION_CREATE_ROOM,
    ACTION_DISCONNECT,
    ACTION_GET_HISTORY,
    ACTION_GET_ROOMS,
    ACTION_GET_ROOM_MEMBERS,
    ACTION_JOIN_ROOM,
    ACTION_LEAVE_ROOM,
    ACTION_LOGIN,
    ACTION_MESSAGE_DELIVERED,
    ACTION_PING,
    ACTION_REGISTER,
    ACTION_SEND_MESSAGE,
    ACTION_SEARCH_MESSAGES,
    ACTION_TYPING,
    EVENT_RESPONSE,
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
        self._listener_thread: threading.Thread | None = None
        self._stop_listener = threading.Event()
        self._response_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._event_callbacks: list[Callable[[dict[str, Any]], None]] = []
        self._listener_active = False

    @property
    def is_connected(self) -> bool:
        """Return True if socket exists and is connected."""
        return self._socket is not None

    def connect(self) -> None:
        """Establish TCP connection to the server."""

        # Clear stale responses from any previous connection session.
        while True:
            try:
                self._response_queue.get_nowait()
            except queue.Empty:
                break

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

    def send_request(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a framed JSON request and return the server's framed JSON response."""
        if self._socket is None:
            raise ConnectionError("Client is not connected to the server.")

        message = {
            "action": action,
            "payload": payload if payload is not None else {},
        }
        send_frame(self._socket, message)

        # If listener is active, get response from queue.
        if self._listener_active:
            try:
                return self._response_queue.get(timeout=self.timeout)
            except queue.Empty:
                raise ConnectionError("Timed out waiting for server response.")
        else:
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

    # ---- Stage 5: Chat Room Methods ----

    def create_room(self, room_name: str) -> dict[str, Any]:
        """Send a create room request."""
        return self.send_request(ACTION_CREATE_ROOM, {"room_name": room_name})

    def join_room(self, room_name: str) -> dict[str, Any]:
        """Send a join room request."""
        return self.send_request(ACTION_JOIN_ROOM, {"room_name": room_name})

    def leave_room(self, room_name: str) -> dict[str, Any]:
        """Send a leave room request."""
        return self.send_request(ACTION_LEAVE_ROOM, {"room_name": room_name})

    def send_chat_message(
        self,
        target_type: str,
        target_name: str,
        content: str,
    ) -> dict[str, Any]:
        """Send a chat message (room or direct)."""
        return self.send_request(
            ACTION_SEND_MESSAGE,
            {
                "target_type": target_type,
                "target_name": target_name,
                "content": content,
            },
        )

    def get_history(
        self,
        target_type: str,
        target_name: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Retrieve chat history for a room or user conversation."""
        return self.send_request(
            ACTION_GET_HISTORY,
            {
                "target_type": target_type,
                "target_name": target_name,
                "limit": limit,
            },
        )

    def send_typing(self, target_type: str, target_name: str, is_typing: bool) -> dict[str, Any]:
        """Notify the server that the user started or stopped typing.

        ``target_type`` must be "room" or "user". ``target_name`` is the room name or the
        username of the other participant. ``is_typing`` indicates whether typing has
        started (True) or stopped (False). Returns the server's response frame.
        """
        return self.send_request(
            ACTION_TYPING,
            {
                "target_type": target_type,
                "target_name": target_name,
                "is_typing": is_typing,
            },
        )

    def search_messages(
        self,
        target_type: str,
        target_name: str,
        query: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Search message history for a substring (case-insensitive).

        ``target_type`` is "room" for room history or "user" for a direct conversation.
        ``target_name`` is the room name or the other user's username. ``query`` is the
        substring to search for. ``limit`` caps the number of results (default 50, max 200).
        Returns a response containing ``payload['messages']``.
        """
        return self.send_request(
            ACTION_SEARCH_MESSAGES,
            {
                "target_type": target_type,
                "target_name": target_name,
                "query": query,
                "limit": limit,
            },
        )

    def get_rooms(self) -> dict[str, Any]:
        """Request available rooms from server."""
        return self.send_request(ACTION_GET_ROOMS)

    def get_room_members(self, room_name: str) -> dict[str, Any]:
        """Request room member list for a room by name."""
        return self.send_request(
            ACTION_GET_ROOM_MEMBERS,
            {"room_name": room_name},
        )

    def acknowledge_message_delivered(self, message_id: int) -> dict[str, Any]:
        """Acknowledge direct-message delivery using persisted message_id."""
        return self.send_request(ACTION_MESSAGE_DELIVERED, {"message_id": message_id})

    # ---- Asynchronous Event Listener ----

    def add_event_callback(
        self,
        callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """Register a callback for asynchronous server push events."""
        self._event_callbacks.append(callback)

    def start_listener(self) -> None:
        """Start the background listener thread."""
        if self._listener_thread is not None and self._listener_thread.is_alive():
            return

        if self._socket is None:
            raise ConnectionError("Client is not connected to the server.")

        self._stop_listener.clear()
        self._listener_active = True

        self._listener_thread = threading.Thread(
            target=self._listener_loop,
            daemon=True,
        )
        self._listener_thread.start()

    def _listener_loop(self) -> None:
        """Background loop reading frames and dispatching events vs responses."""
        while not self._stop_listener.is_set():
            if self._socket is None:
                break

            try:
                frame = recv_frame(self._socket)
                print("DEBUG LISTENER FRAME:", frame)

            except socket.timeout:
                # An idle persistent chat connection is normal.
                # Do not terminate the listener just because no data arrived.
                continue

            except (ConnectionError, OSError) as exc:
                print("DEBUG LISTENER SOCKET ERROR:", repr(exc))
                break

            except Exception as exc:
                print(
                    "DEBUG LISTENER EXCEPTION:",
                    type(exc).__name__,
                    repr(exc),
                )
                break

            if frame.get("event") == EVENT_RESPONSE or frame.get("event") == "error":
                self._response_queue.put(frame)
            else:
                for callback in self._event_callbacks:
                    try:
                        callback(frame)
                    except Exception:
                        pass

        self._listener_active = False

    def stop_listener(self) -> None:
        """Stop the background listener thread."""
        self._stop_listener.set()
        self._listener_active = False

        if self._listener_thread is not None:
            self._listener_thread.join(timeout=2.0)
            self._listener_thread = None


    # ---- Connection Management ----

    def disconnect(self) -> None:
        """Send a disconnect action if connected, then close the socket."""
        self.stop_listener()

        if self._socket is not None:
            try:
                message = {"action": ACTION_DISCONNECT}
                send_frame(self._socket, message)

                # Read optional server disconnect acknowledgment response.
                recv_frame(self._socket)

            except (OSError, ConnectionError, ProtocolError):
                # Handle network/format errors during final disconnect read gracefully.
                pass
            finally:
                self.close()

    def close(self) -> None:
        """Close the underlying TCP socket."""
        self.stop_listener()

        # Clear any responses left over from the current/previous session.
        while True:
            try:
                self._response_queue.get_nowait()
            except queue.Empty:
                break

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

    def __exit__(
        self,
        exc_type: object,
        exc_val: object,
        exc_tb: object,
    ) -> None:
        self.disconnect()