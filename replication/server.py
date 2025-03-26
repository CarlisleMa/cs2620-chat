import argparse
import time
import sqlite3
import bcrypt
import queue
from concurrent import futures

import grpc
import chat_pb2
import chat_pb2_grpc

import threading
import time
import json


# ----- Helper Function -----
def log_message_size(sender, recipient, message):
    sender_bytes = len(sender.encode("utf-8"))
    recipient_bytes = len(recipient.encode("utf-8"))
    message_bytes = len(message.encode("utf-8"))
    total_size = sender_bytes + recipient_bytes + message_bytes
    print(f"Message Size: {total_size} bytes | {sender} -> {recipient}: {message}")

class ChatServer(chat_pb2_grpc.ChatServiceServicer, chat_pb2_grpc.ReplicationServiceServicer):
    def __init__(self, server_id, address, config_file="config.json"):
        self.id = server_id
        self.address = address
        with open(config_file, "r") as f:  # Use config_file here
            config_data = json.load(f)    # Assign loaded JSON to config_data
        self.all_servers = {server["id"]: server["address"] for server in config_data["servers"]}
        self.peers = [addr for sid, addr in self.all_servers.items() if sid != self.id]
        self.is_leader = False
        self.leader_address = None  # Initially unknown
        self.alive_peers = {peer: 0 for peer in self.peers}  # Last heartbeat timestamp
        self.conn = sqlite3.connect(f"chat_db_{server_id}.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.active_subscriptions = {}  # Only leader uses this
        # Initialize database (move schema creation here if not already done globally)

        # Database setup
        self.conn = sqlite3.connect(f"chat_db_{server_id}.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Create tables
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash BLOB NOT NULL
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                delivered INTEGER DEFAULT 0
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sequence (
                name TEXT PRIMARY KEY,
                value INTEGER
            )
        ''')
        self.conn.commit()

    def start(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        chat_pb2_grpc.add_ChatServiceServicer_to_server(self, server)
        chat_pb2_grpc.add_ReplicationServiceServicer_to_server(self, server)
        server.add_insecure_port(self.address)
        print(f"Server {self.id} starting on {self.address}...")
        server.start()
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()
        try:
            server.wait_for_termination()
        except KeyboardInterrupt:
            print("Server shutting down...")
            server.stop(0)

    def heartbeat_loop(self):
        while True:
            # Send heartbeats
            for peer in self.peers:
                try:
                    with grpc.insecure_channel(peer) as channel:
                        stub = chat_pb2_grpc.ReplicationServiceStub(channel)
                        stub.Heartbeat(chat_pb2.HeartbeatRequest(sender_address=self.address), timeout=1)
                except:
                    pass
            # Check leader status
            if self.leader_address:
                if self.leader_address == self.address:
                    self.is_leader = True
                elif time.time() - self.alive_peers.get(self.leader_address, 0) > 3:  # 3s timeout
                    self.initiate_election()
            else:
                self.initiate_election()
            time.sleep(1)

    def initiate_election(self):
        higher_peers = [p for p in self.peers if int(p.split(':')[-1]) - 50050 > self.id]
        if not higher_peers:
            self.become_leader()
            return
        any_higher_alive = False
        for peer in higher_peers:
            try:
                with grpc.insecure_channel(peer) as channel:
                    stub = chat_pb2_grpc.ReplicationServiceStub(channel)
                    response = stub.RequestElection(chat_pb2.ElectionRequest(sender_address=self.address), timeout=1)
                    if response.ok:
                        any_higher_alive = True
                        break
            except:
                pass
        if not any_higher_alive:
            self.become_leader()

    def become_leader(self):
        self.is_leader = True
        self.leader_address = self.address
        print(f"Server {self.id} elected as leader at {self.address}")
        self.synchronize_database()
        for peer in self.peers:
            try:
                with grpc.insecure_channel(peer) as channel:
                    stub = chat_pb2_grpc.ReplicationServiceStub(channel)
                    stub.SetLeader(chat_pb2.SetLeaderRequest(leader_address=self.address), timeout=1)
            except:
                pass

    def synchronize_database(self):
        users = set()
        messages = set()
        acks = 0
        for peer in self.peers:
            try:
                with grpc.insecure_channel(peer) as channel:
                    stub = chat_pb2_grpc.ChatServiceStub(channel)
                    response = stub.GetState(chat_pb2.GetStateRequest(), timeout=1)
                    for user in response.users:
                        users.add((user.username, user.password_hash))
                    for msg in response.messages:
                        messages.add((msg.id, msg.sender, msg.recipient, msg.message, msg.timestamp, msg.delivered))
                    acks += 1
                    if acks >= 2:
                        break
            except:
                pass
        if acks >= 2:
            for user in users:
                self.cursor.execute("INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)", user)
            for msg in messages:
                self.cursor.execute("INSERT OR IGNORE INTO messages (id, sender, recipient, message, timestamp, delivered) VALUES (?, ?, ?, ?, ?, ?)", msg)
            self.conn.commit()
            self.cursor.execute("SELECT COALESCE(MAX(id), 0) FROM messages")
            max_id = self.cursor.fetchone()[0]
            self.cursor.execute("INSERT OR REPLACE INTO sequence (name, value) VALUES ('message_id', ?)", (max_id + 1,))
            self.conn.commit()

    def apply_operation(self, operation):
        parts = operation.split(":")
        cmd = parts[0]
        if cmd == "CreateAccount":
            username, password_hash = parts[1], parts[2].encode()
            self.cursor.execute("INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
        elif cmd == "SendMessage":
                id, sender, recipient, message, timestamp = int(parts[1]), parts[2], parts[3], parts[4], int(parts[5])
                self.cursor.execute(
                    "INSERT OR IGNORE INTO messages (id, sender, recipient, message, timestamp, delivered) VALUES (?, ?, ?, ?, ?, 0)",
                    (id, sender, recipient, message, timestamp)
                )
        elif cmd == "DeleteMessages":
            recipient, message_ids = parts[1], [int(i) for i in parts[2].split(",")]
            placeholders = ",".join("?" for _ in message_ids)
            self.cursor.execute(f"DELETE FROM messages WHERE id IN ({placeholders}) AND recipient = ?", message_ids + [recipient])
        elif cmd == "DeleteAccount":
            username = parts[1]
            self.cursor.execute("DELETE FROM messages WHERE sender = ? OR recipient = ?", (username, username))
            self.cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        self.conn.commit()

    # ChatService Methods
    def CreateAccount(self, request, context):
        if not self.is_leader:
            return chat_pb2.CreateAccountResponse(success=False, message=f"Not leader, current leader is {self.leader_address}")
        operation = f"CreateAccount:{request.username}:{bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode()}"
        if self.replicate_operation(operation):
            self.apply_operation(operation)
            return chat_pb2.CreateAccountResponse(success=True, message="Registration successful")
        return chat_pb2.CreateAccountResponse(success=False, message="Failed to replicate")

    def Login(self, request, context):
        if not self.is_leader:
            return chat_pb2.LoginResponse(success=False, message=f"Not leader, current leader is {self.leader_address}", unread_messages=0)
        username = request.username
        password = request.password
        if not username or not password:
            return chat_pb2.LoginResponse(success=False, message="Username and password required", unread_messages=0)
        
        self.cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
        result = self.cursor.fetchone()
        if result and bcrypt.checkpw(password.encode("utf-8"), result[0]):
            # Do not mark as online here; instant delivery only works if the client subscribes.
            self.cursor.execute("SELECT COUNT(*) FROM messages WHERE recipient = ? AND delivered = 0", (username,))
            unread_count = self.cursor.fetchone()[0]
            return chat_pb2.LoginResponse(success=True, message="Login successful", unread_messages=unread_count)
        else:
            return chat_pb2.LoginResponse(success=False, message="Invalid username or password", unread_messages=0)

    def Logout(self, request, context):
        if not self.is_leader:
            return chat_pb2.LogoutResponse(success=False, message="Request must be sent to the leader")
        username = request.username
        # Remove subscription if it exists.
        if username in self.active_subscriptions:
            del self.active_subscriptions[username]
            return chat_pb2.LogoutResponse(success=True, message="Logged out successfully")
        else:
            return chat_pb2.LogoutResponse(success=False, message="User not subscribed to instant messages")

    def SendMessage(self, request, context):
        if not self.is_leader:
            return chat_pb2.SendMessageResponse(success=False, message=f"Not leader, current leader is {self.leader_address}")
        self.cursor.execute("INSERT OR REPLACE INTO sequence (name, value) VALUES ('message_id', COALESCE((SELECT value FROM sequence WHERE name = 'message_id'), 0) + 1)")
        self.cursor.execute("SELECT value FROM sequence WHERE name = 'message_id'")
        message_id = self.cursor.fetchone()[0]
        current_time = int(time.time())  # Get current Unix timestamp
        operation = f"SendMessage:{message_id}:{request.sender}:{request.to}:{request.message}:{current_time}"
        if self.replicate_operation(operation):
            self.apply_operation(operation)
            if request.to in self.active_subscriptions:
                chat_msg = chat_pb2.ChatMessage(id=message_id, sender=request.sender, to=request.to, message=request.message, timestamp=current_time)
                self.active_subscriptions[request.to].put(chat_msg)
                print(f"Server {self.id}: Pushed message {message_id} to {request.to}’s queue")
            else:
                print(f"Server {self.id}: No active subscription for {request.to}")
            return chat_pb2.SendMessageResponse(success=True, message="Message sent")
        return chat_pb2.SendMessageResponse(success=False, message="Failed to replicate")

    def ReadMessages(self, request, context):
        if not self.is_leader:
            return chat_pb2.ReadMessagesResponse(messages=[])
        """
        Retrieves unread (undelivered) messages for a given user, up to a specified limit.
        Once retrieved, the messages are marked as delivered.
        """
        username = request.username
        limit = request.count if request.count > 0 else 10

        if not username:
            return chat_pb2.ReadMessagesResponse(messages=[])

        # Retrieve unread messages for the user.
        self.cursor.execute(
            "SELECT id, sender, message, timestamp FROM messages WHERE recipient = ? AND delivered = 0 ORDER BY id ASC LIMIT ?",
            (username, limit)
        )
        messages = self.cursor.fetchall()
        message_ids = [msg[0] for msg in messages]
        if message_ids:
            placeholders = ",".join("?" for _ in message_ids)
            self.cursor.execute(f"UPDATE messages SET delivered = 1 WHERE id IN ({placeholders})", message_ids)
            self.conn.commit()

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
        if not self.is_leader:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details(f"Not leader, current leader is {self.leader_address}")
            return
        """
        Server-streaming RPC that registers an instant-delivery subscription for the user.
        Only messages sent while the user is subscribed will be pushed instantly.
        """
        username = request.username
        print(f"User {username} subscribed for instant messages.")
        # Create a subscription queue for this user.
        sub_queue = queue.Queue()
        self.active_subscriptions[username] = sub_queue

        try:
            while context.is_active():
                try:
                    chat_msg = sub_queue.get(timeout=1)
                    yield chat_msg
                except queue.Empty:
                    continue
        finally:
            if username in self.active_subscriptions:
                del self.active_subscriptions[username]

    def ListAccounts(self, request, context):
        if not self.is_leader:
            return chat_pb2.ListAccountsResponse(accounts=[])
        pattern = request.pattern if request.pattern else "%"
        pattern = f"%{pattern}%"
        self.cursor.execute("SELECT username FROM users WHERE username LIKE ?", (pattern,))
        accounts = [row[0] for row in self.cursor.fetchall()]
        return chat_pb2.ListAccountsResponse(accounts=accounts)

    def ListMessages(self, request, context):
        if not self.is_leader:
            return chat_pb2.ListMessagesResponse(messages=[])
        username = request.username
        if not username:
            return chat_pb2.ListMessagesResponse(messages=[])
        
        self.cursor.execute(
        "SELECT id, sender, message, timestamp, delivered FROM messages WHERE recipient = ? ORDER BY id ASC",
        (username,)
        )
        messages = self.cursor.fetchall()
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
        if not self.is_leader:
            return chat_pb2.DeleteMessagesResponse(success=False, message=f"Not leader, current leader is {self.leader_address}")
        operation = f"DeleteMessages:{request.username}:{','.join(map(str, request.message_ids))}"
        if self.replicate_operation(operation):
            self.apply_operation(operation)
            return chat_pb2.DeleteMessagesResponse(success=True, message="Messages deleted")
        return chat_pb2.DeleteMessagesResponse(success=False, message="Failed to replicate")
    
    def DeleteAccount(self, request, context):
        if not self.is_leader:
            return chat_pb2.DeleteAccountResponse(success=False, message=f"Not leader, current leader is {self.leader_address}")
        operation = f"DeleteAccount:{request.username}"
        if self.replicate_operation(operation):
            self.apply_operation(operation)
            if request.username in self.active_subscriptions:
                del self.active_subscriptions[request.username]
            return chat_pb2.DeleteAccountResponse(success=True, message="Account deleted")
        return chat_pb2.DeleteAccountResponse(success=False, message="Failed to replicate")
    
    def GetLeader(self, request, context):
        return chat_pb2.GetLeaderResponse(leader_address=self.leader_address or self.address)

    def GetState(self, request, context):
        self.cursor.execute("SELECT username, password_hash FROM users")
        users = [chat_pb2.User(username=row[0], password_hash=row[1]) for row in self.cursor.fetchall()]
        self.cursor.execute("SELECT id, sender, recipient, message, timestamp, delivered FROM messages")
        messages = [chat_pb2.Message(id=row[0], sender=row[1], recipient=row[2], message=row[3], timestamp=row[4], delivered=row[5]) for row in self.cursor.fetchall()]
        return chat_pb2.GetStateResponse(users=users, messages=messages)
    

    # ReplicationService Methods
    def Heartbeat(self, request, context):
        self.alive_peers[request.sender_address] = time.time()
        return chat_pb2.HeartbeatResponse(success=True)

    def RequestElection(self, request, context):
        self.alive_peers[request.sender_address] = time.time()
        return chat_pb2.ElectionResponse(ok=self.id > int(request.sender_address.split(':')[-1]) - 50050)

    def SetLeader(self, request, context):
        self.leader_address = request.leader_address
        self.is_leader = (self.address == self.leader_address)
        return chat_pb2.SetLeaderResponse(success=True)

    def ReplicateOperation(self, request, context):
        self.apply_operation(request.operation)
        return chat_pb2.ReplicateResponse(success=True)

    def replicate_operation(self, operation):
        acks = 0
        for peer in self.peers:
            try:
                with grpc.insecure_channel(peer) as channel:
                    stub = chat_pb2_grpc.ReplicationServiceStub(channel)
                    response = stub.ReplicateOperation(chat_pb2.ReplicateRequest(operation=operation), timeout=1)
                    if response.success:
                        acks += 1
                        if acks >= 2:
                            return True
            except:
                pass
        return False

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
    parser.add_argument("--id", type=int, required=True, help="Server ID (1-5)")
    parser.add_argument("--address", type=str, required=True, help="My address (host:port)")
    parser.add_argument("--config", type=str, default="config.json", help="Path to config file")
    args = parser.parse_args()
    server = ChatServer(args.id, args.address, args.config)
    server.start()