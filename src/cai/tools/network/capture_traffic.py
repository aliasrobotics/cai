#!/usr/bin/env python3
import paramiko
import tempfile
import os
import subprocess
import time
import socket
import sys
from contextlib import contextmanager 
from cai.sdk.agents import function_tool

@function_tool
def capture_remote_traffic(ip, username, password, interface, capture_filter="", port=22, timeout=10):
    """
    Captures network traffic from a remote VM and returns a pipe that can be read by tshark.
    
    Args:
        ip (str): IP address of the remote VM
        username (str): SSH username for the remote VM
        password (str): SSH password for the remote VM
        interface (str): Network interface to capture on (e.g., eth0)
        capture_filter (str, optional): tcpdump filter expression
        port (int, optional): SSH port (default: 22)
        timeout (int, optional): Connection timeout in seconds (default: 10)
        
    Returns:
        subprocess.Popen: A process with stdout that can be read by tshark
        
    Raises:
        ConnectionError: If connection to the remote VM fails
        RuntimeError: If traffic capture fails to start
    """
    try:
        # Create SSH client and connect to remote VM
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        print(f"Connecting to {ip}:{port} as {username}...")
        client.connect(ip, port=port, username=username, password=password, timeout=timeout)
        
        # Verify interface exists
        _, stdout, stderr = client.exec_command(f"ip link show {interface}")
        if stdout.channel.recv_exit_status() != 0:
            error = stderr.read().decode().strip()
            raise RuntimeError(f"Interface {interface} not found: {error}")
        
        # Check if we have necessary permissions
        _, stdout, stderr = client.exec_command("which tcpdump")
        if stdout.channel.recv_exit_status() != 0:
            raise RuntimeError("tcpdump not found on remote system")
        
        # Build tcpdump command with filter if provided
        tcpdump_cmd = f"tcpdump -U -i {interface} -w - "
        if capture_filter:
            tcpdump_cmd += f"'{capture_filter}'"
        
        print(f"Starting capture on {ip}:{interface}...")
        
        # Start tcpdump process on remote machine and get its output
        stdin, stdout, stderr = client.exec_command(tcpdump_cmd)
        
        # Check if tcpdump started successfully (non-blocking check)
        time.sleep(1)
        if stdout.channel.exit_status_ready():
            error = stderr.read().decode().strip()
            raise RuntimeError(f"Failed to start tcpdump: {error}")
        
        # Create a named pipe (FIFO) for tshark to read from
        fifo_path = tempfile.mktemp()
        os.mkfifo(fifo_path)
        
        # Start a process to read from SSH and write to the FIFO
        def pipe_ssh_to_fifo():
            try:
                with open(fifo_path, 'wb') as fifo:
                    while True:
                        data = stdout.read(4096)
                        if not data:
                            break
                        fifo.write(data)
                        fifo.flush()
            except (BrokenPipeError, OSError) as e:
                print(f"Error in pipe_ssh_to_fifo: {str(e)}")
            finally:
                print("Closing FIFO due to error or completion.")

        import threading
        thread = threading.Thread(target=pipe_ssh_to_fifo, daemon=True)
        thread.start()
        
        print(f"Capture running. Data available at: {fifo_path}")
        print(f"You can now use: tshark -r {fifo_path} -c 100 [options]")
        
        # Example usage in the context manager
        subprocess.run(["tshark", "-r", fifo_path, "-c", "100"])
        
        return fifo_path
        
    except paramiko.AuthenticationException:
        raise ConnectionError("Authentication failed. Check username and password.")
    except paramiko.SSHException as e:
        raise ConnectionError(f"SSH connection error: {str(e)}")
    except socket.timeout:
        raise ConnectionError(f"Connection timed out after {timeout} seconds")
    except Exception as e:
        raise RuntimeError(f"Unexpected error: {str(e)}")


@function_tool # TODO: not ideal to decorate this context manager.
@contextmanager
def remote_capture_session(ip, username, password, interface, capture_filter="", port=22):
    """
    Context manager for remote traffic capture that automatically cleans up resources.
    
    Usage:
        with remote_capture_session("192.168.1.100", "admin", "password", "eth0") as fifo_path:
            # Run tshark to read from the FIFO
            subprocess.run(["tshark", "-r", fifo_path, "-T", "fields", "-e", "ip.src"])
    """
    fifo_path = None
    client = None
    
    try:
        fifo_path = capture_remote_traffic(ip, username, password, interface, 
                                          capture_filter=capture_filter, port=port)
        yield fifo_path
    finally:
        if fifo_path and os.path.exists(fifo_path):
            try:
                os.unlink(fifo_path)
            except:
                pass

if __name__ == "__main__":
    # Example usage
    if len(sys.argv) < 5:
        print("Usage: capture_traffic.py <ip> <username> <password> <interface> [filter]")
        sys.exit(1)
    
    ip = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    interface = sys.argv[4]
    capture_filter = sys.argv[5] if len(sys.argv) > 5 else ""
    
    try:
        with remote_capture_session(ip, username, password, interface, capture_filter) as fifo_path:
            # Keep the script running until interrupted
            print("Press Ctrl+C to stop the capture")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nCapture stopped")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)