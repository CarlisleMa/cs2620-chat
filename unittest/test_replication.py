import unittest
import tempfile
import os
import shutil
import time
import json
import sqlite3
import bcrypt
import grpc
import gc

import chat_pb2
import chat_pb2_grpc
from server import ChatServer


# --- Fake gRPC Channel and Stub for Testing Fault Tolerance ---

# Global dictionary to simulate server "up" status
TEST_ALIVE_STATUS = {}

class FakeReplicationStub:
    def __init__(self, address):
        self.address = address

    def ReplicateOperation(self, request, timeout=None):
        # Debug print to see which address is being contacted.
        print(f"FakeReplicationStub called for address {self.address} with operation: {request.operation}")
        if not TEST_ALIVE_STATUS.get(self.address, False):
            raise grpc.RpcError("Simulated server failure")
        # Return a fake successful response.
        from chat_pb2 import ReplicateResponse
        return ReplicateResponse(success=True)

class FakeChannel:
    def __init__(self, address):
        self.address = address

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def close(self):
        pass

def fake_insecure_channel(address):
    return FakeChannel(address)

# Save original functions to restore later.
_original_insecure_channel = grpc.insecure_channel
_original_replication_stub = None  # Set in setUp

# --- Revised Unit Tests ---

class TestChatSystem(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test databases and config.
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # Write a temporary config.json with 5 servers starting at id 7.
        # Their addresses are adjusted to avoid port conflicts.
        self.config_data = {
            "servers": [
                {"id": 7, "address": "127.0.0.1:50057"},
                {"id": 8, "address": "127.0.0.1:50058"},
                {"id": 9, "address": "127.0.0.1:50059"},
                {"id": 10, "address": "127.0.0.1:50060"},
                {"id": 11, "address": "127.0.0.1:50061"}
            ]
        }
        with open("config.json", "w") as f:
            json.dump(self.config_data, f)

        # Mark all servers as “up” initially.
        global TEST_ALIVE_STATUS
        TEST_ALIVE_STATUS = {server["address"]: True for server in self.config_data["servers"]}

        # Monkey-patch grpc.insecure_channel for fault tolerance tests.
        grpc.insecure_channel = fake_insecure_channel

        # Also patch the ReplicationServiceStub so that it returns our FakeReplicationStub.
        import chat_pb2_grpc
        global _original_replication_stub
        _original_replication_stub = chat_pb2_grpc.ReplicationServiceStub
        chat_pb2_grpc.ReplicationServiceStub = lambda channel: FakeReplicationStub(channel.address)

        # Keep track of all created server instances for cleanup.
        self.servers = []

    def tearDown(self):
        # Close any open database connections.
        for server in self.servers:
            try:
                server.conn.close()
            except Exception as e:
                print(f"Error closing server connection: {e}")
        # Force garbage collection and wait a bit to release file handles.
        time.sleep(2)
        gc.collect()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
        # Restore the original grpc.insecure_channel and ReplicationServiceStub.
        grpc.insecure_channel = _original_insecure_channel
        import chat_pb2_grpc
        chat_pb2_grpc.ReplicationServiceStub = _original_replication_stub

    def test_persistence(self):
        """
        Verify that data is persisted across a "restart" of a server.
        """
        from server import ChatServer  # Adjust import as needed
        server7 = ChatServer(7, "127.0.0.1:50057", config_file="config.json")
        self.servers.append(server7)
        server7.is_leader = True

        # Simulate CreateAccount operation.
        password_hash = bcrypt.hashpw(b"password", bcrypt.gensalt()).decode()
        create_op = f"CreateAccount:testuser:{password_hash}"
        server7.apply_operation(create_op)

        # Simulate sending a message.
        current_time = int(time.time())
        send_op = f"SendMessage:1:testuser:anotheruser:Hello:{current_time}"
        server7.apply_operation(send_op)

        # Verify that the data exists.
        server7.cursor.execute("SELECT username FROM users WHERE username = ?", ("testuser",))
        self.assertIsNotNone(server7.cursor.fetchone(), "User should be persisted in the database.")
        server7.cursor.execute("SELECT message FROM messages WHERE id = 1")
        self.assertIsNotNone(server7.cursor.fetchone(), "Message should be persisted in the database.")

        # "Restart" the server by creating a new instance with the same ID.
        server7_new = ChatServer(7, "127.0.0.1:50057", config_file="config.json")
        self.servers.append(server7_new)
        server7_new.is_leader = True

        server7_new.cursor.execute("SELECT username FROM users WHERE username = ?", ("testuser",))
        self.assertIsNotNone(server7_new.cursor.fetchone(), "User should persist after a restart.")
        server7_new.cursor.execute("SELECT message FROM messages WHERE id = 1")
        self.assertIsNotNone(server7_new.cursor.fetchone(), "Message should persist after a restart.")

    def test_fault_tolerance(self):
        """
        Verify that the leader’s replicate_operation can tolerate up to two server failures.
        """
        from server import ChatServer  # Adjust import as needed
        # Create ChatServer instances for all 5 servers.
        servers = {}
        for server_info in self.config_data["servers"]:
            s = ChatServer(server_info["id"], server_info["address"], config_file="config.json")
            servers[server_info["id"]] = s
            self.servers.append(s)

        # Choose the server with id 11 to be the leader.
        leader = servers[11]
        leader.is_leader = True
        leader.leader_address = leader.address

        # With all peers up, replication should succeed.
        op1 = f"CreateAccount:replicauser:{bcrypt.hashpw(b'password', bcrypt.gensalt()).decode()}"
        result1 = leader.replicate_operation(op1)
        self.assertTrue(result1, "Replication should succeed when all peers are up.")

        # Now simulate failure of two peers (e.g., servers at 127.0.0.1:50058 and 127.0.0.1:50059).
        TEST_ALIVE_STATUS["127.0.0.1:50058"] = False
        TEST_ALIVE_STATUS["127.0.0.1:50059"] = False

        op2 = f"SendMessage:2:replicauser:otheruser:Hi:{int(time.time())}"
        result2 = leader.replicate_operation(op2)
        self.assertTrue(result2, "Replication should succeed with two peers down (meeting 2-fault tolerance).")

        # Simulate failure of a third peer (e.g., take down 127.0.0.1:50060).
        TEST_ALIVE_STATUS["127.0.0.1:50060"] = False
        op3 = f"SendMessage:3:replicauser:otheruser:Hey:{int(time.time())}"
        result3 = leader.replicate_operation(op3)
        self.assertFalse(result3, "Replication should fail if more than 2 peers are down.")

if __name__ == "__main__":
    unittest.main()
