import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog
import queue
import grpc

import chat_pb2
import chat_pb2_grpc

class ChatClient:
    def __init__(self, root, host, port):
        self.root = root
        self.host = host
        self.port = port
        self.root.title("Chat Client")

        self.channel = None
        self.stub = None
        self.username = None

        # Thread-safe queue for incoming instant messages from the SubscribeMessages stream.
        self.incoming_queue = queue.Queue()

        self.create_login_screen()

    # ------------------------------ GRPC Connection ------------------------------
    def connect_to_server(self):
        """Creates a gRPC channel and stub to connect to the server."""
        self.channel = grpc.insecure_channel(f"{self.host}:{self.port}")
        self.stub = chat_pb2_grpc.ChatServiceStub(self.channel)

    # ------------------------------ Instant Message Subscription ------------------------------
    def subscribe_instant_messages(self):
        subscribe_request = chat_pb2.SubscribeRequest(username=self.username)
        try:
            for chat_msg in self.stub.SubscribeMessages(subscribe_request):
                # Instead of calling update_chat directly, enqueue the message.
                self.incoming_queue.put({
                    "type": "message",
                    "from": chat_msg.sender,
                    "message": chat_msg.message
                })
        except grpc.RpcError as ex:
            error_message = f"[INFO] Instant message subscription ended: {ex}"
            self.root.after(0, lambda: self.update_chat(error_message))



    def poll_incoming(self):
        """Called periodically in the GUI thread to process any instant messages."""
        while not self.incoming_queue.empty():
            response = self.incoming_queue.get_nowait()
            self.handle_server_response(response)
        self.root.after(100, self.poll_incoming)

    # ------------------------------ Response Handling ------------------------------
    def handle_server_response(self, response):
        """
        Processes responses that come via the incoming_queue.
        Instant messages have the key "type" set to "message".
        """
        if response.get("type") == "message":
            sender = response.get("from", "Unknown")
            text = response.get("message", "")
            self.update_chat(f"{sender} -> You: {text}")
        else:
            self.update_chat(f"[INFO] {response}")

    def process_rpc_response(self, response):
        """
        Processes responses from synchronous RPC calls.
        If the response contains a message field, show it in the chat window.
        Also process any returned messages or accounts.
        """
        # Display any generic message from the server.
        if hasattr(response, "message") and response.message:
            self.update_chat(f"[SERVER] {response.message}")

        # Display unread count if available.
        if hasattr(response, "unread_messages"):
            self.update_chat(f"[INFO] Unread messages: {response.unread_messages}")

        # Process messages (from READ or LIST_MESSAGES commands)
        if hasattr(response, "messages"):
            if not response.messages:
                self.update_chat("[INFO] No messages found.")
            else:
                self.update_chat("\n--- Retrieved Messages ---")
                for msg in response.messages:
                    # Convert the epoch timestamp to a human-readable format.
                    formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(msg.timestamp))
                    line = f"[{formatted_time}] id=[{msg.id}]: {msg.sender} -> {self.username}: {msg.message}"
                    self.update_chat(line)
                self.update_chat("--- End of List ---\n")

        # Process account list (from LIST command)
        if hasattr(response, "accounts"):
            if not response.accounts:
                self.update_chat("[INFO] No users found.")
            else:
                self.update_chat("[INFO] Registered Users:\n" + "\n".join(response.accounts))

    # ------------------------------ GUI Screens ------------------------------
    def create_login_screen(self):
        self.clear_screen()

        tk.Label(self.root, text="Username:").pack()
        self.username_entry = tk.Entry(self.root)
        self.username_entry.pack()

        tk.Label(self.root, text="Password:").pack()
        self.password_entry = tk.Entry(self.root, show="*")
        self.password_entry.pack()

        tk.Button(self.root, text="Register",
                  command=lambda: self.authenticate("REGISTER")).pack()
        tk.Button(self.root, text="Login",
                  command=lambda: self.authenticate("LOGIN")).pack()

    def create_chat_screen(self):
        self.clear_screen()

        # Header Frame: Display the current username.
        header = tk.Frame(self.root)
        header.pack(pady=5)
        username_label = tk.Label(header, text=f"Logged in as: {self.username}", font=("Arial", 12, "bold"))
        username_label.pack()

        # Chat messages text box
        self.messages_text = tk.Text(self.root, state=tk.DISABLED, height=15)
        self.messages_text.pack()

        # Message entry and buttons
        self.message_entry = tk.Entry(self.root)
        self.message_entry.pack()

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=5)

        tk.Button(btn_frame, text="Send Message", command=self.send_message).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame, text="Read Unread", command=self.read_messages).grid(row=0, column=1, padx=5)
        tk.Button(btn_frame, text="List Users", command=self.list_users).grid(row=0, column=2, padx=5)
        tk.Button(btn_frame, text="List All Msgs", command=self.list_all_messages).grid(row=0, column=3, padx=5)
        tk.Button(btn_frame, text="Delete Msg(s)", command=self.delete_messages).grid(row=1, column=0, padx=5, pady=5)
        tk.Button(btn_frame, text="Delete Account", command=self.delete_account).grid(row=1, column=1, padx=5, pady=5)
        tk.Button(btn_frame, text="Logout", command=self.logout).grid(row=1, column=2, padx=5, pady=5)

        # Start polling for instant messages.
        self.poll_incoming()


    # ------------------------------ Authentication ------------------------------
    def authenticate(self, command):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            messagebox.showerror("Error", "Username and password required.")
            return

        self.connect_to_server()
        self.username = username

        if command == "REGISTER":
            response = self.stub.CreateAccount(chat_pb2.CreateAccountRequest(username=username, password=password))
        elif command == "LOGIN":
            response = self.stub.Login(chat_pb2.LoginRequest(username=username, password=password))
        else:
            messagebox.showerror("Error", "Unknown command")
            return

        if response.success:
            self.create_chat_screen()
            # Start subscription thread for instant messages.
            threading.Thread(target=self.subscribe_instant_messages, daemon=True).start()
            self.update_chat(f"[SERVER] {response.message}")
            if command == "LOGIN":
                self.update_chat(f"[INFO] You have {response.unread_messages} unread messages")
        else:
            messagebox.showerror("Error", response.message)

    def logout(self):
        if not self.stub or not self.username:
            return
        response = self.stub.Logout(chat_pb2.LogoutRequest(username=self.username))
        self.update_chat(f"[SERVER] {response.message}")
        self.channel.close()
        self.channel = None
        self.stub = None
        self.username = None
        self.create_login_screen()

    # ------------------------------ Commands ------------------------------
    def send_message(self):
        if not self.username:
            messagebox.showerror("Error", "You must be logged in.")
            return

        recipient = simpledialog.askstring("Send Message", "Enter recipient username:")
        if not recipient:
            return

        message = self.message_entry.get().strip()
        if not message:
            messagebox.showerror("Error", "Message cannot be empty.")
            return

        request = chat_pb2.SendMessageRequest(sender=self.username, to=recipient, message=message)
        response = self.stub.SendMessage(request)
        if response.success:
            self.update_chat(f"You -> {recipient}: {message}")
            self.message_entry.delete(0, tk.END)
        else:
            messagebox.showerror("Error", response.message)

    def read_messages(self):
        if not self.username:
            messagebox.showerror("Error", "You must be logged in.")
            return

        request = chat_pb2.ReadMessagesRequest(username=self.username, count=10)
        response = self.stub.ReadMessages(request)
        self.process_rpc_response(response)

    def list_users(self):
        if not self.username:
            messagebox.showerror("Error", "You must be logged in.")
            return

        pattern = simpledialog.askstring("List Users", "Enter search pattern (empty = all users):")
        pattern = pattern if pattern is not None else ""
        request = chat_pb2.ListAccountsRequest(pattern=pattern, page=0)
        response = self.stub.ListAccounts(request)
        self.process_rpc_response(response)

    def list_all_messages(self):
        if not self.username:
            messagebox.showerror("Error", "You must be logged in.")
            return

        request = chat_pb2.ListMessagesRequest(username=self.username)
        response = self.stub.ListMessages(request)
        self.process_rpc_response(response)

    def delete_messages(self):
        if not self.username:
            messagebox.showerror("Error", "You must be logged in.")
            return

        # First, list messages so the user can see message IDs.
        request = chat_pb2.ListMessagesRequest(username=self.username)
        response = self.stub.ListMessages(request)
        self.process_rpc_response(response)

        # After a short delay, ask the user for message IDs.
        def ask_for_ids():
            msg_ids_str = simpledialog.askstring("Delete Messages", "Enter message IDs (comma-separated):")
            if not msg_ids_str:
                return
            ids_list = [int(m.strip()) for m in msg_ids_str.split(",") if m.strip().isdigit()]
            if not ids_list:
                return
            del_request = chat_pb2.DeleteMessagesRequest(username=self.username, message_ids=ids_list)
            del_response = self.stub.DeleteMessages(del_request)
            if del_response.success:
                self.update_chat(f"[SERVER] {del_response.message}")
            else:
                messagebox.showerror("Error", del_response.message)
        self.root.after(1000, ask_for_ids)

    def delete_account(self):
        if not self.username:
            messagebox.showerror("Error", "You must be logged in.")
            return

        confirm = messagebox.askyesno("Delete Account", "Are you sure you want to delete your account? This is irreversible.")
        if not confirm:
            return

        request = chat_pb2.DeleteAccountRequest(username=self.username)
        response = self.stub.DeleteAccount(request)
        if response.success:
            self.update_chat(f"[SERVER] {response.message}")
            self.logout()
        else:
            messagebox.showerror("Error", response.message)

    # ------------------------------ Helper Methods ------------------------------
    def update_chat(self, message):
        # If the widget doesn't exist, don't try to update it.
        if not hasattr(self, "messages_text") or not self.messages_text.winfo_exists():
            return
        try:
            self.messages_text.config(state=tk.NORMAL)
            self.messages_text.insert(tk.END, message + "\n")
            self.messages_text.config(state=tk.DISABLED)
            self.messages_text.see(tk.END)
        except Exception as e:
            # Optionally log the exception.
            print(f"Error updating chat: {e}")

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

def main():
    root = tk.Tk()

    # Prompt for server address and port before launching the client
    host = simpledialog.askstring("Server Address", "Enter server IP address:", initialvalue="127.0.0.1")
    port = simpledialog.askinteger("Server Port", "Enter server port:", initialvalue=50051)

    if not host or not port:
        messagebox.showerror("Error", "Server address and port are required.")
        return

    app = ChatClient(root, host, port)
    root.mainloop()

if __name__ == "__main__":
    main()
