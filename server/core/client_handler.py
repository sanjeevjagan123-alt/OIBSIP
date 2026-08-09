"""Session handler for individual client socket connections."""

from __future__ import annotations

import re
import socket
import threading
from typing import TYPE_CHECKING, Any

from client.core.protocol import ProtocolError, recv_frame, send_frame
from common.protocol_constants import (
    ACTION_CREATE_ROOM,
    ACTION_DISCONNECT,
    ACTION_GET_HISTORY,
    ACTION_JOIN_ROOM,
    ACTION_LEAVE_ROOM,
    ACTION_LOGIN,
    ACTION_PING,
    ACTION_REGISTER,
    ACTION_SEND_MESSAGE,
    ERROR_INVALID_REQUEST,
    ERROR_RATE_LIMIT_EXCEEDED,
    ERROR_ROOM_EXISTS,
    ERROR_ROOM_NOT_FOUND,
    ERROR_UNAUTHORIZED,
    ERROR_USER_NOT_FOUND,
    EVENT_ERROR,
    EVENT_NEW_MESSAGE,
    EVENT_RESPONSE,
    EVENT_ROOM_UPDATE,
    STATUS_ERROR,
    STATUS_SUCCESS,
)

if TYPE_CHECKING:
    import logging
    from common.config_loader import AppConfig
    from server.logic.auth import AuthManager
    from server.logic.client_registry import ClientRegistry
    from server.logic.rate_limiter import TokenBucketRateLimiter
    from server.logic.rooms import RoomManager

ROOM_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{1,30}$")


