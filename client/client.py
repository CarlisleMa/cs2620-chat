import socket

HOST = "127.0.0.1"
PORT = 54400

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    print(f"Connected to server at {HOST}:{PORT}")

    while True:
        message = input("Enter a message to send to the server (or 'exit' to quit): ")
        
        if message.lower() == "exit":
            print("Closing connection...")
            break

        s.sendall(message.encode("utf-8"))
        
        data = s.recv(1024)
        if not data:
            print("Server disconnected.")
            break
        
        print(f"Received: {data.decode('utf-8')}")

print("Client closed.")
