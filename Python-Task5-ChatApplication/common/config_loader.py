"""Load and validate application configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for the chat application."""

    host: str
    port: int
    database_path: str
    log_level: str = "INFO"
    max_payload_bytes: int = 10 * 1024 * 1024
    max_message_length: int = 4096
    rate_limit_per_second: int = 5
    rate_limit_burst: int = 10
    password_iterations: int = 100000


DEFAULT_CONFIG_PATH = Path("config.json")


def _require(value: Any, key: str, expected_type: type) -> Any:
    if not isinstance(value, expected_type):
        raise ValueError(f"Configuration field '{key}' must be of type {expected_type.__name__}.")
    return value


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    """Load the JSON config file and validate required fields."""

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8-sig") as handle:
        raw = json.load(handle)

    host = _require(raw.get("host"), "host", str)
    port = _require(raw.get("port"), "port", int)
    database_path = _require(raw.get("database_path"), "database_path", str)
    log_level = str(raw.get("log_level", "INFO"))
    max_payload_bytes = int(raw.get("max_payload_bytes", 10 * 1024 * 1024))
    max_message_length = int(raw.get("max_message_length", 4096))
    rate_limit_per_second = int(raw.get("rate_limit_per_second", 5))
    rate_limit_burst = int(raw.get("rate_limit_burst", 10))
    password_iterations = int(raw.get("password_iterations", 100000))

    if port <= 0 or port > 65535:
        raise ValueError("Configuration field 'port' must be between 1 and 65535.")
    if max_payload_bytes <= 0:
        raise ValueError("Configuration field 'max_payload_bytes' must be positive.")
    if max_message_length <= 0:
        raise ValueError("Configuration field 'max_message_length' must be positive.")
    if rate_limit_per_second <= 0:
        raise ValueError("Configuration field 'rate_limit_per_second' must be positive.")
    if rate_limit_burst <= 0:
        raise ValueError("Configuration field 'rate_limit_burst' must be positive.")
    if password_iterations < 10000:
        raise ValueError("Configuration field 'password_iterations' must be at least 10000.")

    return AppConfig(
        host=host,
        port=port,
        database_path=database_path,
        log_level=log_level,
        max_payload_bytes=max_payload_bytes,
        max_message_length=max_message_length,
        rate_limit_per_second=rate_limit_per_second,
        rate_limit_burst=rate_limit_burst,
        password_iterations=password_iterations,
    )
