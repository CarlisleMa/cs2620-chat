import os
import json
import time
import sqlite3
import unittest
import bcrypt

import chat_pb2
import chat_pb2_grpc
from server import ChatServer


# A simple fake gRPC context to pass to our RPC methods.
class FakeContext:
    def __init__(self):
        self.code = None
        self.details = None

    def is_active(self):
        return True

    def set_code(self, code):
        self.code = code

    def set_details(self, details):
        self.details = details

import gc

def safe_remove(filename, retries=10, delay=0.1):
    """Try to remove a file, retrying if a PermissionError occurs."""
    for _ in range(retries):
        try:
            os.remove(filename)
            return
        except PermissionError:
            time.sleep(delay)
    # If still locked, attempt one final time (will raise if still locked)
    os.remove(filename)

class TestChatServer(unittest.TestCase):
    def setUp(self):
        # Create a temporary config file with two server entries.
        self.config_filename = "temp_config.json"
        config_data = {
            "servers": [
                {"id": 6, "address": "localhost:50051"},
                {"id": 2, "address": "localhost:50052"}
            ]
        }
        with open(self.config_filename, "w") as f:
            json.dump(config_data, f)

        # Create a ChatServer instance with server id=6.
        self.server = ChatServer(6, "localhost:50051", self.config_filename)
        # For testing, force this instance to be the leader.
        self.server.is_leader = True
        self.server.leader_address = self.server.address
        # Override replicate_operation so that it always returns True.
        self.server.replicate_operation = lambda op: True

        # Clear any existing data from tables.
        self.server.cursor.execute("DELETE FROM users")
        self.server.cursor.execute("DELETE FROM messages")
        self.server.cursor.execute("DELETE FROM sequence")
        self.server.conn.commit()

    def tearDown(self):
        # Close DB resources.
        self.server.cursor.close()
        self.server.conn.close()
        # Remove reference to self.server and force garbage collection.
        del self.server
        gc.collect()
        time.sleep(0.5)  # give the OS a moment to release the file lock
        
        if os.path.exists(self.config_filename):
            os.remove(self.config_filename)
        
        db_filename = "chat_db_6.db"
        if os.path.exists(db_filename):
            safe_remove(db_filename)

    # ... (the rest of your test methods) ...

    def test_create_account(self):
        context = FakeContext()
        req = chat_pb2.CreateAccountRequest(username="user1", password="password123")
        resp = self.server.CreateAccount(req, context)
        self.assertTrue(resp.success)
        # Verify that the user is in the database.
        self.server.cursor.execute("SELECT username FROM users WHERE username = ?", ("user1",))
        result = self.server.cursor.fetchone()
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "user1")

    def test_login_success_and_failure(self):
        context = FakeContext()
        # Create an account first.
        create_req = chat_pb2.CreateAccountRequest(username="user2", password="secret")
        create_resp = self.server.CreateAccount(create_req, context)
        self.assertTrue(create_resp.success)

        # Test successful login.
        login_req = chat_pb2.LoginRequest(username="user2", password="secret")
        login_resp = self.server.Login(login_req, context)
        self.assertTrue(login_resp.success)

        # Test login with an incorrect password.
        wrong_login_req = chat_pb2.LoginRequest(username="user2", password="wrongpass")
        wrong_login_resp = self.server.Login(wrong_login_req, context)
        self.assertFalse(wrong_login_resp.success)

    def test_send_and_read_message(self):
        context = FakeContext()
        # Create accounts for sender and receiver.
        self.server.CreateAccount(chat_pb2.CreateAccountRequest(username="sender", password="pass"), context)
        self.server.CreateAccount(chat_pb2.CreateAccountRequest(username="receiver", password="pass"), context)

        # Send a message from sender to receiver.
        send_req = chat_pb2.SendMessageRequest(sender="sender", to="receiver", message="Hello there!")
        send_resp = self.server.SendMessage(send_req, context)
        self.assertTrue(send_resp.success)

        # Verify the message is stored in the database.
        self.server.cursor.execute("SELECT sender, recipient, message FROM messages WHERE recipient = ?", ("receiver",))
        msg = self.server.cursor.fetchone()
        self.assertIsNotNone(msg)
        self.assertEqual(msg[0], "sender")
        self.assertEqual(msg[1], "receiver")
        self.assertEqual(msg[2], "Hello there!")

        # Read messages for the receiver.
        read_req = chat_pb2.ReadMessagesRequest(username="receiver", count=10)
        read_resp = self.server.ReadMessages(read_req, context)
        self.assertEqual(len(read_resp.messages), 1)
        msg_proto = read_resp.messages[0]
        self.assertEqual(msg_proto.sender, "sender")
        self.assertEqual(msg_proto.message, "Hello there!")

        # Check that the message is marked as delivered.
        self.server.cursor.execute("SELECT delivered FROM messages WHERE id = ?", (msg_proto.id,))
        delivered_flag = self.server.cursor.fetchone()[0]
        self.assertEqual(delivered_flag, 1)

    def test_delete_messages(self):
        context = FakeContext()
        # Create accounts and send a message.
        self.server.CreateAccount(chat_pb2.CreateAccountRequest(username="sender", password="pass"), context)
        self.server.CreateAccount(chat_pb2.CreateAccountRequest(username="receiver", password="pass"), context)
        send_req = chat_pb2.SendMessageRequest(sender="sender", to="receiver", message="Test delete")
        send_resp = self.server.SendMessage(send_req, context)
        self.assertTrue(send_resp.success)

        # Retrieve the message ID.
        self.server.cursor.execute("SELECT id FROM messages WHERE recipient = ?", ("receiver",))
        msg_id = self.server.cursor.fetchone()[0]

        # Delete the message.
        delete_req = chat_pb2.DeleteMessagesRequest(username="receiver", message_ids=[msg_id])
        delete_resp = self.server.DeleteMessages(delete_req, context)
        self.assertTrue(delete_resp.success)

        # Verify the message has been deleted.
        self.server.cursor.execute("SELECT id FROM messages WHERE id = ?", (msg_id,))
        result = self.server.cursor.fetchone()
        self.assertIsNone(result)

    def test_delete_account(self):
        context = FakeContext()
        # Create two accounts and send a message to the account to be deleted.
        self.server.CreateAccount(chat_pb2.CreateAccountRequest(username="to_delete", password="pass"), context)
        self.server.CreateAccount(chat_pb2.CreateAccountRequest(username="other", password="pass"), context)
        send_req = chat_pb2.SendMessageRequest(sender="other", to="to_delete", message="Hello")
        send_resp = self.server.SendMessage(send_req, context)
        self.assertTrue(send_resp.success)

        # Delete the account.
        del_req = chat_pb2.DeleteAccountRequest(username="to_delete")
        del_resp = self.server.DeleteAccount(del_req, context)
        self.assertTrue(del_resp.success)

        # Verify that the account is removed.
        self.server.cursor.execute("SELECT username FROM users WHERE username = ?", ("to_delete",))
        result = self.server.cursor.fetchone()
        self.assertIsNone(result)

        # Verify that messages related to the account are also deleted.
        self.server.cursor.execute("SELECT id FROM messages WHERE sender = ? OR recipient = ?", ("to_delete", "to_delete"))
        result = self.server.cursor.fetchone()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
