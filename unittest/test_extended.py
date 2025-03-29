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
import threading

from server import ChatServer
import chat_pb2
import chat_pb2_grpc


# --- Fake gRPC Channel and Stub for Testing Fault Tolerance ---
TEST_ALIVE_STATUS = {}

class FakeReplicationStub:
    def __init__(self, address):
        self.address = address

    def ReplicateOperation(self, request, timeout=None):
        print(f"FakeReplicationStub called for address {self.address} with operation: {request.operation}")
        if not TEST_ALIVE_STATUS.get(self.address, False):
            raise grpc.RpcError("Simulated server failure")
        return chat_pb2.ReplicateResponse(success=True)

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

_original_insecure_channel = grpc.insecure_channel
_original_replication_stub = chat_pb2_grpc.ReplicationServiceStub

# --- Extended Test Suite ---

class TestChatSystemExtended(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

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

        global TEST_ALIVE_STATUS
        TEST_ALIVE_STATUS = {server["address"]: True for server in self.config_data["servers"]}

        grpc.insecure_channel = fake_insecure_channel
        chat_pb2_grpc.ReplicationServiceStub = lambda channel: FakeReplicationStub(channel.address)

        self.servers = []

    def tearDown(self):
        for server in self.servers:
            try:
                server.conn.close()
            except Exception as e:
                print(f"Error closing server connection: {e}")
        time.sleep(2)
        gc.collect()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
        grpc.insecure_channel = _original_insecure_channel
        chat_pb2_grpc.ReplicationServiceStub = _original_replication_stub

    def test_data_consistency_multiple_ops(self):
        """
        Create several accounts and messages, delete one message,
        then restart the leader server and verify that the database state
        is consistent with all applied operations.
        """
        server7 = ChatServer(7, "127.0.0.1:50057", config_file="config.json")
        self.servers.append(server7)
        server7.is_leader = True

        # Create two accounts: alice and bob.
        for username in ["alice", "bob"]:
            pwd_hash = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
            op = f"CreateAccount:{username}:{pwd_hash}"
            server7.apply_operation(op)
        
        # Send three messages.
        now = int(time.time())
        ops = [
            f"SendMessage:1:alice:bob:Hello Bob:{now}",
            f"SendMessage:2:bob:alice:Hi Alice:{now+1}",
            f"SendMessage:3:alice:bob:How are you?:{now+2}"
        ]
        for op in ops:
            server7.apply_operation(op)
        
        # Delete message with id 2.
        # IMPORTANT: Since message 2 is sent to "alice", we must use "alice" as the recipient.
        del_op = "DeleteMessages:alice:2"
        server7.apply_operation(del_op)

        # Verify state before restart.
        server7.cursor.execute("SELECT COUNT(*) FROM users")
        user_count = server7.cursor.fetchone()[0]
        self.assertEqual(user_count, 2, "There should be 2 users.")
        
        server7.cursor.execute("SELECT id FROM messages")
        message_ids = sorted([row[0] for row in server7.cursor.fetchall()])
        # Expected: Only messages with id 1 and 3 remain.
        self.assertEqual(message_ids, [1, 3], "Only messages 1 and 3 should exist.")

        # Restart server7.
        server7_new = ChatServer(7, "127.0.0.1:50057", config_file="config.json")
        self.servers.append(server7_new)
        server7_new.is_leader = True

        # Verify that the same users and messages persist after restart.
        server7_new.cursor.execute("SELECT COUNT(*) FROM users")
        new_user_count = server7_new.cursor.fetchone()[0]
        self.assertEqual(new_user_count, 2, "Users should persist after restart.")

        server7_new.cursor.execute("SELECT id FROM messages")
        new_message_ids = sorted([row[0] for row in server7_new.cursor.fetchall()])
        self.assertEqual(new_message_ids, [1, 3], "Messages should persist after restart.")

    # Other tests remain unchanged...
    def test_concurrent_operations_partial_failure(self):
        from server import ChatServer
        cluster = {}
        for info in self.config_data["servers"]:
            s = ChatServer(info["id"], info["address"], config_file="config.json")
            cluster[info["id"]] = s
            self.servers.append(s)
        leader = cluster[11]
        leader.is_leader = True
        leader.leader_address = leader.address

        op_initial = f"CreateAccount:concurrentuser:{bcrypt.hashpw(b'pwd', bcrypt.gensalt()).decode()}"
        self.assertTrue(leader.replicate_operation(op_initial),
                        "Initial replication should succeed with all peers up.")

        TEST_ALIVE_STATUS["127.0.0.1:50058"] = False
        TEST_ALIVE_STATUS["127.0.0.1:50059"] = False

        def send_message(op, results, idx):
            res = leader.replicate_operation(op)
            results[idx] = res

        num_ops = 5
        threads = []
        results = [None] * num_ops
        base_time = int(time.time())
        for i in range(num_ops):
            op = f"SendMessage:{i+10}:concurrentuser:otheruser:Msg{i}:{base_time+i}"
            t = threading.Thread(target=send_message, args=(op, results, i))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        self.assertTrue(all(results), "All concurrent replications should succeed with two peers down.")

        TEST_ALIVE_STATUS["127.0.0.1:50060"] = False
        op_fail = f"SendMessage:100:concurrentuser:otheruser:This should fail:{int(time.time())}"
        self.assertFalse(leader.replicate_operation(op_fail),
                         "Replication should fail when more than 2 peers are down.")

    def test_leader_election_simulation(self):
        from server import ChatServer
        cluster = {}
        for info in self.config_data["servers"]:
            s = ChatServer(info["id"], info["address"], config_file="config.json")
            cluster[info["id"]] = s
            self.servers.append(s)
        
        TEST_ALIVE_STATUS["127.0.0.1:50061"] = False  # Simulate current leader failure

        candidate = cluster[10]
        candidate.is_leader = False
        candidate.leader_address = None

        candidate.initiate_election()
        self.assertTrue(candidate.is_leader,
                        "Candidate should elect itself as leader when all higher peers are down.")

if __name__ == "__main__":
    unittest.main(verbosity=2)
