import socket
import json
import threading
import threading
import select
import sys
import queue




HOST = "127.0.0.1"
PORT = 54400
response_queue = queue.Queue()

import select
import queue

response_queue = queue.Queue()

global stop_threads  # Global flag to stop threads
stop_threads = False

def listen_for_responses(sock):
    """Listens for all responses from the server and places them into a queue."""
    while not stop_threads:  # Only run if stop_threads is False
        try:
            ready_to_read, _, _ = select.select([sock], [], [], 1)
            if not ready_to_read:
                continue  # No data available, keep listening

            response_data = sock.recv(4096).decode("utf-8")
            if not response_data.strip():
                continue  # Ignore empty messages

            responses = response_data.strip().split("\n")
            for response in responses:
                parsed_response = json.loads(response)
                response_queue.put(parsed_response)  # Store all responses

        except (json.JSONDecodeError, ConnectionResetError, BrokenPipeError):
            break  # Exit gracefully when an error occurs


def process_real_time_messages():
    """Continuously checks the response queue and prints real-time messages."""
    while not stop_threads:  # Only run if stop_threads is False
        try:
            response = response_queue.get(timeout=1)
            if "type" in response and response["type"] == "message":
                print(f"\nNew message from {response['from']}: {response['message']}\n> ", end="")
            else:
                response_queue.put(response)  # Keep command responses in queue
        except queue.Empty:
            continue  # No messages, keep checking



def send_request(sock, request):
    """Sends a request to the server and waits for the correct response."""
    try:
        sock.sendall((json.dumps(request) + "\n").encode("utf-8"))

        while True:
            try:
                response = response_queue.get(timeout=3)  # Wait up to 3 seconds
                if "status" in response:  # This is a command response
                    return response
                elif "type" in response and response["type"] == "message":
                    print(f"\nNew message from {response['from']}: {response['message']}\n> ", end="")
            except queue.Empty:
                return {"status": "error", "message": "No response received from server"}

    except json.JSONDecodeError:
        return {"status": "error", "message": "Malformed response from server"}
    except ConnectionResetError:
        return {"status": "error", "message": "Connection lost"}




# Start client socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    print(f"Connected to server at {HOST}:{PORT}")

    # Start the listener thread as soon as the client connects
    listener_thread = threading.Thread(target=listen_for_responses, args=(s,), daemon=True)
    listener_thread.start()

    ## This is debatable if this should be put before or afteer login
    # Start the real-time message processor (handles real-time message printing)
    message_processor_thread = threading.Thread(target=process_real_time_messages, daemon=True)
    message_processor_thread.start()


    while True:
        action = input("Register or Login? (REGISTER/LOGIN): ").upper()
        username = input("Enter username: ")
        password = input("Enter password: ")

        response = send_request(s, {"command": action, "username": username, "password": password})
        print(response)

        if response["status"] == "success":
            print("Login successful. Listening for new messages...")
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

            # Notify the server BEFORE closing the socket
            send_request(s, {"command": "EXIT", "username": username})

            # Stop background threads safely
            # stop_threads = True  # Signal threads to stop

            # # Wait for threads to exit before closing the socket
            # listener_thread.join(timeout=2)
            # message_processor_thread.join(timeout=2)

            s.close()  # Now close the socket
            break  # Exit the client loop


        elif action == "LIST":
            pattern = input("Enter search pattern (leave empty for all users): ")
            response = send_request(s, {"command": "LIST", "pattern": pattern})
            
            if response["status"] == "success":
                print("Registered Users:", response["accounts"])
            else:
                print("Error retrieving accounts.")



        print(response)

print("Client closed.")
