
# Project Title: Chat App with Replication
## By Alex Geng and Carl Ma
## Engineering Notebook for Replication Implementation
📔 [https://docs.google.com/document/d/1w9PmqjK77rJCrC0eqTVDdmDO3WythQmmjYu8MH-yuvc/edit?usp=sharing]












# Project Title: Customized Wiring Protocol
## By Alex Geng and Carl Ma

## Engineering Notebook for Wiring Protocol
📔 [View the Engineering Notebook on Google Docs](https://docs.google.com/document/d/1t55yTAW73h1h-Jwun9jXmagnJGOjMwCCPUcAQvqWMWk/edit?usp=sharing)

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


Comparison and Results

We find that binary messages are always smaller than JSON messages, with shorter messages benefitting the most from binary encoding. This is because as messages increase in length, JSON overhead becomes less significant.

| Message Length | JSON Size (bytes) | Binary Size (bytes) | Size Reduction (%) |
|---------------|------------------|-------------------|------------------|
| 3 chars      | 76 bytes         | 17 bytes         | 77.63% smaller  |
| 19 chars     | 92 bytes         | 33 bytes         | 64.13% smaller  |
| 44 chars     | 117 bytes        | 58 bytes         | 50.43% smaller  |
| 144 chars    | 217 bytes        | 158 bytes        | 27.19% smaller  |
| 276 chars    | 349 bytes        | 290 bytes        | 16.91% smaller  |


JSON overhead occurs because of text-based formatting, with keys ("command", "sender", "message") and extra characters ("{}", ":", "). Even a single-word message ("Hi!") takes 76 bytes in JSON. Binary encoding packs data more efficiently, without the need for headers.

With respect to efficiency and scalability, binary is highly efficient, saving bandwidth and improving latency. However, JSON is more human-readable and easier to debug. Thus, for efficiency purposes and low-latency messaging systems, binary is preferred, but for debugging and extensibility purposes (APIs, web-based messaging when human readability is preferred), JSON is the way to go.
