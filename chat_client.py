import socket
import threading
import json
import sys
import time
from datetime import datetime

class ChatClient:
    def __init__(self, host='127.0.0.1', port=55555):
        """
        Initialize the chat client
        """
        self.host = host
        self.port = port
        self.client = None
        self.username = None
        self.running = False
        self.message_queue = []
        
    def connect(self):
        """
        Connect to the chat server
        """
        try:
            # Create TCP socket
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect((self.host, self.port))
            self.running = True
            
            # Start receiving thread
            receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
            receive_thread.start()
            
            return True
            
        except Exception as e:
            print(f"[{self.get_timestamp()}] Connection error: {e}")
            return False
    
    def set_username(self, username):
        """
        Send username to server
        """
        try:
            self.client.send(username.encode('utf-8'))
            self.username = username
            return True
        except:
            return False
    
    def receive_messages(self):
        """
        Receive messages from server
        """
        while self.running:
            try:
                message_data = self.client.recv(1024)
                if not message_data:
                    print(f"[{self.get_timestamp()}] Connection lost")
                    self.running = False
                    break
                    
                # Decode JSON message
                message = json.loads(message_data.decode('utf-8'))
                self.display_message(message)
                
            except json.JSONDecodeError:
                print(f"[{self.get_timestamp()}] Received invalid data")
            except ConnectionResetError:
                print(f"[{self.get_timestamp()}] Connection reset by server")
                self.running = False
                break
            except Exception as e:
                if self.running:  # Only print error if we're still supposed to be running
                    print(f"[{self.get_timestamp()}] Receive error: {e}")
                break
    
    def display_message(self, message_data):
        """
        Display formatted message
        """
        timestamp = message_data.get('timestamp', self.get_timestamp())
        sender = message_data.get('sender', 'Unknown')
        message = message_data.get('message', '')
        msg_type = message_data.get('type', 'message')
        
        # Color coding based on message type
        colors = {
            'system': '\033[94m',    # Blue
            'welcome': '\033[92m',   # Green
            'error': '\033[91m',     # Red
            'whisper': '\033[95m',   # Magenta
            'message': '\033[0m'     # Default
        }
        
        color = colors.get(msg_type, '\033[0m')
        reset = '\033[0m'
        
        if msg_type == 'whisper':
            print(f"{color}[{timestamp}] {sender}: {message}{reset}")
        elif sender == 'Server':
            print(f"{color}[{timestamp}] {message}{reset}")
        else:
            print(f"{color}[{timestamp}] {sender}: {message}{reset}")
    
    def send_message(self, message):
        """
        Send message to server
        """
        if not self.running:
            print("Not connected to server")
            return False
            
        try:
            self.client.send(message.encode('utf-8'))
            return True
        except Exception as e:
            print(f"[{self.get_timestamp()}] Send error: {e}")
            self.running = False
            return False
    
    def disconnect(self):
        """
        Disconnect from server
        """
        self.running = False
        if self.client:
            self.client.close()
    
    @staticmethod
    def get_timestamp():
        """
        Get current timestamp
        """
        return datetime.now().strftime("%H:%M:%S")

def print_banner():
    """
    Print welcome banner
    """
    banner = """
    ╔══════════════════════════════════════╗
    ║      Python Socket Chat Client       ║
    ║          (TCP Implementation)        ║
    ╚══════════════════════════════════════╝
    """
    print(banner)

def print_help():
    """
    Print help message
    """
    help_text = """
    Quick Commands:
    /help     - Show this help
    /users    - List online users
    /whisper  - Send private message (format: /whisper username message)
    /time     - Show server time
    /quit     - Disconnect from server
    
    Just type and press Enter to send message to everyone!
    """
    print(help_text)

def main():
    """
    Main function to run the chat client
    """
    print_banner()
    
    # Configuration
    HOST = '127.0.0.1'  # Change if server is on different machine
    PORT = 55555
    
    # Check for command line arguments
    if len(sys.argv) > 2:
        HOST = sys.argv[1]
        PORT = int(sys.argv[2])
    elif len(sys.argv) > 1:
        try:
            PORT = int(sys.argv[1])
        except ValueError:
            print(f"Usage: python chat_client.py [host] [port]")
            print(f"Defaulting to {HOST}:{PORT}")
    
    # Create client
    client = ChatClient(HOST, PORT)
    
    # Connect to server
    print(f"[{client.get_timestamp()}] Connecting to {HOST}:{PORT}...")
    if not client.connect():
        print(f"[{client.get_timestamp()}] Failed to connect to server")
        return
    
    # Get username
    while True:
        username = input("Enter your username: ").strip()
        if username:
            if client.set_username(username):
                print(f"[{client.get_timestamp()}] Connected as '{username}'")
                print("Type /help for commands\n")
                break
            else:
                print("Failed to set username. Try again.")
        else:
            print("Username cannot be empty")
    
    # Main chat loop
    try:
        while client.running:
            try:
                # Get user input
                message = input().strip()
                
                if not message:
                    continue
                
                # Check for quit command
                if message.lower() == '/quit':
                    client.send_message('/quit')
                    time.sleep(0.1)  # Give time for server to process
                    break
                elif message.lower() == '/help':
                    print_help()
                else:
                    # Send message to server
                    client.send_message(message)
                    
            except KeyboardInterrupt:
                print("\nDisconnecting...")
                client.send_message('/quit')
                break
            except EOFError:
                print("\nDisconnecting...")
                break
                
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        client.disconnect()
        print(f"[{client.get_timestamp()}] Disconnected from server")

if __name__ == "__main__":
    main()