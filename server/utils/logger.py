"""Server logging utilities."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(level_name: str) -> logging.Logger:
    """Configure console and file logging for the server."""

    logger = logging.getLogger("chat_server")
    if logger.handlers:
        return logger

    level = getattr(logging, level_name.upper(), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    log_path = Path("server.log")
    file_handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.info("Logger initialized at %s level", level_name.upper())
    return logger
