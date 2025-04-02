"""
Basic utilities for executing tools
inside or outside of virtual containers.
"""
import subprocess  # nosec B404
import threading
import os
import pty
import signal
import time
import uuid
from wasabi import color  # pylint: disable=import-error

# Global dictionary to store active sessions
ACTIVE_SESSIONS = {}


def _get_workspace_dir() -> str:
    """Determines the target workspace directory based on env var."""
    base_dir = "/workspace/workspaces"
    workspace_name = os.getenv("CAI_WORKSPACE")
    if workspace_name:
        # Basic validation - allow alphanumeric, underscore, hyphen
        if not all(c.isalnum() or c in ['_', '-'] for c in workspace_name):
            print(color(f"Invalid CAI_WORKSPACE name '{workspace_name}'. "
                        f"Using default.", fg="yellow"))
            workspace_name = "cai_default"
    else:
        workspace_name = "cai_default"

    target_dir = os.path.join(base_dir, workspace_name)
    # Ensure the directory exists
    try:
        os.makedirs(target_dir, exist_ok=True)
    except OSError as e:
        print(color(f"Error creating workspace directory '{target_dir}': {e}", fg="red"))
        # Fallback to root workspace if creation fails
        return "/workspace"
    return target_dir


class ShellSession:  # pylint: disable=too-many-instance-attributes
    """Class to manage interactive shell sessions"""

    def __init__(self, command, session_id=None, ctf=None, workspace_dir=None):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.original_command = command  # Store original for logging
        self.ctf = ctf
        self.workspace_dir = workspace_dir or _get_workspace_dir()
        self.process = None
        self.master = None
        self.slave = None
        self.output_buffer = []
        self.is_running = False
        self.last_activity = time.time()

        # Prepare the command based on context
        self.command = self._prepare_command(command)

    def _prepare_command(self, command):
        """Prefixes the command with cd if necessary."""
        # Ensure workspace_dir exists for CTF/SSH before prefixing
        # Local uses cwd parameter, no prefix needed.
        if self.ctf:
             # For CTF, always change directory
            return f"cd '{self.workspace_dir}' && {command}"
        # For local, cwd is handled by Popen/run, no prefix needed
        return command

    def start(self):
        """Start the shell session"""
        start_message_cmd = self.original_command # Use original for messages
        if self.ctf:
            # For CTF environments
            self.is_running = True
            self.output_buffer.append(
                f"[Session {self.session_id}] Started CTF command: "
                f"{start_message_cmd} in {self.workspace_dir}")
            try:
                # Execute the prepared command (with cd prefix)
                output = self.ctf.get_shell(self.command)
                self.output_buffer.append(output)
            except Exception as e:  # pylint: disable=broad-except
                self.output_buffer.append(f"Error: {str(e)}")
            self.is_running = False
            return

        # For local environment
        try:
            # Create a pseudo-terminal
            self.master, self.slave = pty.openpty()

            # Start the process IN THE WORKSPACE DIRECTORY
            self.process = subprocess.Popen(  # pylint: disable=subprocess-popen-preexec-fn, consider-using-with # noqa: E501
                self.command,  # Use the (potentially prefixed) command
                shell=True,  # nosec B602
                stdin=self.slave,
                stdout=self.slave,
                stderr=self.slave,
                cwd=self.workspace_dir, # <<<<< Set CWD for local process
                preexec_fn=os.setsid,  # Create a new process group
                universal_newlines=True
            )

            self.is_running = True
            self.output_buffer.append(
                f"[Session {self.session_id}] Started: "
                f"{start_message_cmd} in {self.workspace_dir}")

            # Start a thread to read output
            threading.Thread(target=self._read_output, daemon=True).start()
        except Exception as e:  # pylint: disable=broad-except
            self.output_buffer.append(f"Error starting session: {str(e)}")
            self.is_running = False

    def _read_output(self):
        """Read output from the process"""
        try:
            while self.is_running:
                try:
                    output = os.read(self.master, 1024).decode()
                    if output:
                        self.output_buffer.append(output)
                        self.last_activity = time.time()
                except OSError:
                    # No data available or terminal closed
                    time.sleep(0.1)
                    if not self.is_process_running():
                        self.is_running = False
                        break
        except Exception as e:  # pylint: disable=broad-except
            self.output_buffer.append(f"Error reading output: {str(e)}")
            self.is_running = False

    def is_process_running(self):
        """Check if the process is still running"""
        if not self.process:
            return False
        return self.process.poll() is None

    def send_input(self, input_data):
        """Send input to the process"""
        if not self.is_running:
            return "Session is not running"

        try:
            if self.ctf:
                # For CTF environments
                output = self.ctf.get_shell(input_data)
                self.output_buffer.append(output)
                return "Input sent to CTF session"

            # For local environment
            input_data = input_data.rstrip() + "\n"
            os.write(self.master, input_data.encode())
            self.last_activity = time.time()
            return "Input sent to session"
        except Exception as e:  # pylint: disable=broad-except
            return f"Error sending input: {str(e)}"

    def get_output(self, clear=True):
        """Get and optionally clear the output buffer"""
        output = "\n".join(self.output_buffer)
        if clear:
            self.output_buffer = []
        return output

    def terminate(self):
        """Terminate the session"""
        if not self.is_running:
            return "Session already terminated"

        try:
            self.is_running = False

            if self.process:
                # Try to terminate the process group
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                except BaseException:  # pylint: disable=bare-except,broad-except # noqa: E501
                    # If that fails, try to terminate just the process
                    self.process.terminate()

                # Clean up resources
                if self.master:
                    os.close(self.master)
                if self.slave:
                    os.close(self.slave)

            return f"Session {self.session_id} terminated"
        except Exception as e:  # pylint: disable=broad-except
            return f"Error terminating session: {str(e)}"


