import socket
import json
import threading


HOST = "127.0.0.1"
PORT = 54400

def send_request(sock, request):
    """Helper function to send a JSON request and receive a response."""
    sock.sendall(json.dumps(request).encode("utf-8"))
    return json.loads(sock.recv(1024).decode("utf-8"))

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    print(f"Connected to server at {HOST}:{PORT}")

    while True:
        action = input("Register or Login? (REGISTER/LOGIN): ").upper()
        username = input("Enter username: ")
        password = input("Enter password: ")

        response = send_request(s, {"command": action, "username": username, "password": password})
        print(response)

        if response["status"] == "success":
            break

    while True:
        action = input("Choose action: [SEND, READ, EXIT, LIST]: ").upper()

        if action == "SEND":
            recipient = input("Recipient: ")
            message = input("Message: ")
            response = send_request(s, {"command": "SEND", "sender": username, "recipient": recipient, "message": message})
            print(response["message"])

        elif action == "READ":
            limit = input("How many messages do you want to read? (default: 10): ").strip()
            limit = int(limit) if limit.isdigit() else 10
            response = send_request(s, {"command": "READ", "username": username, "limit": limit})
            
            messages = response.get("messages", [])
            if messages:
                print("\n Your Messages:")
                for msg in messages:
                    print(f"[{msg['timestamp']}] {msg['from']}: {msg['message']}")
            else:
                print("No unread messages.")

        elif action == "EXIT":
            print("Closing connection...")
            break
        
        elif action == "LIST":
            pattern = input("Enter search pattern (leave empty for all users): ")
            response = send_request(s, {"command": "LIST", "pattern": pattern})
            
            if response["status"] == "success":
                print("Registered Users:", response["accounts"])
            else:
                print("Error retrieving accounts.")



        print(response)

print("Client closed.")
