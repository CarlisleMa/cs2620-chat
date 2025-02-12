# client_binary.py
import socket
import struct

HOST = "127.0.0.1"
PORT = 54401  # Binary server port

def send_binary_message(sock, sender, recipient, message):
    """
    1 byte for len(sender), 1 for len(recipient), 1 for len(message).
    Then the raw bytes of each part.
    """
    sender_bytes = sender.encode("utf-8")
    recipient_bytes = recipient.encode("utf-8")
    message_bytes = message.encode("utf-8")

    header = struct.pack("!BBB", len(sender_bytes), len(recipient_bytes), len(message_bytes))
    payload = header + sender_bytes + recipient_bytes + message_bytes
    sock.sendall(payload)
    print(f"Sent {len(payload)} bytes in binary format.")


if __name__ == "__main__":
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        print(f"Connected to binary server at {HOST}:{PORT}")

        # For testing, send a few messages
        send_binary_message(s, "alice", "bob", "Hello Bob!")
        send_binary_message(s, "alice", "bob", "Another message")

        print("Done sending binary messages. Closing.")
