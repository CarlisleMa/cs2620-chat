# server_binary.py
import socket
import selectors
import sqlite3
import struct
import types

sel = selectors.DefaultSelector()

# Same DB as before
conn = sqlite3.connect("chat.db", check_same_thread=False)
cursor = conn.cursor()

# In case your tables are not yet created; otherwise no effect:
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash BLOB NOT NULL
    )
''')
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

# Track who is online (by username → socket). This is optional.
clients = {}

def handle_binary_message(sock):
    """
    Continuously reads messages in a custom binary format:
    
    1. 3 bytes for sender_len, recipient_len, message_len (BBB).
    2. Then read `sender_len` bytes for sender
    3. Then `recipient_len` bytes for recipient
    4. Then `message_len` bytes for the message
    """
    try:
        while True:
            # Try reading the 3-byte header
            header = sock.recv(3)
            if not header:
                # No more data; client disconnected
                return
            
            # Unpack lengths (3 bytes total for B, B, B)
            sender_len, recipient_len, message_len = struct.unpack("!BBB", header)
            
            # Read the sender
            sender_bytes = sock.recv(sender_len)
            sender = sender_bytes.decode("utf-8")
            
            # Read the recipient
            recipient_bytes = sock.recv(recipient_len)
            recipient = recipient_bytes.decode("utf-8")
            
            # Read the message
            message_bytes = sock.recv(message_len)
            message = message_bytes.decode("utf-8")
            
            print(f"Received from {sender} -> {recipient}: {message}")
            
            # Store in DB
            cursor.execute("""
                INSERT INTO messages (sender, recipient, message, delivered)
                VALUES (?, ?, ?, 0)
            """, (sender, recipient, message))
            conn.commit()
            
            # If the recipient is online, send immediate notification
            if recipient in clients:
                clients[recipient].sendall(f"[{sender}] {message}".encode("utf-8"))

    except Exception as e:
        print(f"Error reading binary message: {e}")


def accept_wrapper(sock):
    conn, addr = sock.accept()
    print(f"Accepted binary connection from {addr}")
    conn.setblocking(False)
    
    # We don't keep extra state since we read everything in handle_binary_message
    data = types.SimpleNamespace(addr=addr)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    sel.register(conn, events, data=data)

def service_connection(key, mask):
    sock = key.fileobj
    data = key.data

    if mask & selectors.EVENT_READ:
        # We'll call our binary handler
        recv_data = sock.recv(1, socket.MSG_PEEK)
        if not recv_data:
            # Disconnected
            print(f"Client {data.addr} disconnected.")
            sel.unregister(sock)
            sock.close()
            return

        # We "push back" the byte by not actually consuming it here,
        # and instead letting handle_binary_message read everything fully
        handle_binary_message(sock)

if __name__ == "__main__":
    lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lsock.bind(("127.0.0.1", 54401))
    lsock.listen()
    print("Binary Server listening on 127.0.0.1:54401")
    
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
        print("Binary server shutting down")
    finally:
        sel.close()