def create_shell_session(command, ctf=None):
    """Create a new shell session in the correct workspace."""
    workspace_dir = _get_workspace_dir()
    session = ShellSession(command, ctf=ctf, workspace_dir=workspace_dir)
    session.start() # Start already handles the workspace dir logic
    ACTIVE_SESSIONS[session.session_id] = session
    return session.session_id


def list_shell_sessions():
    """List all active shell sessions"""
    result = []
    for session_id, session in list(ACTIVE_SESSIONS.items()):
        # Clean up terminated sessions
        if not session.is_running:
            del ACTIVE_SESSIONS[session_id]
            continue

        result.append({
            "session_id": session_id,
            "command": session.original_command,
            "running": session.is_running,
            "last_activity": time.strftime(
                "%H:%M:%S",
                time.localtime(session.last_activity))
        })
    return result


def send_to_session(session_id, input_data):
    """Send input to a specific session"""
    if session_id not in ACTIVE_SESSIONS:
        return f"Session {session_id} not found"

    session = ACTIVE_SESSIONS[session_id]
    # We don't need to cd here again, the session is already in the dir
    return session.send_input(input_data)


def get_session_output(session_id, clear=True):
    """Get output from a specific session"""
    if session_id not in ACTIVE_SESSIONS:
        return f"Session {session_id} not found"

    session = ACTIVE_SESSIONS[session_id]
    return session.get_output(clear)


def terminate_session(session_id):
    """Terminate a specific session"""
    if session_id not in ACTIVE_SESSIONS:
        return f"Session {session_id} not found"

    session = ACTIVE_SESSIONS[session_id]
    result = session.terminate()
    del ACTIVE_SESSIONS[session_id]
    return result


def _run_ctf(ctf, command, stdout=False, timeout=100, workspace_dir=None):
    """Runs command in CTF env, changing to workspace_dir first."""
    target_dir = workspace_dir or _get_workspace_dir()
    full_command = f"cd '{target_dir}' && {command}"
    original_cmd_for_msg = command # For logging
    try:
        # Ensure the command is executed in a shell that supports command
        # chaining
        output = ctf.get_shell(full_command, timeout=timeout)
        # exploit_logger.log_ok()

        if stdout:
            print(f"\033[32m(in {target_dir}) $ {original_cmd_for_msg}\n{output}\033[0m") # noqa E501
        return output
    except Exception as e:  # pylint: disable=broad-except
        print(color(f"Error executing CTF command '{original_cmd_for_msg}' in '{target_dir}': {e}", fg="red")) # noqa E501
        # exploit_logger.log_error(str(e))
        return f"Error executing CTF command: {str(e)}"


