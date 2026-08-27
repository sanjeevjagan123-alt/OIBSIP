"""Server application entry point."""

from __future__ import annotations

from common.config_loader import load_config
from server.core.server import ChatServer
from server.utils.logger import setup_logger


def main() -> None:
    """Start the chat server using the configured host and port."""

    config = load_config()
    logger = setup_logger(config.log_level)
    server = ChatServer(config=config, logger=logger)
    server.run()


if __name__ == "__main__":
    main()
