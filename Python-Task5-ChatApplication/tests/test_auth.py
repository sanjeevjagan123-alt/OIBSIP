"""Unit tests for AuthManager and password hashing functions."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from common.protocol_constants import ERROR_INVALID_CREDENTIALS, ERROR_INVALID_REQUEST, ERROR_USER_EXISTS
from server.database.db import DatabaseManager
from server.logic.auth import AuthManager, hash_password, verify_password


class AuthLogicTests(unittest.TestCase):
    """Verify password hashing, verification, and authentication logic."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "test_auth.db"
        self.db = DatabaseManager(self.db_path)
        self.db.init_db()
        self.auth_manager = AuthManager(self.db, password_iterations=10000)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_hash_and_verify_password(self) -> None:
        raw_password = "SecretPassword123"
        hash_hex, salt_hex = hash_password(raw_password, iterations=10000)

        # Verification succeeds with correct password
        self.assertTrue(verify_password(raw_password, hash_hex, salt_hex, iterations=10000))

        # Verification fails with wrong password
        self.assertFalse(verify_password("WrongPassword123", hash_hex, salt_hex, iterations=10000))

    def test_unique_salts_generated(self) -> None:
        hash1, salt1 = hash_password("SamePassword", iterations=10000)
        hash2, salt2 = hash_password("SamePassword", iterations=10000)
        self.assertNotEqual(salt1, salt2)
        self.assertNotEqual(hash1, hash2)

    def test_register_user(self) -> None:
        # Successful registration
        success, err_code, err_msg, user_info = self.auth_manager.register_user("alice", "Password123")
        self.assertTrue(success)
        self.assertIsNone(err_code)
        self.assertEqual(user_info["username"], "alice")

        # Duplicate registration fails
        success, err_code, err_msg, user_info = self.auth_manager.register_user("Alice", "Password123")
        self.assertFalse(success)
        self.assertEqual(err_code, ERROR_USER_EXISTS)

    def test_register_user_invalid_input(self) -> None:
        # Username too short
        success, err_code, _, _ = self.auth_manager.register_user("ab", "Password123")
        self.assertFalse(success)
        self.assertEqual(err_code, ERROR_INVALID_REQUEST)

        # Password too short
        success, err_code, _, _ = self.auth_manager.register_user("valid_user", "123")
        self.assertFalse(success)
        self.assertEqual(err_code, ERROR_INVALID_REQUEST)

    def test_authenticate_user(self) -> None:
        self.auth_manager.register_user("bob_builder", "SecurePass123")

        # Successful login
        success, err_code, err_msg, user_info = self.auth_manager.authenticate_user("bob_builder", "SecurePass123")
        self.assertTrue(success)
        self.assertIsNone(err_code)
        self.assertEqual(user_info["username"], "bob_builder")

        # Wrong password
        success, err_code, err_msg, _ = self.auth_manager.authenticate_user("bob_builder", "WrongPass123")
        self.assertFalse(success)
        self.assertEqual(err_code, ERROR_INVALID_CREDENTIALS)

        # Non-existent user
        success, err_code, err_msg, _ = self.auth_manager.authenticate_user("charlie", "SecurePass123")
        self.assertFalse(success)
        self.assertEqual(err_code, ERROR_INVALID_CREDENTIALS)


if __name__ == "__main__":
    unittest.main()
