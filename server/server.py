import socket
import selectors
import sqlite3
import json
import bcrypt
import types

# Initialize selector for handling multiple clients
sel = selectors.DefaultSelector()

# Database connection
conn = sqlite3.connect("chat.db", check_same_thread=False)
cursor = conn.cursor()

# Create users table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash BLOB NOT NULL
    )
''')

# Create messages table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT NOT NULL,
        recipient TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        delivered INTEGER DEFAULT 0
    )
''')

conn.commit()

# Store online clients
clients = {}

# ---------------------------- Helper Functions ----------------------------
def send_response(sock, response):
    """Send a JSON response to the client."""
    sock.sendall(json.dumps(response).encode("utf-8"))

def handle_register(client_socket, request):
    """Handles user registration."""
    username = request.get("username")
    password = request.get("password")

    if not username or not password:
        send_response(client_socket, {"status": "error", "message": "Username and password required"})
        return

    # Hash password
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    try:
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
        conn.commit()
        send_response(client_socket, {"status": "success", "message": "Registration successful"})
    except sqlite3.IntegrityError:
        send_response(client_socket, {"status": "error", "message": "Username already exists"})

def handle_login(client_socket, request):
    """Handles user login."""
    username = request.get("username")
    password = request.get("password")

    if not username or not password:
        send_response(client_socket, {"status": "error", "message": "Username and password required"})
        return

    cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()

    if result and bcrypt.checkpw(password.encode("utf-8"), result[0]):
        clients[username] = client_socket  # Store client as online

        # Check unread messages
        cursor.execute("SELECT COUNT(*) FROM messages WHERE recipient = ? AND delivered = 0", (username,))
        unread_count = cursor.fetchone()[0]

        send_response(client_socket, {
            "status": "success",
            "message": "Login successful",
            "unread_messages": unread_count
        })
    else:
        send_response(client_socket, {"status": "error", "message": "Invalid username or password"})

def handle_send_message(client_socket, request):
    """Handles sending a message, storing it in the database, and delivering instantly if the recipient is online."""
    sender = request.get("sender")
    recipient = request.get("recipient")
    message = request.get("message")

    if not sender or not recipient or not message:
        send_response(client_socket, {"status": "error", "message": "Missing sender, recipient, or message"})
        return

    # Store message in SQLite
    cursor.execute("INSERT INTO messages (sender, recipient, message, delivered) VALUES (?, ?, ?, 0)", 
                   (sender, recipient, message))
    conn.commit()

    # If recipient is online, deliver immediately
    if recipient in clients:
        send_response(clients[recipient], {"type": "message", "from": sender, "message": message})

    send_response(client_socket, {"status": "success", "message": "Message stored and delivered if recipient is online"})

def handle_read_messages(client_socket, request):
    """Retrieves undelivered messages, allowing users to specify how many they want."""
    username = request.get("username")
    limit = int(request.get("limit", 10))  # Default: 10 messages

    if not username:
        send_response(client_socket, {"status": "error", "message": "Username required"})
        return

    cursor.execute("SELECT id, sender, message, timestamp FROM messages WHERE recipient = ? AND delivered = 0 ORDER BY id ASC LIMIT ?", 
                   (username, limit))
    messages = cursor.fetchall()

    # Mark retrieved messages as delivered
    message_ids = [msg[0] for msg in messages]
    if message_ids:
        cursor.execute(f"UPDATE messages SET delivered = 1 WHERE id IN ({','.join(['?']*len(message_ids))})", message_ids)
        conn.commit()

    # Format messages to send to client
    message_list = [{"id": msg[0], "from": msg[1], "message": msg[2], "timestamp": msg[3]} for msg in messages]

    send_response(client_socket, {"status": "success", "messages": message_list})


def handle_list_accounts(client_socket, request):
    """Handles listing accounts with optional pattern matching."""
    pattern = request.get("pattern", "%")  # Default: show all accounts
    pattern = f"%{pattern}%"  # Wildcard search

    cursor.execute("SELECT username FROM users WHERE username LIKE ?", (pattern,))
    accounts = [row[0] for row in cursor.fetchall()]

    send_response(client_socket, {"status": "success", "accounts": accounts})


# ---------------------------- Socket Server ----------------------------
def accept_wrapper(sock):
    """Accept new client connections."""
    conn, addr = sock.accept()
    print(f"Accepted connection from {addr}")
    conn.setblocking(False)
    
    data = types.SimpleNamespace(addr=addr, inb=b"", outb=b"")
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    sel.register(conn, events, data=data)

def service_connection(key, mask):
    """Handles client communication."""
    sock = key.fileobj
    data = key.data

    if mask & selectors.EVENT_READ:
        recv_data = sock.recv(1024)
        if not recv_data:
            print(f"Client {data.addr} disconnected.")
            sel.unregister(sock)
            sock.close()
            return

        request = json.loads(recv_data.decode("utf-8"))

        # Handle client request
        command = request.get("command")
        if command == "REGISTER":
            handle_register(sock, request)
        elif command == "LOGIN":
            handle_login(sock, request)
        elif command == "SEND":
            handle_send_message(sock, request)
        elif command == "READ":
            handle_read_messages(sock, request)
        elif command == "LIST":  # 🆕 Add handling for "LIST" command
            handle_list_accounts(sock, request)

if __name__ == "__main__":
    # Start server
    lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lsock.bind(("127.0.0.1", 54400))
    lsock.listen()
    print("Server listening on 127.0.0.1:54400")
    
    lsock.setblocking(False)
    sel.register(lsock, selectors.EVENT_READ, data=None)

    try:
        while True:
            events = sel.select(timeout=None)
            for key, mask in events:
                if key.data is None:
                    accept_wrapper(key.fileobj)
                else:
                    service_connection(key, mask)
    except KeyboardInterrupt:
        print("Server shutting down")
    finally:
        sel.close()