class ClientHandler(threading.Thread):
    """Manages the request/response lifecycle for a single connected client."""

    def __init__(
        self,
        client_socket: socket.socket,
        client_address: tuple[str, int],
        config: AppConfig,
        logger: logging.Logger,
        auth_manager: AuthManager | None = None,
        client_registry: ClientRegistry | None = None,
        room_manager: RoomManager | None = None,
    ) -> None:
        super().__init__(daemon=True)
        self.client_socket = client_socket
        self.client_address = client_address
        self.config = config
        self.logger = logger
        self.auth_manager = auth_manager
        self.client_registry = client_registry
        self.room_manager = room_manager
        self.authenticated_user: dict[str, Any] | None = None
        self.rate_limiter: TokenBucketRateLimiter | None = None
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

                self.logger.debug("Received request from %s:%s: action=%s", self.client_address[0], self.client_address[1], request.get("action"))
                response = self._route_request(request)
                if response is not None:
                    send_frame(self.client_socket, response)

                if request.get("action") == ACTION_DISCONNECT:
                    self.logger.info("Client %s:%s requested disconnect.", *self.client_address)
                    break
        except OSError as exc:
            self.logger.debug("Socket exception in session %s:%s: %s", self.client_address[0], self.client_address[1], exc)
        finally:
            self._cleanup()
            self.logger.info("Session closed for %s:%s", *self.client_address)

    def _cleanup(self) -> None:
        """Unregister from all registries and close socket."""
        if self.authenticated_user is not None:
            user_id = self.authenticated_user.get("user_id")
            if user_id is not None:
                if self.room_manager is not None:
                    self.room_manager.remove_user_from_all_rooms(user_id)
                if self.client_registry is not None:
                    self.client_registry.unregister_client(user_id)
        self.close()

    def _require_auth(self) -> dict[str, Any] | None:
        """Return an error response if the user is not authenticated, else None."""
        if self.authenticated_user is None:
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_UNAUTHORIZED,
                "message": "Authentication required.",
            }
        return None

    def _check_rate_limit(self, action: str) -> dict[str, Any] | None:
        """Return a rate-limit error response if the request is throttled, else None."""
        if self.rate_limiter is not None and not self.rate_limiter.allow_request():
            self.logger.warning(
                "Rate limit exceeded for user '%s' on action '%s'",
                self.authenticated_user.get("username") if self.authenticated_user else "unknown",
                action,
            )
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_RATE_LIMIT_EXCEEDED,
                "message": f"Rate limit exceeded. Maximum {self.config.rate_limit_per_second} requests/sec allowed.",
            }
        return None

    def _route_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Dispatch incoming action to appropriate logic handler."""
        action = request.get("action")
        payload = request.get("payload", {})
        if not isinstance(payload, dict):
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "Payload must be a JSON object.",
            }

        if action == ACTION_PING:
            return {
                "event": EVENT_RESPONSE,
                "action": ACTION_PING,
                "status": STATUS_SUCCESS,
                "payload": {"message": "pong"},
            }
        elif action == ACTION_REGISTER:
            return self._handle_register(payload)
        elif action == ACTION_LOGIN:
            return self._handle_login(payload)
        elif action == ACTION_DISCONNECT:
            return {
                "event": EVENT_RESPONSE,
                "action": ACTION_DISCONNECT,
                "status": STATUS_SUCCESS,
                "payload": {"message": "Disconnected cleanly"},
            }
        elif action == ACTION_CREATE_ROOM:
            return self._handle_create_room(payload)
        elif action == ACTION_JOIN_ROOM:
            return self._handle_join_room(payload)
        elif action == ACTION_LEAVE_ROOM:
            return self._handle_leave_room(payload)
        elif action == ACTION_SEND_MESSAGE:
            return self._handle_send_message(payload)
        elif action == ACTION_GET_HISTORY:
            return self._handle_get_history(payload)
        else:
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": f"Unsupported or unknown action '{action}'.",
            }

    # ---- Authentication Handlers (Stage 4) ----

    def _handle_register(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle user registration."""
        if self.auth_manager is None:
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "Authentication manager not configured on server.",
            }
        username = payload.get("username")
        password = payload.get("password")
        success, err_code, err_msg, user_info = self.auth_manager.register_user(username, password)
        if success:
            self.logger.info("Successfully registered user '%s' from %s:%s", username, *self.client_address)
            return {
                "event": EVENT_RESPONSE,
                "action": ACTION_REGISTER,
                "status": STATUS_SUCCESS,
                "payload": user_info,
            }
        else:
            self.logger.warning("Failed registration attempt for user '%s': %s", username, err_msg)
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": err_code,
                "message": err_msg,
            }

    def _handle_login(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle user login and session initialization."""
        if self.auth_manager is None:
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "Authentication manager not configured on server.",
            }
        username = payload.get("username")
        password = payload.get("password")
        success, err_code, err_msg, user_info = self.auth_manager.authenticate_user(username, password)
        if success:
            self.authenticated_user = user_info
            user_id = user_info["user_id"]

            # Initialize rate limiter for this session
            from server.logic.rate_limiter import TokenBucketRateLimiter
            self.rate_limiter = TokenBucketRateLimiter(
                rate_per_second=self.config.rate_limit_per_second,
                burst_capacity=self.config.rate_limit_burst,
            )

            # Register in client registry
            if self.client_registry is not None:
                self.client_registry.register_client(user_id, self)

            # Auto-join the default #general room
            if self.room_manager is not None:
                try:
                    self.room_manager.join_room("general", user_id)
                except ValueError:
                    pass  # Room might not exist yet if server init race

            self.logger.info("User '%s' authenticated successfully from %s:%s", username, *self.client_address)
            return {
                "event": EVENT_RESPONSE,
                "action": ACTION_LOGIN,
                "status": STATUS_SUCCESS,
                "payload": user_info,
            }
        else:
            self.logger.warning("Authentication failed for user '%s' from %s:%s", username, *self.client_address)
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": err_code,
                "message": err_msg,
            }

    # ---- Stage 5: Chat Room Handlers ----

    def _handle_create_room(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle room creation request."""
        auth_err = self._require_auth()
        if auth_err is not None:
            return auth_err

        rate_err = self._check_rate_limit(ACTION_CREATE_ROOM)
        if rate_err is not None:
            return rate_err

        room_name = payload.get("room_name")
        if not room_name or not isinstance(room_name, str):
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "Room name is required.",
            }

        clean_name = room_name.strip()
        if not ROOM_NAME_REGEX.match(clean_name):
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "Room name must be 1-30 alphanumeric characters or underscores.",
            }

        if self.room_manager is None:
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "Room management not configured on server.",
            }

        user_id = self.authenticated_user["user_id"]
        try:
            room = self.room_manager.create_room(clean_name, created_by=user_id)
            # Auto-join the creator
            self.room_manager.join_room(clean_name, user_id)
            self.logger.info("User '%s' created room '%s'", self.authenticated_user.get("username"), clean_name)
            return {
                "event": EVENT_RESPONSE,
                "action": ACTION_CREATE_ROOM,
                "status": STATUS_SUCCESS,
                "payload": {"room_id": room["id"], "room_name": room["name"]},
            }
        except ValueError:
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_ROOM_EXISTS,
                "message": f"Room '{clean_name}' already exists.",
            }

    def _handle_join_room(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle room join request."""
        auth_err = self._require_auth()
        if auth_err is not None:
            return auth_err

        rate_err = self._check_rate_limit(ACTION_JOIN_ROOM)
        if rate_err is not None:
            return rate_err

        room_name = payload.get("room_name")
        if not room_name or not isinstance(room_name, str):
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "Room name is required.",
            }

        if self.room_manager is None:
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "Room management not configured on server.",
            }

        user_id = self.authenticated_user["user_id"]
        try:
            room = self.room_manager.join_room(room_name.strip(), user_id)
            username = self.authenticated_user.get("username", "")
            self.logger.info("User '%s' joined room '%s'", username, room_name)

            # Broadcast room update to other members
            room_update = {
                "event": EVENT_ROOM_UPDATE,
                "payload": {
                    "room_name": room["name"],
                    "action": "user_joined",
                    "username": username,
                },
            }
            self.room_manager.broadcast_to_room(room_name.strip(), room_update, exclude_user_id=user_id)

            return {
                "event": EVENT_RESPONSE,
                "action": ACTION_JOIN_ROOM,
                "status": STATUS_SUCCESS,
                "payload": {"room_id": room["id"], "room_name": room["name"]},
            }
        except ValueError:
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_ROOM_NOT_FOUND,
                "message": f"Room '{room_name}' does not exist.",
            }

    def _handle_leave_room(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle room leave request."""
        auth_err = self._require_auth()
        if auth_err is not None:
            return auth_err

        room_name = payload.get("room_name")
        if not room_name or not isinstance(room_name, str):
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "Room name is required.",
            }

        if self.room_manager is None:
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "Room management not configured on server.",
            }

        user_id = self.authenticated_user["user_id"]
        username = self.authenticated_user.get("username", "")

        # Broadcast departure before removing membership
        room_update = {
            "event": EVENT_ROOM_UPDATE,
            "payload": {
                "room_name": room_name.strip(),
                "action": "user_left",
                "username": username,
            },
        }
        self.room_manager.broadcast_to_room(room_name.strip(), room_update, exclude_user_id=user_id)

        self.room_manager.leave_room(room_name.strip(), user_id)
        self.logger.info("User '%s' left room '%s'", username, room_name)

        return {
            "event": EVENT_RESPONSE,
            "action": ACTION_LEAVE_ROOM,
            "status": STATUS_SUCCESS,
            "payload": {"room_name": room_name.strip()},
        }

    # ---- Stage 5: Messaging Handlers ----

    def _handle_send_message(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Handle send_message for both room and direct messages."""
        auth_err = self._require_auth()
        if auth_err is not None:
            return auth_err

        rate_err = self._check_rate_limit(ACTION_SEND_MESSAGE)
        if rate_err is not None:
            return rate_err

        target_type = payload.get("target_type")
        target_name = payload.get("target_name")
        content = payload.get("content")

        # Validate target_type
        if target_type not in ("room", "user"):
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "target_type must be 'room' or 'user'.",
            }

        # Validate target_name
        if not target_name or not isinstance(target_name, str):
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "target_name is required.",
            }

        # Validate content
        if not content or not isinstance(content, str) or not content.strip():
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "Message content cannot be empty.",
            }

        if len(content) > self.config.max_message_length:
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": f"Message content exceeds maximum length of {self.config.max_message_length} characters.",
            }

        user_id = self.authenticated_user["user_id"]
        username = self.authenticated_user.get("username", "")

        if target_type == "room":
            return self._send_room_message(user_id, username, target_name.strip(), content)
        else:
            return self._send_direct_message(user_id, username, target_name.strip(), content)

    def _send_room_message(self, sender_id: int, sender_username: str, room_name: str, content: str) -> dict[str, Any]:
        """Send a message to all members of a room."""
        if self.room_manager is None or self.room_manager.db is None:
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "Messaging not configured on server.",
            }

        # Verify room exists
        room = self.room_manager.db.get_room_by_name(room_name)
        if room is None:
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_ROOM_NOT_FOUND,
                "message": f"Room '{room_name}' does not exist.",
            }

        # Save message to database
        msg = self.room_manager.db.save_message(sender_id, "room", room["id"], content)

        # Build broadcast event
        broadcast_event = {
            "event": EVENT_NEW_MESSAGE,
            "payload": {
                "message_id": msg["id"],
                "sender_id": sender_id,
                "sender_username": sender_username,
                "target_type": "room",
                "target_name": room_name,
                "content": content,
                "timestamp": msg["timestamp"],
            },
        }

        # Broadcast to room members (excluding sender)
        self.room_manager.broadcast_to_room(room_name, broadcast_event, exclude_user_id=sender_id)

        # Return success acknowledgment to sender
        return {
            "event": EVENT_RESPONSE,
            "action": ACTION_SEND_MESSAGE,
            "status": STATUS_SUCCESS,
            "payload": {
                "message_id": msg["id"],
                "timestamp": msg["timestamp"],
            },
        }

    def _send_direct_message(self, sender_id: int, sender_username: str, target_username: str, content: str) -> dict[str, Any]:
        """Send a direct private message to another user."""
        if self.room_manager is None or self.room_manager.db is None:
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "Messaging not configured on server.",
            }

        # Look up target user in database
        target_user = self.room_manager.db.get_user_by_username(target_username)
        if target_user is None:
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_USER_NOT_FOUND,
                "message": f"User '{target_username}' not found.",
            }

        target_user_id = target_user["id"]

        # Save message to database
        msg = self.room_manager.db.save_message(sender_id, "user", target_user_id, content)

        # Try to deliver to online recipient
        if self.client_registry is not None:
            target_handler = self.client_registry.get_client(target_user_id)
            if target_handler is not None:
                push_event = {
                    "event": EVENT_NEW_MESSAGE,
                    "payload": {
                        "message_id": msg["id"],
                        "sender_id": sender_id,
                        "sender_username": sender_username,
                        "target_type": "user",
                        "target_name": target_username,
                        "content": content,
                        "timestamp": msg["timestamp"],
                    },
                }
                try:
                    send_frame(target_handler.client_socket, push_event)
                except (OSError, ConnectionError) as exc:
                    self.logger.warning("Failed to deliver direct message to '%s': %s", target_username, exc)

        # Return success to sender
        return {
            "event": EVENT_RESPONSE,
            "action": ACTION_SEND_MESSAGE,
            "status": STATUS_SUCCESS,
            "payload": {
                "message_id": msg["id"],
                "timestamp": msg["timestamp"],
            },
        }

    # ---- Stage 5: History Handler ----

    def _handle_get_history(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle chat history retrieval."""
        auth_err = self._require_auth()
        if auth_err is not None:
            return auth_err

        target_type = payload.get("target_type")
        target_name = payload.get("target_name")
        limit = payload.get("limit", 50)

        if target_type not in ("room", "user"):
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "target_type must be 'room' or 'user'.",
            }

        if not target_name or not isinstance(target_name, str):
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "target_name is required.",
            }

        if not isinstance(limit, int) or limit <= 0:
            limit = 50
        if limit > 200:
            limit = 200

        if self.room_manager is None or self.room_manager.db is None:
            return {
                "event": EVENT_ERROR,
                "status": STATUS_ERROR,
                "error_code": ERROR_INVALID_REQUEST,
                "message": "History not configured on server.",
            }

        if target_type == "room":
            room = self.room_manager.db.get_room_by_name(target_name.strip())
            if room is None:
                return {
                    "event": EVENT_ERROR,
                    "status": STATUS_ERROR,
                    "error_code": ERROR_ROOM_NOT_FOUND,
                    "message": f"Room '{target_name}' does not exist.",
                }
            target_id = room["id"]
        else:
            target_user = self.room_manager.db.get_user_by_username(target_name.strip())
            if target_user is None:
                return {
                    "event": EVENT_ERROR,
                    "status": STATUS_ERROR,
                    "error_code": ERROR_USER_NOT_FOUND,
                    "message": f"User '{target_name}' not found.",
                }
            target_id = target_user["id"]

        messages = self.room_manager.db.get_messages(target_type, target_id, limit=limit)

        return {
            "event": EVENT_RESPONSE,
            "action": ACTION_GET_HISTORY,
            "status": STATUS_SUCCESS,
            "payload": {"messages": messages},
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
