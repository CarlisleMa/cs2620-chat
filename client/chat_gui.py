import socket
import json
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog

HOST = "127.0.0.1"
PORT = 54400

class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Chat Client")
        self.socket = None
        self.username = None
        
        self.create_login_screen()

    def connect_to_server(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect((HOST, PORT))
        except ConnectionRefusedError:
            messagebox.showerror("Connection Error", "Unable to connect to the server.")
            self.root.quit()

    def send_request(self, request):
        """
        Sends a request to the server and receives a response.

        We append a newline so the server knows we've finished sending,
        and we also read up to a newline (or end) so we can parse JSON cleanly.
        """
        try:
            # Send JSON + newline
            self.socket.sendall((json.dumps(request) + "\n").encode("utf-8"))

            # Read up to 4096 bytes of response
            response_data = self.socket.recv(4096).decode("utf-8").strip()
            # If the server ever sends multiple lines, split them.
            lines = response_data.split("\n")
            # Usually we only need the first line as the response:
            return json.loads(lines[0])
        except Exception as e:
            messagebox.showerror("Error", f"Communication error: {str(e)}")
            return None

    def create_login_screen(self):
        """Creates the login/register screen."""
        self.clear_screen()

        tk.Label(self.root, text="Username:").pack()
        self.username_entry = tk.Entry(self.root)
        self.username_entry.pack()

        tk.Label(self.root, text="Password:").pack()
        self.password_entry = tk.Entry(self.root, show="*")
        self.password_entry.pack()

        tk.Button(self.root, text="Register", command=lambda: self.authenticate("REGISTER")).pack()
        tk.Button(self.root, text="Login", command=lambda: self.authenticate("LOGIN")).pack()

    def authenticate(self, action):
        """Handles user authentication."""
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        if not username or not password:
            messagebox.showerror("Error", "Username and password required.")
            return

        self.connect_to_server()
        response = self.send_request({"command": action, "username": username, "password": password})
        
        if response and response.get("status") == "success":
            self.username = username
            self.create_chat_screen()
        else:
            msg = response.get("message", "Authentication failed") if response else "No response"
            messagebox.showerror("Error", msg)

    def create_chat_screen(self):
        """Creates the chat interface."""
        self.clear_screen()
        
        self.messages_text = tk.Text(self.root, state=tk.DISABLED, height=15)
        self.messages_text.pack()
        
        self.message_entry = tk.Entry(self.root)
        self.message_entry.pack()
        
        tk.Button(self.root, text="Send Message", command=self.send_message).pack()
        tk.Button(self.root, text="Read Messages", command=self.read_messages).pack()
        tk.Button(self.root, text="List Users", command=self.list_users).pack()
        tk.Button(self.root, text="Logout", command=self.logout).pack()

        # In this simplified version, we do NOT run a background thread to read
        # incoming messages asynchronously. Instead, the user manually presses
        # "Read Messages" to poll for new messages.

    def send_message(self):
        """Sends a message to another user."""
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
        
        response = self.send_request({
            "command": "SEND",
            "sender": self.username,
            "recipient": recipient,
            "message": message
        })

        if response and response.get("status") == "success":
            # Show in local chat area
            self.update_chat(f"You -> {recipient}: {message}")
        else:
            msg = response.get("message", "Failed to send message") if response else "No response"
            messagebox.showerror("Error", msg)
        
        self.message_entry.delete(0, tk.END)
    
    def read_messages(self):
        """Reads unread messages."""
        if not self.username:
            messagebox.showerror("Error", "You must be logged in.")
            return

        response = self.send_request({"command": "READ", "username": self.username, "limit": 10})
        if not response:
            messagebox.showerror("Error", "No response from server.")
            return

        if response.get("messages"):
            for msg in response["messages"]:
                self.update_chat(f"{msg['from']} -> You: {msg['message']}")
        else:
            messagebox.showinfo("Messages", "No unread messages.")
    
    def list_users(self):
        """Lists registered users."""
        if not self.username:
            messagebox.showerror("Error", "You must be logged in.")
            return

        response = self.send_request({"command": "LIST", "pattern": ""})
        if response and response.get("status") == "success":
            users = "\n".join(response["accounts"])
            messagebox.showinfo("Registered Users", users if users else "No users found.")
        else:
            messagebox.showerror("Error", "Failed to retrieve users.")

    def logout(self):
        """Logs out and returns to the login screen."""
        if self.socket:
            self.socket.close()
        self.socket = None
        self.username = None
        self.create_login_screen()

    def update_chat(self, message):
        """Updates the chat log."""
        self.messages_text.config(state=tk.NORMAL)
        self.messages_text.insert(tk.END, message + "\n")
        self.messages_text.config(state=tk.DISABLED)
    
    def clear_screen(self):
        """Clears all widgets from the root window."""
        for widget in self.root.winfo_children():
            widget.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatClient(root)
    root.mainloop()
