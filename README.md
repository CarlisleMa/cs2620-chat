# Chat Server and Client Implementations (JSON and Binary Protocol)

This repository contains two separate implementations of a simple chat application:

1. **JSON-based** client–server pair (`server.py`, `client.py`).
2. **Binary (custom wire protocol)** client–server pair (`server_binary.py`, `client_binary.py`).

Both implementations store user data and messages in an SQLite database, but they differ in how the client–server communication is structured and how data is serialized and transmitted.

---

## Table of Contents

1. [Overview](#overview)  
2. [Features](#features)  
3. [JSON Implementation](#json-implementation)  
   - [Server (server.py)](#serverpy)  
   - [Client (clientpy)](#clientpy)  
4. [Binary Implementation](#binary-implementation)  
   - [Server (server_binary.py)](#server_binarypy)  
   - [Client (client_binary.py)](#client_binarypy)  
5. [Installation and Setup](#installation-and-setup)  
6. [Usage](#usage)  
   - [JSON Chat Usage](#json-chat-usage)  
   - [Binary Chat Usage](#binary-chat-usage)  
7. [Data Size Logging](#data-size-logging)  
8. [Comparison Notes](#comparison-notes)  
9. [License](#license)

---

## Overview

- **Purpose**: Demonstrate two ways of building a simple chat service—one using human-readable JSON messages and another using a custom binary protocol.  
- **Persistence**: Both servers use SQLite to store user credentials and messages.
- **Concurrency**: Both servers utilize Python’s `selectors` module to handle multiple client connections efficiently.

---

## Features

- **User Registration**: Create an account with a username and password (stored securely using `bcrypt` in the JSON server).
- **User Login**: Authenticate existing users.
- **Send Messages**: Send messages to online or offline users; offline messages are stored and delivered when the user logs in.
- **Read Messages**: Retrieve undelivered (unread) messages or list all messages.
- **List Accounts** (JSON only): Search for user accounts by pattern.
- **Delete Messages** (JSON only): Select which messages to remove.
- **Delete Account** (JSON only): Permanently remove your account and all associated data.
- **Graceful Exit**: Log out and disconnect from the server cleanly.

---

## JSON Implementation

### `server.py`

- **Runs on** `127.0.0.1:54400` by default.
- **Uses JSON**: Expects each request from the client to be a JSON object with a newline terminator.
- **Commands** (keys in the JSON object):
  1. `REGISTER`
  2. `LOGIN`
  3. `SEND`
  4. `READ`
  5. `LIST`
  6. `LIST_MESSAGES`
  7. `DELETE`
  8. `DELETE_ACCOUNT`
  9. `EXIT`
- **Database**:
  - `users` table: `username`, `password_hash`
  - `messages` table: `sender`, `recipient`, `message`, `timestamp`, `delivered`
- **Selector-based concurrency**: Accepts multiple client connections using `select`.

### `client.py`

- Connects to `127.0.0.1:54400`.
- Prompts the user for **Register** or **Login** initially.
- Once logged in, the user can type commands (`SEND`, `READ`, `LIST`, etc.) to interact with the server.
- **Real-time message push**: A background thread listens for incoming messages; if a `"type":"message"` JSON object arrives, it prints immediately.
- **Data Size Logging**:  
  - Keeps track of **bytes sent** and **bytes received** for each JSON message transmission.  
  - A final summary is printed upon client exit.

---

## Binary Implementation

### `server_binary.py`

- **Runs on** `127.0.0.1:54401`.
- **Custom Wire Protocol**:  
  - Each message is prefixed by a **3-byte header**: `[sender_len, recipient_len, message_len]` (each is 1 byte).  
  - Followed by the **sender**, **recipient**, and **message** in raw bytes.
- **Storing Messages**: Uses the same `chat.db` with the same schema as the JSON server.
- **On Receipt**:  
  - If the recipient is currently connected (`clients[recipient]`), the server immediately forwards the message.  
  - Otherwise, the message is stored for later delivery.

### `client_binary.py`

- Connects to `127.0.0.1:54401`.
- **Sends messages** using `struct.pack` for the header:
  ```python
  header = struct.pack("!BBB", len(sender_bytes), len(recipient_bytes), len(message_bytes))
  payload = header + sender_bytes + recipient_bytes + message_bytes
  sock.sendall(payload)
