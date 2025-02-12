import socket
import json
import threading


HOST = "127.0.0.1"
PORT = 54400

def send_request(sock, request):
    """Helper function to send a JSON request and receive a response."""
    sock.sendall(json.dumps(request).encode("utf-8"))
    return json.loads(sock.recv(1024).decode("utf-8"))


import threading
import select
import sys

# def listen_for_messages(sock):
#     """Continuously listens for incoming messages from the server without blocking user input."""
#     while True:
#         try:
#             # Use select to check if data is available to read (timeout of 1 second)
#             ready_to_read, _, _ = select.select([sock], [], [], 1)
#             if sock in ready_to_read:
#                 response_data = sock.recv(1024).decode("utf-8")
#                 if not response_data.strip():  # Ignore empty responses
#                     continue

#                 response = json.loads(response_data)
#                 if response.get("type") == "message":
#                     sys.stdout.write(f"\n New message from {response['from']}: {response['message']}\n> ")
#                     sys.stdout.flush()  # Ensure prompt reappears correctly

#         except (json.JSONDecodeError, ConnectionResetError, BrokenPipeError):
#             print("\n Connection lost. Exiting...")
#             break


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
        # Start the background listener thread
    
    # listener_thread = threading.Thread(target=listen_for_messages, args=(s,), daemon=True)
    # listener_thread.start()

    while True:
        action = input("Choose action: [SEND, READ, EXIT, LIST, DELETE]: ").upper()

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
        elif action == "DELETE":
            message_id = input("Enter message ID to delete (leave blank to delete all): ").strip()
            request = {"command": "DELETE", "username": username}

            if message_id:
                request["message_id"] = int(message_id)

            response = send_request(s, request)
            
            # ✅ Handle missing keys gracefully
            if "message" in response:
                print(response["message"])
            else:
                print("⚠️ Unexpected response from server:", response)




        print(response)

print("Client closed.")
