"""Client application entrypoint to launch the GUI-based chat client."""

from __future__ import annotations

import logging
import sys

from client.gui.app import ChatApp


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    app = ChatApp()
    try:
        app.run()
    except KeyboardInterrupt:
        app.shutdown()


if __name__ == "__main__":
    main()
