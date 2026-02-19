import socket
import threading
import time
from datetime import datetime
import json
import sys

class ChatServer:
    def __init__(self, host='127.0.0.1', port=55555):
        """
        Initialize the chat server
        """
        self.host = host
        self.port = port
        self.server = None
        self.clients = {}  # Format: {conn: {'username': name, 'address': addr}}
        self.client_lock = threading.Lock()
        self.running = False
        
    def start(self):
        """
        Start the chat server
        """
        try:
            # Create TCP socket
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind((self.host, self.port))
            self.server.listen(5)
            
            self.running = True
            print(f"[{self.get_timestamp()}] Chat Server started on {self.host}:{self.port}")
            print(f"[{self.get_timestamp()}] Waiting for connections...")
            print("Type 'shutdown' to stop the server\n")
            
            # Start admin thread for server commands
            admin_thread = threading.Thread(target=self.admin_interface, daemon=True)
            admin_thread.start()
            
            # Accept connections
            while self.running:
                try:
                    conn, addr = self.server.accept()
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(conn, addr)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except OSError:
                    # Server socket closed
                    break
                    
        except Exception as e:
            print(f"[{self.get_timestamp()}] Server error: {e}")
        finally:
            self.shutdown()
            
    def handle_client(self, conn, addr):
        """
        Handle individual client connection
        """
        username = None
        try:
            # Send welcome message
            conn.send(self.encode_message("Server", "Welcome to the chat server! Enter your username:", "system"))
            
            # Get username
            username_data = conn.recv(1024).decode('utf-8')
            if not username_data:
                conn.close()
                return
                
            username = username_data.strip()
            
            # Check if username is already taken
            with self.client_lock:
                taken_usernames = [client['username'] for client in self.clients.values()]
                if username in taken_usernames or username.lower() == 'server':
                    conn.send(self.encode_message("Server", "Username already taken. Disconnecting...", "error"))
                    conn.close()
                    return
            
            # Add client to dictionary
            with self.client_lock:
                self.clients[conn] = {'username': username, 'address': addr}
            
            # Notify all clients
            self.broadcast(f"{username} has joined the chat!", "system", exclude=conn)
            print(f"[{self.get_timestamp()}] {username} connected from {addr[0]}:{addr[1]}")
            
            # Send welcome message to new client
            conn.send(self.encode_message("Server", 
                f"Welcome {username}! Type '/help' for commands. Currently online: {self.get_online_users()}", 
                "welcome"))
            
            # Handle client messages
            while self.running:
                try:
                    message_data = conn.recv(1024)
                    if not message_data:
                        break
                        
                    message = message_data.decode('utf-8').strip()
                    
                    # Check for commands
                    if message.startswith('/'):
                        self.handle_command(conn, username, message)
                    else:
                        # Broadcast regular message
                        self.broadcast(message, username, exclude=None)
                        
                except ConnectionResetError:
                    break
                except Exception as e:
                    print(f"[{self.get_timestamp()}] Error with client {username}: {e}")
                    break
                    
        except Exception as e:
            print(f"[{self.get_timestamp()}] Client handler error: {e}")
        finally:
            # Remove client and notify others
            if username:
                with self.client_lock:
                    if conn in self.clients:
                        del self.clients[conn]
                
                self.broadcast(f"{username} has left the chat.", "system")
                print(f"[{self.get_timestamp()}] {username} disconnected")
            conn.close()
            
    def handle_command(self, conn, username, command):
        """
        Handle client commands
        """
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == '/help':
            help_text = """
            Available Commands:
            /help - Show this help message
            /users - List online users
            /whisper <username> <message> - Send private message
            /quit - Disconnect from server
            /time - Show server time
            """
            conn.send(self.encode_message("Server", help_text, "system"))
            
        elif cmd == '/users':
            online_users = self.get_online_users()
            conn.send(self.encode_message("Server", f"Online users: {online_users}", "system"))
            
        elif cmd == '/whisper' and len(parts) >= 3:
            target_user = parts[1]
            whisper_msg = ' '.join(parts[2:])
            
            # Find target connection
            target_conn = None
            with self.client_lock:
                for client_conn, client_info in self.clients.items():
                    if client_info['username'] == target_user:
                        target_conn = client_conn
                        break
            
            if target_conn and target_conn != conn:
                # Send whisper to target
                target_conn.send(self.encode_message(f"[Whisper from {username}]", whisper_msg, "whisper"))
                # Confirm to sender
                conn.send(self.encode_message("Server", f"Whisper sent to {target_user}", "system"))
            else:
                conn.send(self.encode_message("Server", f"User '{target_user}' not found or is yourself", "error"))
                
        elif cmd == '/time':
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.send(self.encode_message("Server", f"Server time: {current_time}", "system"))
            
        elif cmd == '/quit':
            conn.send(self.encode_message("Server", "Goodbye!", "system"))
            # Client will be removed in handle_client finally block
            
        else:
            conn.send(self.encode_message("Server", "Unknown command. Type /help for available commands.", "error"))
    
    def broadcast(self, message, sender, exclude=None, msg_type="message"):
        """
        Broadcast message to all connected clients except 'exclude'
        """
        with self.client_lock:
            for client_conn in list(self.clients.keys()):
                if client_conn != exclude:
                    try:
                        client_conn.send(self.encode_message(sender, message, msg_type))
                    except:
                        # Remove failed client
                        if client_conn in self.clients:
                            del self.clients[client_conn]
    
    def get_online_users(self):
        """
        Get list of online usernames
        """
        with self.client_lock:
            return [info['username'] for info in self.clients.values()]
    
    def encode_message(self, sender, message, msg_type):
        """
        Encode message as JSON for transmission
        """
        message_data = {
            'timestamp': self.get_timestamp(),
            'sender': sender,
            'message': message,
            'type': msg_type
        }
        return json.dumps(message_data).encode('utf-8')
    
    def admin_interface(self):
        """
        Handle server admin commands
        """
        while self.running:
            try:
                command = input()
                if command.lower() == 'shutdown':
                    print(f"[{self.get_timestamp()}] Shutting down server...")
                    self.shutdown()
                    break
                elif command.lower() == 'users':
                    users = self.get_online_users()
                    print(f"[{self.get_timestamp()}] Online users ({len(users)}): {', '.join(users) if users else 'None'}")
                elif command.lower() == 'help':
                    print("Admin commands: shutdown, users, help")
                else:
                    print(f"Unknown command. Type 'help' for admin commands.")
            except EOFError:
                break
            except Exception as e:
                print(f"Admin interface error: {e}")
    
    def shutdown(self):
        """
        Gracefully shutdown the server
        """
        self.running = False
        
        # Notify all clients
        self.broadcast("Server is shutting down. Goodbye!", "Server", msg_type="error")
        
        # Close all client connections
        with self.client_lock:
            for conn in list(self.clients.keys()):
                try:
                    conn.close()
                except:
                    pass
            self.clients.clear()
        
        # Close server socket
        if self.server:
            self.server.close()
        
        print(f"[{self.get_timestamp()}] Server shut down successfully")
    
    @staticmethod
    def get_timestamp():
        """
        Get current timestamp
        """
        return datetime.now().strftime("%H:%M:%S")

def main():
    """
    Main function to run the chat server
    """
    # You can change these parameters
    HOST = '127.0.0.1'  # Localhost - change to '' for all interfaces
    PORT = 55555         # Default port
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        try:
            PORT = int(sys.argv[1])
        except ValueError:
            print(f"Usage: python chat_server.py [port]")
            print(f"Defaulting to port {PORT}")
    
    server = ChatServer(HOST, PORT)
    server.start()

if __name__ == "__main__":
    main()