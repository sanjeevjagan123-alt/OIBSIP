# Oasis Chat Application

A lightweight, multi-client chat application built with Python, socket programming, and CustomTkinter.

## Features

- **User Authentication**: Secure registration and login with salted PBKDF2 password hashing.
- **Chat Rooms & Direct Messaging**: Public room channels and private user-to-user messaging.
- **Message History & Search**: Searchable chat history backed by SQLite database storage.
- **Delivery Receipts & Typing Indicators**: Real-time typing indicators and message delivery acknowledgments.
- **Desktop Notifications**: Background desktop notifications for incoming messages using `plyer`.
- **Emoji Support**: Textual shortcodes automatically converted to Unicode emojis.
- **Rate Limiting**: Server-side request throttling to protect against flooding.

## Project Structure

```text
├── client/
│   ├── core/           # TCP client protocol & listener loop
│   └── gui/            # CustomTkinter GUI application
├── server/
│   ├── core/           # Multi-threaded TCP server & client handler
│   ├── database/       # SQLite schema & persistence logic
│   └── logic/          # Authentication, room management & rate limiting
├── common/             # Stream framing, protocol constants & config loader
├── tests/              # Comprehensive automated integration & unit tests
└── data/               # SQLite database storage (chat_app.db)
```

## Getting Started

### Prerequisites

- Python 3.10+
- Dependencies: `customtkinter`, `plyer`

```powershell
pip install customtkinter plyer
```

### Running the Server

```powershell
python -m server.main
```

### Running the GUI Client

```powershell
python -m client.main
```

## Data Storage & Security

**Storage:**
- User credentials are hashed using PBKDF2-HMAC-SHA256 with a unique random salt per user (100,000 iterations). Plaintext passwords are never stored.
- Chat messages (room and direct) are stored in a local SQLite database (`data/chat_app.db`), including sender, recipient/room, content, and timestamp.
- Message delivery state (`sent`/`delivered`) is tracked per message.

**What is NOT encrypted:**
- Message content is stored in the database in **plaintext**. Anyone with direct file access to the SQLite database can read all chat history.
- Data sent over the network between client and server is **not encrypted** — it uses plain TCP with a JSON-based application protocol, not TLS/SSL. On a shared or untrusted network, traffic could be intercepted and read.
- This project is intended for local/educational use (e.g., localhost or trusted LAN). It is **not suitable for production use** without adding TLS for transport security and encryption-at-rest for stored messages.

**What IS protected:**
- Passwords (hashed + salted, never stored or transmitted in plaintext beyond the initial login request)
- Per-user access control on direct messages (a user cannot read DMs they weren't part of)
- Rate limiting to prevent request flooding
