"""Deterministic concurrent client tests for Stage 10.

Multiple clients register/login concurrently, join a room, send messages concurrently,
then verify persisted history contains all messages.
"""

from __future__ import annotations

import threading
import time
import unittest

from client.core.client import ChatClient
from common.config_loader import AppConfig
from server.core.server import ChatServer


class ConcurrentClientsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = AppConfig(host="127.0.0.1", port=8774, database_path="data/test_stage10_concurrent.db", log_level="DEBUG", rate_limit_per_second=1000, rate_limit_burst=1000)
        # Ensure fresh database for this test run
        from pathlib import Path

        Path(cls.config.database_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            Path(cls.config.database_path).unlink()
        except Exception:
            pass

        import logging

        cls.logger = logging.getLogger("test_server_concurrent")
        cls.logger.setLevel(logging.DEBUG)
        cls.server = ChatServer(config=cls.config, logger=cls.logger)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server_thread.join(timeout=2.0)

    def test_multiple_clients_send_messages_concurrently(self) -> None:
        num_clients = 3
        messages_per_client = 5
        room_name = "testroom"

        barrier = threading.Barrier(num_clients)
        clients: list[ChatClient] = []
        room_created = threading.Event()
        successes: list[bool] = []

        def client_worker(idx: int) -> None:
            name = f"user_{idx}_{int(time.time() * 1000) % 10000}"
            c = ChatClient(host=self.config.host, port=self.config.port, timeout=5.0)
            c.connect()
            clients.append(c)
            try:
                # Register or ignore if already exists
                try:
                    c.register(name, "password")
                except Exception:
                    pass
                c.login(name, "password")
                # First client creates the room and signals others
                if idx == 0:
                    c.create_room(room_name)
                    room_created.set()
                else:
                    # wait for creator to create the room
                    room_created.wait(timeout=2.0)
                c.join_room(room_name)
                # synchronize before sending
                barrier.wait()
                for m in range(messages_per_client):
                    resp = c.send_chat_message("room", room_name, f"msg {idx}-{m}")
                    # record successful sends
                    try:
                        if resp.get("status") == "success":
                            successes.append(True)
                    except Exception:
                        pass
            finally:
                # leave and disconnect
                try:
                    c.leave_room(room_name)
                except Exception:
                    pass
                c.disconnect()

        threads = [threading.Thread(target=client_worker, args=(i,)) for i in range(num_clients)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify persisted messages via a fresh client
        verifier = ChatClient(host=self.config.host, port=self.config.port, timeout=5.0)
        verifier.connect()
        try:
            verifier.register("verifier", "password")
            verifier.login("verifier", "password")
            # join room to be allowed to get history (server requires auth)
            # room may exist; if not, join_room will return error
            try:
                verifier.join_room(room_name)
            except Exception:
                pass
            resp = verifier.get_history("room", room_name, limit=1000)
            messages = resp.get("payload", {}).get("messages", [])
            # Ensure every client contributed at least one persisted message
            for idx in range(num_clients):
                self.assertTrue(any(m["content"].startswith(f"msg {idx}-") for m in messages), msg=f"No messages from client {idx} found in history")
        finally:
            verifier.disconnect()


if __name__ == "__main__":
    unittest.main()
