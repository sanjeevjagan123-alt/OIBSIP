"""Integration tests for chat room broadcasting, direct messages, and history persistence."""

from __future__ import annotations

import socket
import tempfile
import unittest
import logging
from pathlib import Path

from server.database.db import DatabaseManager
from server.logic.client_registry import ClientRegistry
from server.logic.rooms import RoomManager
from client.core.protocol import recv_frame, send_frame


class FakeHandler:
    def __init__(self, sock: socket.socket, user_id: int, username: str):
        self.client_socket = sock
        self.authenticated_user = {"user_id": user_id, "username": username}


class ChatIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "test_chat.db"
        self.db = DatabaseManager(self.db_path)
        self.db.init_db()
        self.registry = ClientRegistry()
        self.logger = logging.getLogger("test_chat")
        self.logger.addHandler(logging.NullHandler())
        self.rm = RoomManager(db=self.db, client_registry=self.registry, logger=self.logger)
        self.rm.init_default_room("general")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_room_broadcast_and_history(self) -> None:
        # create two user accounts
        u1 = self.db.create_user("alice", "h1", "s1")
        u2 = self.db.create_user("bob", "h2", "s2")

        # create socket pairs for both clients
        s1, c1 = socket.socketpair()
        s2, c2 = socket.socketpair()

        try:
            # register fake handlers in registry
            h1 = FakeHandler(c1, u1["id"], u1["username"][0:])
            h2 = FakeHandler(c2, u2["id"], u2["username"][0:])
            self.registry.register_client(u1["id"], h1)
            self.registry.register_client(u2["id"], h2)

            # Add both to general room
            self.rm.join_room("general", u1["id"])
            self.rm.join_room("general", u2["id"])

            # Broadcast a message from alice
            msg_event = {
                "event": "new_message",
                "payload": {"sender": "alice", "content": "Hello all"},
            }
            # Broadcast to room (exclude none)
            self.rm.broadcast_to_room("general", msg_event)

            # read messages from server sockets
            received1 = recv_frame(s1)
            received2 = recv_frame(s2)

            self.assertEqual(received1["event"], "new_message")
            self.assertEqual(received2["event"], "new_message")

            # Save a message and verify history retrieval
            saved = self.db.save_message(u1["id"], "room", self.db.get_room_by_name("general")["id"], "Persisted Msg")
            msgs = self.db.get_messages("room", self.db.get_room_by_name("general")["id"], limit=10)
            contents = [m["content"] for m in msgs]
            self.assertIn("Persisted Msg", contents)
        finally:
            s1.close(); s2.close(); c1.close(); c2.close()

    def test_direct_message_delivery(self) -> None:
        # create users
        u1 = self.db.create_user("charlie", "h1", "s1")
        u2 = self.db.create_user("dave", "h2", "s2")

        # socketpair for recipient
        s_recv, c_recv = socket.socketpair()
        try:
            handler_recv = FakeHandler(c_recv, u2["id"], u2["username"][0:])
            self.registry.register_client(u2["id"], handler_recv)

            # send direct message: save to DB then push to recipient
            msg = self.db.save_message(u1["id"], "user", u2["id"], "Private Hello")
            push_event = {
                "event": "new_message",
                "payload": {"sender": "charlie", "content": "Private Hello"},
            }
            send_frame(handler_recv.client_socket, push_event)
            received = recv_frame(s_recv)
            self.assertEqual(received["event"], "new_message")
            self.assertEqual(received["payload"]["content"], "Private Hello")

            # verify DB persistence
            msgs = self.db.get_messages("user", u2["id"], limit=10)
            contents = [m["content"] for m in msgs]
            self.assertIn("Private Hello", contents)
        finally:
            s_recv.close(); c_recv.close()


if __name__ == "__main__":
    unittest.main()