def _run_ssh(command, stdout=False, timeout=100, workspace_dir=None):
    """Runs command via SSH, changing to workspace_dir first."""
    ssh_user = os.environ.get('SSH_USER')
    ssh_host = os.environ.get('SSH_HOST')
    ssh_pass = os.environ.get('SSH_PASS')

    # Prepare the command to be executed remotely
    remote_command = f"{command}"
    original_cmd_for_msg = command  # For logging

    if ssh_pass:
        # Use sshpass if password is provided
        ssh_cmd = f"sshpass -p '{ssh_pass}' ssh {ssh_user}@{ssh_host} '{remote_command}'"  # noqa E501
    else:
        # Use regular SSH if no password (assuming key-based auth)
        ssh_cmd = f"ssh {ssh_user}@{ssh_host} '{remote_command}'"

    try:
        result = subprocess.run(
            ssh_cmd,
            shell=True,  # nosec B602
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout)

        output = result.stdout if result.stdout else result.stderr
        if stdout:
            print(f"\033[32m({ssh_user}@{ssh_host}) $ {original_cmd_for_msg}\n{output}\033[0m")  # noqa E501
        return output
    except subprocess.TimeoutExpired as e:
        error_output = e.stdout.decode() if e.stdout else str(e)
        if stdout:
            print(f"\033[32m({ssh_user}@{ssh_host}) $ {original_cmd_for_msg}\nTIMEOUT\n{error_output}\033[0m")  # noqa E501
        return f"Timeout executing SSH command: {error_output}"
    except Exception as e:  # pylint: disable=broad-except
        error_msg = f"Error executing SSH command '{original_cmd_for_msg}' on {ssh_host}: {e}"  # noqa E501
        print(color(error_msg, fg="red"))
        return error_msg


def _run_local(command, stdout=False, timeout=100, workspace_dir=None):
    """Runs command locally in the specified workspace_dir."""
    target_dir = workspace_dir or _get_workspace_dir()
    original_cmd_for_msg = command # For logging
    try:
        # nosec B602 - shell=True is required for command chaining
        result = subprocess.run(
            command,
            shell=True,  # nosec B602
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            cwd=target_dir # <<<<< Set CWD for local process
        )
        output = result.stdout if result.stdout else result.stderr
        if stdout:
            print(f"\033[32m(local:{target_dir}) $ {original_cmd_for_msg}\n{output}\033[0m") # noqa E501
        return output
    except subprocess.TimeoutExpired as e:
        error_output = e.stdout.decode() if e.stdout else str(e)
        if stdout:
            print(f"\033[32m(local:{target_dir}) $ {original_cmd_for_msg}\nTIMEOUT\n{error_output}\033[0m") # noqa E501
        return f"Timeout executing local command: {error_output}"
    except Exception as e:  # pylint: disable=broad-except
        error_msg = f"Error executing local command '{original_cmd_for_msg}' in '{target_dir}': {e}" # noqa E501
        print(color(error_msg, fg="red"))
        return error_msg


def run_command(command, ctf=None, stdout=False,  # pylint: disable=too-many-arguments # noqa: E501
                async_mode=False, session_id=None,
                timeout=100):
    """
    Run command either in CTF container or on the local attacker machine,
    ensuring execution happens within the correct workspace directory.

    Args:
        command: The command to execute
        ctf: CTF environment object (if running in CTF)
        stdout: Whether to print output to stdout
        async_mode: Whether to run the command asynchronously
        session_id: ID of an existing session to send the command to
        timeout: Timeout for synchronous commands

    Returns:
        str: Command output, status message, or session ID
    """
    # Determine the workspace directory once
    workspace_dir = _get_workspace_dir()

    # If session_id is provided, send command to that session
    # The session itself is already running in the correct directory
    if session_id:
        if session_id not in ACTIVE_SESSIONS:
            return f"Session {session_id} not found"

        session = ACTIVE_SESSIONS[session_id]
        result = session.send_input(command) # Send original command
        if stdout:
            # Output is read from the session, reflects its context
            output = get_session_output(session_id, clear=False)
            # Maybe add workspace context to the print?
            print(f"\033[32m(Session {session_id} in {session.workspace_dir}) $ {command}\n{output}\033[0m") # noqa E501
        return result

    # If async_mode, create a new session (handles workspace internally)
    if async_mode:
        # create_shell_session now handles getting workspace_dir
        new_session_id = create_shell_session(command, ctf=ctf)
        if stdout:
            # Wait a moment for initial output
            time.sleep(0.5)
            output = get_session_output(new_session_id, clear=False)
            session = ACTIVE_SESSIONS.get(new_session_id)
            dir_context = session.workspace_dir if session else "unknown"
            print(f"\033[32m(Started Session {new_session_id} in {dir_context})\n{output}\033[0m") # noqa E501
        return f"Created session {new_session_id}. Use this ID to interact."

    # Otherwise, run command normally, passing workspace_dir
    if ctf:
        return _run_ctf(ctf, command, stdout, timeout, workspace_dir)

    # Check if SSH environment variables are set
    if all(os.environ.get(var) for var in ['SSH_USER', 'SSH_HOST']):
        return _run_ssh(command, stdout, timeout, workspace_dir)

    return _run_local(command, stdout, timeout, workspace_dir)
