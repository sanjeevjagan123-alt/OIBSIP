"""Authentication business logic, password hashing, and user credential verification."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
from typing import Any

from common.protocol_constants import (
    ERROR_INVALID_CREDENTIALS,
    ERROR_INVALID_REQUEST,
    ERROR_USER_EXISTS,
)
from server.database.db import DatabaseManager

USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,30}$")


def hash_password(password: str, salt: bytes | None = None, iterations: int = 100000) -> tuple[str, str]:
    """Derive a PBKDF2-HMAC-SHA256 password hash with a salt. Returns (hash_hex, salt_hex)."""
    if salt is None:
        salt = os.urandom(16)
    derived_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return derived_key.hex(), salt.hex()


def verify_password(password: str, stored_hash_hex: str, stored_salt_hex: str, iterations: int = 100000) -> bool:
    """Verify a plaintext password against a stored PBKDF2 hash and salt in constant time."""
    salt = bytes.fromhex(stored_salt_hex)
    computed_hash_hex, _ = hash_password(password, salt=salt, iterations=iterations)
    return secrets.compare_digest(computed_hash_hex, stored_hash_hex)


class AuthManager:
    """Manages user registration and authentication logic."""

    def __init__(self, db: DatabaseManager, password_iterations: int = 100000) -> None:
        self.db = db
        self.password_iterations = password_iterations

    def validate_username(self, username: str) -> str | None:
        """Validate username syntax."""
        if not username or not isinstance(username, str):
            return "Username cannot be empty."
        username = username.strip()
        if not USERNAME_REGEX.match(username):
            return "Username must be 3-30 alphanumeric characters or underscores."
        return None

    def validate_password(self, password: str) -> str | None:
        """Validate password requirements."""
        if not password or not isinstance(password, str):
            return "Password cannot be empty."
        if len(password) < 6:
            return "Password must be at least 6 characters long."
        return None

    def register_user(self, username: str, password: str) -> tuple[bool, str | None, str | None, dict[str, Any] | None]:
        """Register a new user. Returns (success, error_code, error_message, user_info)."""
        username_err = self.validate_username(username)
        if username_err:
            return False, ERROR_INVALID_REQUEST, username_err, None

        password_err = self.validate_password(password)
        if password_err:
            return False, ERROR_INVALID_REQUEST, password_err, None

        username = username.strip()
        existing_user = self.db.get_user_by_username(username)
        if existing_user is not None:
            return False, ERROR_USER_EXISTS, f"Username '{username}' is already taken.", None

        hash_hex, salt_hex = hash_password(password, iterations=self.password_iterations)
        try:
            created_user = self.db.create_user(username, hash_hex, salt_hex)
            return True, None, None, created_user
        except ValueError as exc:
            return False, ERROR_USER_EXISTS, str(exc), None

    def authenticate_user(self, username: str, password: str) -> tuple[bool, str | None, str | None, dict[str, Any] | None]:
        """Authenticate user credentials. Returns (success, error_code, error_message, user_info)."""
        if not username or not password or not isinstance(username, str) or not isinstance(password, str):
            return False, ERROR_INVALID_CREDENTIALS, "Invalid username or password.", None

        user = self.db.get_user_by_username(username.strip())
        if user is None:
            return False, ERROR_INVALID_CREDENTIALS, "Invalid username or password.", None

        if not verify_password(password, user["password_hash"], user["salt"], iterations=self.password_iterations):
            return False, ERROR_INVALID_CREDENTIALS, "Invalid username or password.", None

        user_info = {
            "user_id": user["id"],
            "username": user["username"],
        }
        return True, None, None, user_info
