import argparse
import time
import sqlite3
import bcrypt
import queue
from concurrent import futures

import grpc
import chat_pb2
import chat_pb2_grpc

# ----- Database Setup (using SQLite) -----
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

# Global dictionary to store active subscription queues for instant delivery.
active_subscriptions = {}

# ----- Helper Function -----
def log_message_size(sender, recipient, message):
    sender_bytes = len(sender.encode("utf-8"))
    recipient_bytes = len(recipient.encode("utf-8"))
    message_bytes = len(message.encode("utf-8"))
    total_size = sender_bytes + recipient_bytes + message_bytes
    print(f"Message Size: {total_size} bytes | {sender} -> {recipient}: {message}")

class ChatServiceServicer(chat_pb2_grpc.ChatServiceServicer):

    def CreateAccount(self, request, context):
        username = request.username
        password = request.password
        if not username or not password:
            return chat_pb2.CreateAccountResponse(success=False, message="Username and password required")
        
        # Hash password using bcrypt
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        try:
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
            conn.commit()
            return chat_pb2.CreateAccountResponse(success=True, message="Registration successful")
        except sqlite3.IntegrityError:
            return chat_pb2.CreateAccountResponse(success=False, message="Username already exists")

    def Login(self, request, context):
        username = request.username
        password = request.password
        if not username or not password:
            return chat_pb2.LoginResponse(success=False, message="Username and password required", unread_messages=0)
        
        cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        if result and bcrypt.checkpw(password.encode("utf-8"), result[0]):
            # Do not mark as online here; instant delivery only works if the client subscribes.
            cursor.execute("SELECT COUNT(*) FROM messages WHERE recipient = ? AND delivered = 0", (username,))
            unread_count = cursor.fetchone()[0]
            return chat_pb2.LoginResponse(success=True, message="Login successful", unread_messages=unread_count)
        else:
            return chat_pb2.LoginResponse(success=False, message="Invalid username or password", unread_messages=0)

    def Logout(self, request, context):
        username = request.username
        # Remove subscription if it exists.
        if username in active_subscriptions:
            del active_subscriptions[username]
            return chat_pb2.LogoutResponse(success=True, message="Logged out successfully")
        else:
            return chat_pb2.LogoutResponse(success=False, message="User not subscribed to instant messages")

    def SendMessage(self, request, context):
        sender = request.sender
        recipient = request.to
        message_text = request.message
        if not sender or not recipient or not message_text:
            return chat_pb2.SendMessageResponse(success=False, message="Missing sender, recipient, or message")

        # Insert the message into the database with delivered flag = 0.
        cursor.execute(
            "INSERT INTO messages (sender, recipient, message, delivered) VALUES (?, ?, ?, 0)",
            (sender, recipient, message_text)
        )
        conn.commit()
        log_message_size(sender, recipient, message_text)

        # Check if the recipient has an active subscription for instant delivery.
        if recipient in active_subscriptions:
            # Mark this message as delivered.
            message_id = cursor.lastrowid
            cursor.execute("UPDATE messages SET delivered = 1 WHERE id = ?", (message_id,))
            conn.commit()
            # Create a ChatMessage object to send instantly.
            chat_msg = chat_pb2.ChatMessage(
                id=message_id,
                sender=sender,
                to=recipient,
                message=message_text,
                timestamp=int(time.time())
            )
            # Push the message into the recipient's subscription queue.
            active_subscriptions[recipient].put(chat_msg)
            return chat_pb2.SendMessageResponse(success=True, message="Message delivered instantly")
        else:
            # The recipient is not actively subscribed; message remains for offline retrieval.
            return chat_pb2.SendMessageResponse(success=True, message="Message stored for offline delivery")

    def ReadMessages(self, request, context):
        """
        Retrieves unread (undelivered) messages for a given user, up to a specified limit.
        Once retrieved, the messages are marked as delivered.
        """
        username = request.username
        limit = request.count if request.count > 0 else 10

        if not username:
            return chat_pb2.ReadMessagesResponse(messages=[])

        # Retrieve unread messages for the user.
        cursor.execute(
            "SELECT id, sender, message, timestamp FROM messages WHERE recipient = ? AND delivered = 0 ORDER BY id ASC LIMIT ?",
            (username, limit)
        )
        messages = cursor.fetchall()
        message_ids = [msg[0] for msg in messages]
        if message_ids:
            placeholders = ",".join("?" for _ in message_ids)
            cursor.execute(f"UPDATE messages SET delivered = 1 WHERE id IN ({placeholders})", message_ids)
            conn.commit()

        message_list = []
        for msg in messages:
            # Convert the stored timestamp (a string, e.g., "2025-02-26 12:35:00") to epoch.
            try:
                ts_epoch = int(time.mktime(time.strptime(msg[3], "%Y-%m-%d %H:%M:%S")))
            except Exception:
                ts_epoch = 0  # Fallback if conversion fails.
            chat_msg = chat_pb2.ChatMessage(
                id=msg[0],
                sender=msg[1],
                to=username,
                message=msg[2],
                timestamp=ts_epoch
            )
            message_list.append(chat_msg)
        return chat_pb2.ReadMessagesResponse(messages=message_list)

    def SubscribeMessages(self, request, context):
        """
        Server-streaming RPC that registers an instant-delivery subscription for the user.
        Only messages sent while the user is subscribed will be pushed instantly.
        """
        username = request.username
        print(f"User {username} subscribed for instant messages.")
        # Create a subscription queue for this user.
        sub_queue = queue.Queue()
        active_subscriptions[username] = sub_queue

        try:
            while context.is_active():
                try:
                    chat_msg = sub_queue.get(timeout=1)
                    yield chat_msg
                except queue.Empty:
                    continue
        finally:
            if username in active_subscriptions:
                del active_subscriptions[username]

    def ListAccounts(self, request, context):
        pattern = request.pattern if request.pattern else "%"
        pattern = f"%{pattern}%"
        cursor.execute("SELECT username FROM users WHERE username LIKE ?", (pattern,))
        accounts = [row[0] for row in cursor.fetchall()]
        return chat_pb2.ListAccountsResponse(accounts=accounts)

    def ListMessages(self, request, context):
        username = request.username
        if not username:
            return chat_pb2.ListMessagesResponse(messages=[])
        
        cursor.execute(
        "SELECT id, sender, message, timestamp, delivered FROM messages WHERE recipient = ? ORDER BY id ASC",
        (username,)
        )
        messages = cursor.fetchall()
        message_list = []
        for msg in messages:
            try:
                ts_epoch = int(time.mktime(time.strptime(msg[3], "%Y-%m-%d %H:%M:%S")))
            except Exception:
                ts_epoch = 0  # Fallback if parsing fails.
            chat_msg = chat_pb2.ChatMessage(
                id=msg[0],
                sender=msg[1],
                to=username,
                message=msg[2],
                timestamp=ts_epoch
            )
            message_list.append(chat_msg)
        return chat_pb2.ListMessagesResponse(messages=message_list)

    def DeleteMessages(self, request, context):
        username = request.username
        message_ids = request.message_ids
        if not username or not message_ids:
            return chat_pb2.DeleteMessagesResponse(success=False, message="Username and message IDs required")
        
        placeholders = ",".join("?" for _ in message_ids)
        query = f"DELETE FROM messages WHERE id IN ({placeholders}) AND recipient = ?"
        params = list(message_ids) + [username]
        cursor.execute(query, params)
        conn.commit()
        return chat_pb2.DeleteMessagesResponse(success=True, message="Messages deleted successfully")

    def DeleteAccount(self, request, context):
        username = request.username
        if not username:
            return chat_pb2.DeleteAccountResponse(success=False, message="Username required")
        
        # Delete all messages associated with the user.
        cursor.execute("DELETE FROM messages WHERE sender = ? OR recipient = ?", (username, username))
        # Delete the user.
        cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        # Remove any active subscription if present.
        if username in active_subscriptions:
            del active_subscriptions[username]
        return chat_pb2.DeleteAccountResponse(success=True, message="Account deleted successfully. You are now logged out.")

# ----- gRPC Server Starter -----
def serve(host, port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    chat_pb2_grpc.add_ChatServiceServicer_to_server(ChatServiceServicer(), server)
    binding_str = f"{host}:{port}"
    server.add_insecure_port(binding_str)
    print(f"gRPC chat server starting on {binding_str}...")
    server.start()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("Server shutting down...")
        server.stop(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="gRPC Chat Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Server IP address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=50051, help="Server port number (default: 50051)")
    args = parser.parse_args()

    serve(args.host, args.port)
