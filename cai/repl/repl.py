"""
This module provides a REPL interface for testing and
interacting with CAI agents.
"""
# Standard library imports
import json
import os
import sys
import subprocess  # nosec B404
import signal
from configparser import ConfigParser
from importlib.resources import files
from typing import Optional, List
from pathlib import Path
import datetime

# Third party imports
from mako.template import Template  # pylint: disable=import-error
from prompt_toolkit import prompt  # pylint: disable=import-error
from prompt_toolkit.completion import (  # pylint: disable=import-error
    Completer, Completion
)
from prompt_toolkit.history import FileHistory  # pylint: disable=import-error
from prompt_toolkit.auto_suggest import (  # pylint: disable=import-error
    AutoSuggestFromHistory
)
from prompt_toolkit.key_binding import (  # pylint: disable=import-error
    KeyBindings
)
from prompt_toolkit.styles import Style  # pylint: disable=import-error
from prompt_toolkit.formatted_text import HTML  # pylint: disable=import-error
from wasabi import color  # pylint: disable=import-error
from rich.console import Console  # pylint: disable=import-error
from rich.panel import Panel  # pylint: disable=import-error
from rich.progress import (  # pylint: disable=import-error
    Progress, SpinnerColumn, TextColumn
)
# Local imports
from cai import (
    is_caiextensions_report_available,
    is_caiextensions_platform_available
)
from cai.core import CAI  # pylint: disable=import-error
from cai.rag.vector_db import QdrantConnector

if is_caiextensions_platform_available():
    from caiextensions.platform.base import (  # pylint: disable=ungrouped-imports,line-too-long,import-error # noqa: E501
        platform_manager
    )

# Global variables
client = None  # pylint: disable=invalid-name
console = Console()

# Command aliases for convenience
COMMAND_ALIASES = {
    "/h": "/help",      # Display help information
    "/q": "/exit",      # Exit the application
    "/quit": "/exit",   # Exit the application
    "/k": "/kill",      # Terminate active sessions
    "/e": "/env",       # Show environment variables
    "/g": "/graph",     # Display graph
    "/m": "/memory",    # Access memory
    "/p": "/platform",  # Interact with platform/s
    # shell commands
    "/s": "/shell",     # Execute shell commands
    "$": "/shell",      # Execute shell commands  # NOTE: research why this doesn't work
}


def get_platform_commands():
    """Get commands for all registered platforms."""
    if not is_caiextensions_platform_available():
        return ["No platform extensions installed"]
    platforms = platform_manager.list_platforms()
    return [
        "list",  # Para listar plataformas disponibles
        *[f"{platform} {cmd}"
          for platform in platforms
          for cmd in platform_manager.get_platform(platform).get_commands()]
    ]


COMMANDS = {
    "/memory": [
        "list",
        "load",
        "delete"
    ],
    "/help": [
        "memory",
        "agents",
        "graph",
        "platform",
        "shell",
        "env",
        "aliases"
    ],
    "/graph": [],
    "/exit": [],
    "/shell": [],
    "/env": [],
    "/platform":
        get_platform_commands(),
    "/kill": []
}


def handle_memory_list():
    """Handle /memory list command"""
    try:
        db = QdrantConnector()
        collections = db.client.get_collections()

        print("\nAvailable Memory Collections:")
        print("-----------------------------")

        for collection in collections.collections:
            name = collection.name
            info = db.client.get_collection(name)
            points_count = db.client.count(collection_name=name).count

            print(f"\nCollection: {color(name, fg='green', bold=True)}")
            print(f"Vectors: {points_count}")
            print(f"Vector Size: {info.config.params.vectors.size}")
            print(f"Distance: {info.config.params.vectors.distance}")

        print("\n")
        return True
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error listing collections: {e}")
        return False


def handle_memory_delete(collection_name):
    """Handle /memory delete command"""
    try:
        db = QdrantConnector()
        db.client.delete_collection(collection_name=collection_name)
        print(
            f"\nDeleted collection: {
                color(
                    collection_name,
                    fg='red',
                    bold=True)}\n")
        return True
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error deleting collection: {e}")
        return False


def handle_memory_load(collection_name):
    """Handle /memory load command"""
    try:
        os.environ['CAI_MEMORY_COLLECTION'] = collection_name
        if collection_name != "_all_":
            os.environ['CAI_MEMORY'] = "episodic"
        elif collection_name == "_all_":
            os.environ['CAI_MEMORY'] = "semantic"
        print(
            f"\nMemory collection set to: {
                color(
                    collection_name,
                    fg='green',
                    bold=True)}\n")
        return True
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error setting memory collection: {e}")
        return False


def handle_help():
    """Handle /help command"""
    print(f"""
{color('Memory Commands:', fg='yellow', bold=True, underline=True)}
{color('/memory list', fg='yellow')} or {color('/m list', fg='yellow')}
    List all memory collections
{color('/memory load <collection>', fg='yellow')
 } or {color('/m load <collection>', fg='yellow')}
    Load a memory collection
{color('/memory delete <collection>', fg='yellow')
 } or {color('/m delete <collection>', fg='yellow')}
    Delete a memory collection

    <{color('collection', bold=True)}>:
    - {color('<CTF_NAME>', fg='yellow')}
        Episodic memory for a specific CTF
        (e.g. {color('baby_first', bold=True)})
    - {color('_all_', fg='yellow')}
        Semantic memory across all CTFs

{color('Graph Commands:', fg='blue', bold=True, underline=True)}
{color('/graph', fg='blue')} or {color('/g', fg='blue')}
    Show the graph of the current memory collection

{color('Shell Commands:', fg='green', bold=True, underline=True)}
{color('/shell <command>', fg='green')} or {color('/s <command>', fg='green')}
    Execute a shell command (can be interrupted with CTRL+C)

{color('Environment Commands:', fg='cyan', bold=True, underline=True)}
{color('/env', fg='cyan')} or {color('/e', fg='cyan')}
    Display environment variables (CAI_* and CTF_*)

{color('Exit Commands:', fg='red', bold=True, underline=True)}
{color('/exit', fg='red')} or {color('/q', fg='red')}
    Exit CAI.

{color('Other Commands:', fg='grey', bold=True, underline=True)}
{color('/help aliases', fg='grey')} or {color('/h aliases', fg='grey')}
    Show all command aliases
""")
    if is_caiextensions_platform_available:
        print(f"""{color('Platform Commands:', fg='grey', bold=True, underline=True)}
{color('/platform', fg='grey')} or {color('/p', fg='grey')}
    Show all available platforms
""")
    return True


def handle_help_aliases():
    """Show all command aliases."""
    print(
        f"\n{
            color(
                'Command Aliases:',
                fg='magenta',
                bold=True,
                underline=True)}")
    for alias, command in sorted(COMMAND_ALIASES.items()):
        print(f"{color(alias, fg='yellow')} → {color(command, fg='green')}")
    print()
    return True


def handle_graph_show():
    """Handle /graph show command"""
    if not client or not client._graph:  # pylint: disable=protected-access
        print("No conversation graph available.")
        return True

    try:
        print("\nConversation Graph:")
        print("------------------")
        print(client._graph.ascii())  # pylint: disable=protected-access
        print()
        return True
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error displaying graph: {e}")
        return False


def handle_platform_command(
        command: str, args: Optional[List[str]] = None) -> bool:
    """Handle platform specific commands."""
    if not args:
        # Mostrar plataformas disponibles
        platforms = platform_manager.list_platforms()
        console.print(Panel(
            "\n".join(f"[green]{p}[/green]" for p in platforms),
            title="Available Platforms",
            border_style="blue"
        ))
        return True

    platform_name = args[0].lower()
    platform = platform_manager.get_platform(platform_name)

    if not platform:
        console.print(f"[red]Unknown platform: {platform_name}[/red]")
        return False

    if len(args) == 1:
        # Mostrar ayuda de la plataforma
        console.print(Panel(
            platform.get_help(),
            title=f"{platform_name.upper()} Help",
            border_style="blue"
        ))
        return True

    # Pasar el comando a la plataforma (sin el nombre de la plataforma)
    platform.handle_command(args[1:])
    return True


def handle_shell_command(command_args: List[str]) -> bool:
    """Execute a shell command that can be interrupted with CTRL+C.

    Args:
        command_args: The shell command and its arguments

    Returns:
        bool: True if the command was executed successfully
    """
    if not command_args:
        console.print("[red]Error: No command specified[/red]")
        return False

    shell_command = " ".join(command_args)
    console.print(f"[blue]Executing:[/blue] {shell_command}")

    # Save original signal handler
    original_sigint_handler = signal.getsignal(signal.SIGINT)

    try:
        # Set temporary handler for SIGINT that only affects shell command
        def shell_sigint_handler(sig, frame):
            # Just allow KeyboardInterrupt to propagate
            signal.signal(signal.SIGINT, original_sigint_handler)
            raise KeyboardInterrupt

        signal.signal(signal.SIGINT, shell_sigint_handler)

        # Check if this is a command that should run asynchronously
        async_commands = [
            'nc',
            'netcat',
            'ncat',
            'telnet',
            'ssh',
            'python -m http.server']
        is_async = any(cmd in shell_command for cmd in async_commands)

        if is_async:
            # For async commands, use os.system to allow terminal interaction
            console.print(
                "[yellow]Running in async mode (Ctrl+C to return to REPL)[/yellow]")
            os.system(shell_command)  # nosec B605
            console.print("[green]Async command completed or detached[/green]")
            return True
        else:
            # For regular commands, use the standard approach
            process = subprocess.Popen(  # nosec B602
                shell_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            # Show output in real time
            for line in iter(process.stdout.readline, ''):
                print(line, end='')

            # Wait for process to finish
            process.wait()

            if process.returncode == 0:
                console.print("[green]Command completed successfully[/green]")
            else:
                console.print(
                    f"[yellow]Command exited with code {process.returncode}"
                    f"[/yellow]")

            return True
    except KeyboardInterrupt:
        # Handle CTRL+C only for this command
        try:
            if not is_async:
                process.terminate()
            console.print("\n[yellow]Command interrupted by user[/yellow]")
        except Exception:  # nosec B110
            pass
        return True
    except Exception as e:
        console.print(f"[red]Error executing command: {str(e)}[/red]")
        return False
    finally:
        # Restore original signal handler
        signal.signal(signal.SIGINT, original_sigint_handler)


def handle_kill_command(args: List[str]) -> bool:
    """Kill a background process by PID.

    Args:
        args: List containing the PID to kill

    Returns:
        bool: True if the process was killed successfully
    """
    if not args:
        console.print("[red]Error: No PID specified[/red]")
        return False

    try:
        pid = int(args[0])
        import os
        import signal

        # Try to kill the process group
        try:
            os.killpg(pid, signal.SIGTERM)
            console.print(f"[green]Process group {pid} terminated[/green]")
        except BaseException:
            # If killing the process group fails, try killing just the process
            os.kill(pid, signal.SIGTERM)
            console.print(f"[green]Process {pid} terminated[/green]")

        return True
    except ValueError:
        console.print("[red]Error: Invalid PID format[/red]")
        return False
    except ProcessLookupError:
        console.print(f"[yellow]No process with PID {args[0]} found[/yellow]")
        return False
    except Exception as e:
        console.print(f"[red]Error killing process: {str(e)}[/red]")
        return False


def handle_env_command() -> bool:
    """Display environment variables starting with CAI or CTF.

    Returns:
        bool: True if the command was executed successfully
    """
    # Get all environment variables
    env_vars = {
        k: v for k, v in os.environ.items() if k.startswith(
            ('CAI_', 'CTF_'))}

    if not env_vars:
        console.print(
            "[yellow]No CAI_ or CTF_ environment variables found[/yellow]")
        return True

    # Create a table to display the variables
    from rich.table import Table
    table = Table(
        title="Environment Variables",
        show_header=True,
        header_style="bold magenta")
    table.add_column("Variable", style="cyan")
    table.add_column("Value", style="green")

    # Add rows to the table with masked values for sensitive data
    for key, value in sorted(env_vars.items()):
        # Mask sensitive values (API keys, tokens, etc.)
        if any(sensitive in key.lower()
               for sensitive in ['key', 'token', 'secret', 'password']):
            # Show first half of the value, mask the rest
            half_length = len(value) // 2
            masked_value = value[:half_length] + \
                '*' * (len(value) - half_length)
            table.add_row(key, masked_value)
        else:
            table.add_row(key, value)

    console.print(table)
    return True


def handle_command(command, args=None):  # pylint: disable=too-many-branches,too-many-locals,too-many-statements,line-too-long # noqa: E501
    """Handle CLI commands"""
    # Handle command aliases
    if command in COMMAND_ALIASES:
        command = COMMAND_ALIASES[command]

    # Special handling for shell command
    if command == "/shell":
        if not args:
            console.print("[red]Error: No command specified[/red]")
            return False
        return handle_shell_command(args)

    # Handle kill command
    if command == "/kill":
        return handle_kill_command(args)

    if command.startswith("/htb"):
        def is_platform_enabled(platform_name: str) -> bool:
            """Check if a platform is enabled as an extension."""
            try:
                if platform_name == "htb":
                    # Import only when needed
                    return True
                # Add more platforms here as needed
            except ImportError:
                return False
            return False
        if not is_platform_enabled("htb"):
            console.print(
                "[red]HTB extension not installed or properly configured"
                "[/red]")
            return False
        try:
            # Import HTB modules only when needed
            from caiextensions.platforms.htb.cli import (
                handle_htb_command
            )
            from caiextensions.platforms.htb.api import HTBClient

            token = os.getenv("HTB_TOKEN")
            if not token:
                console.print(
                    "[red]No HTB token found. Please set HTB_TOKEN "
                    "environment variable.[/red]")
                return False

            # Extract all parts after /htb as arguments
            full_command = command.split() + (args if args else [])
            htb_args = full_command[1:]  # Remove '/htb'

            htb_client = HTBClient(
                token=token, debug=os.getenv(
                    'CAI_HTB_DEBUG', 'false').lower() == 'true')
            handle_htb_command(htb_client, htb_args)
            return True
        except ImportError:
            console.print(
                "[red]HTB extension not installed or properly configured"
                "[/red]")
            return False
    if command == "/memory list":
        return handle_memory_list()
    if command.startswith("/memory load"):
        if not args:
            print("Error: Collection name required")
            return False
        return handle_memory_load(args[0])
    if command.startswith("/memory delete"):
        if not args:
            print("Error: Collection name required")
            return False
        return handle_memory_delete(args[0])
    if command.startswith("/graph"):
        return handle_graph_show()
    if command.startswith("/help aliases"):
        return handle_help_aliases()
    if command.startswith("/help"):
        return handle_help()
    if command.startswith("/exit"):
        sys.exit(0)
    if command.startswith("/env"):
        return handle_env_command()
    if command.startswith("/platform"):
        # Extract all parts after /platform as arguments
        full_command = command.split() + (args if args else [])
        platform_args = full_command[1:]  # Remove '/platform'
        return handle_platform_command(command, platform_args)
    return False


class FuzzyCommandCompleter(Completer):
    """Command completer with fuzzy matching for the REPL."""

    def get_completions(self, document, complete_event):
        """Get completions for the current document."""
        text = document.text_before_cursor.strip()
        words = text.split()

        if not text:
            # Show only main commands for better performance
            for cmd in sorted(COMMANDS.keys()):
                yield Completion(cmd,
                                 start_position=0,
                                 style="fg:ansicyan bold")
            return

        if text.startswith('/'):
            current_word = words[-1]

            # Simplify completion logic for better performance
            if len(words) == 1:
                # Complete main commands
                for cmd in sorted(COMMANDS.keys()):
                    if cmd.startswith(current_word):
                        yield Completion(cmd,
                                         start_position=-len(current_word),
                                         style="fg:ansicyan bold")

                # Complete aliases (only if they match exactly with start)
                for alias, cmd in sorted(COMMAND_ALIASES.items()):
                    if alias.startswith(current_word):
                        yield Completion(alias,
                                         start_position=-len(current_word),
                                         style="fg:ansigreen")

            elif len(words) == 2:
                cmd = words[0]
                # If using an alias, get the real command
                if cmd in COMMAND_ALIASES:
                    cmd = COMMAND_ALIASES[cmd]

                if cmd in COMMANDS:
                    for subcmd in sorted(COMMANDS[cmd]):
                        if subcmd.startswith(current_word):
                            yield Completion(subcmd,
                                             start_position=-len(current_word),
                                             style="fg:ansiyellow bold")


def run_demo_loop(
    starting_agent,
    context_variables=None,
    stream=False,
    debug=False,
    max_turns=float('inf'),
    ctf=None,
    state_agent=None
) -> None:
    """
    Run the demo loop for CAI.

    Args:
        starting_agent: The agent to start with
        context_variables: Optional context variables
        stream: Whether to stream responses
        debug: Debug level
        max_turns: Maximum number of turns
        ctf: Optional CTF instance to use
        state_agent: Optional state agent to use
    """
    global client  # pylint: disable=global-statement
    # Initialize CAI with CTF and state agent if provided
    client = CAI(
        ctf=ctf if os.getenv(
            'CTF_INSIDE',
            "true").lower() == "true" else None,
        state_agent=state_agent)

    # Get version from setup.cfg
    version = "unknown"
    try:
        config = ConfigParser()
        config.read('setup.cfg')
        version = config.get('metadata', 'version')
    except Exception:  # pylint: disable=broad-except
        version = 'unknown'

    print(f"""
                CCCCCCCCCCCCC      ++++++++   ++++++++      IIIIIIIIII
             CCC::::::::::::C  ++++++++++       ++++++++++  I::::::::I
           CC:::::::::::::::C ++++++++++         ++++++++++ I::::::::I
          C:::::CCCCCCCC::::C +++++++++    ++     +++++++++ II::::::II
         C:::::C       CCCCCC +++++++     +++++     +++++++   I::::I
        C:::::C                +++++     +++++++     +++++    I::::I
        C:::::C                ++++                   ++++    I::::I
        C:::::C                 ++                     ++     I::::I
        C:::::C                  +   +++++++++++++++   +      I::::I
        C:::::C                    +++++++++++++++++++        I::::I
        C:::::C                     +++++++++++++++++         I::::I
         C:::::C       CCCCCC        +++++++++++++++          I::::I
          C:::::CCCCCCCC::::C         +++++++++++++         II::::::II
           CC:::::::::::::::C           +++++++++           I::::::::I
             CCC::::::::::::C             +++++             I::::::::I
                CCCCCCCCCCCCC               ++              IIIIIIIIII

                              Cybersecurity AI (CAI) v{version}
""")

    messages = []
    messages_init = []
    if ctf:
        # Get challenge
        challenge_key = os.getenv('CTF_CHALLENGE')
        challenges = list(ctf.get_challenges().keys())
        challenge = challenge_key if challenge_key in challenges else (
            challenges[0] if len(challenges) > 0 else None)

        if challenge:
            print(color("Testing challenge: ", fg="white", bg="blue")
                  + color(f"'{challenge}'", fg="white", bg="blue"))

        # Get initial messages aligned with CTF
        messages += [{
            "role": "user",
            "content": Template(  # nosec B702
                filename="cai/prompts/core/user_master_template.md").render(
                    ctf=ctf,
                    challenge=challenge,
                    ip=ctf.get_ip() if ctf else None
            )
        }]

        messages_init = messages
    agent = starting_agent

    # Setup history file
    history_dir = Path.home() / ".cai"
    history_dir.mkdir(exist_ok=True)
    history_file = history_dir / "history.txt"

    # Setup session log file
    session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    session_log = history_dir / f"session_{session_id}.log"

    # Log start of session
    with open(session_log, "w", encoding="utf-8") as f:
        f.write(
            f"CAI Session started at {
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Version: {version}\n")
        if ctf:
            f.write(f"CTF: {ctf.__class__.__name__}\n")
            if challenge:
                f.write(f"Challenge: {challenge}\n")
        f.write("\n")

    # Function to log interactions
    def log_interaction(role, content):
        with open(session_log, "a", encoding="utf-8") as f:
            f.write(
                f"\n[{
                    datetime.datetime.now().strftime('%H:%M:%S')}] {
                    role.upper()}:\n")
            f.write(f"{content}\n")

    # Create key bindings
    kb = KeyBindings()

    @kb.add('c-l')
    def clear_screen(event):
        """Clear the screen."""
        os.system('cls' if os.name == 'nt' else 'clear')  # nosec B605
        event.app.renderer.clear()

    # Setup prompt style
    cli_style = Style.from_dict({
        'prompt': '#ff0066 bold',
        '': '#ffcc00',
        'bottom-toolbar': 'bg:#222222 #aaaaaa',
    })

    # # Setup command completer
    command_completer = FuzzyCommandCompleter()

    # Function to display bottom toolbar
    def get_bottom_toolbar():
        """Return bottom toolbar HTML content."""
        active_machine = ""
        if is_caiextensions_platform_available():
            try:
                from caiextensions.platform.htb.api import HTBClient
                token = os.getenv("HTB_TOKEN")
                if token:
                    htb_client = HTBClient(token=token)
                    machine = htb_client.get_active_machine()
                    if machine:
                        active_machine = (
                            f" | HTB: {machine.get('name', 'Unknown')} "
                            f"({machine.get('ip', 'Unknown')})"
                        )
            except Exception:  # pylint: disable=broad-except # nosec B110
                pass

        return HTML(
            f'<b>CAI</b> | <style bg="blue">Press Ctrl+L to clear screen'
            f'</style> | <style bg="green">Use ↑↓ for history</style>'
            f'{active_machine}')

    # Show welcome message with tips
    console.print(Panel(
        "[cyan]Welcome to CAI REPL![/cyan]\n\n"
        "[green]• Use arrow keys ↑↓ to navigate command history[/green]\n"
        "[green]• Press Tab for command completion[/green]\n"
        "[green]• Type /help for available commands[/green]\n"
        "[green]• Type /help aliases for command shortcuts[/green]\n"
        "[green]• Press Ctrl+L to clear the screen[/green]\n"
        "[green]• Press Ctrl+C to exit[/green]",
        title="Quick Tips",
        border_style="blue"
    ))

    while True:
        try:
            if ctf and len(messages) == 1:
                pass
            else:
                user_input = prompt(
                    [('class:prompt', 'CAI> ')],
                    completer=command_completer,
                    style=cli_style,
                    history=FileHistory(str(history_file)),
                    auto_suggest=AutoSuggestFromHistory(),
                    key_bindings=kb,
                    # bottom_toolbar=get_bottom_toolbar,
                    complete_in_thread=True,
                    complete_while_typing=False,  # Better performance
                    mouse_support=False  # Better performance
                )

                # Log user input
                log_interaction("user", user_input)

                # Handle commands
                if user_input.startswith('/') or user_input.startswith('$'):
                    parts = user_input.strip().split()
                    command = parts[0]
                    args = parts[1:] if len(parts) > 1 else None

                    # Handle the command
                    if handle_command(command, args):
                        # # Ensure global handler is active after any command
                        # signal.signal(signal.SIGINT, signal_handler)
                        continue

                    # If we get here, command wasn't handled correctly
                    console.print(f"[red]Unknown command: {command}[/red]")
                    continue

                # If not a command, add as message to agent
                messages.append({"role": "user", "content": user_input})

            # Show a spinner while waiting for the response
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:

                task = progress.add_task(   # noqa: F841
                    description="Thinking",
                    total=None)

            response = client.run(
                agent=agent,
                messages=messages,
                context_variables=context_variables or {},
                stream=stream,
                debug=debug,
                max_turns=max_turns,
            )

            messages = response.messages

            # Log assistant response
            if messages and len(messages) > 0:
                last_message = messages[-1]
                if last_message.get(
                        "role") == "assistant" and last_message.get("content"):
                    log_interaction("assistant", last_message["content"])

            if response.agent:
                agent = response.agent
        except KeyboardInterrupt:
            if is_caiextensions_report_available and os.getenv("CAI_REPORT"):
                # Show a spinner while generating the report
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    transient=True,
                ) as progress:
                    progress.add_task(
                        description="Generating report...", total=None)

                    from caiextensions.report.common import create_report
                    report_type = os.environ.get("CAI_REPORT", "ctf").lower()

                    if report_type == "pentesting":
                        from caiextensions.report.pentesting.pentesting_agent import reporter_agent
                        template = str(
                            files('caiextensions.report.pentesting') / 'template.md')
                    elif report_type == "nis2":
                        from caiextensions.report.nis2.nis2_report_agent import reporter_agent
                        template = str(
                            files('caiextensions.report.nis2') / 'template.md')
                    else:
                        from caiextensions.report.ctf.ctf_reporter_agent import reporter_agent
                        template = str(
                            files('caiextensions.report.ctf') / 'template.md')

                    client = CAI(
                        state_agent=state_agent,
                        force_until_flag=False)
                response_report = client.run(
                    agent=reporter_agent,
                    messages=[{
                        "role": "user",
                        "content": "Do a report from " +
                        "\n".join(
                                msg['content'] for msg in response.messages
                                if msg.get('content') is not None
                        )
                    }],
                    debug=float(os.environ.get('CAI_DEBUG', '2')),
                    max_turns=float(
                        os.environ.get(
                            'CAI_MAX_TURNS', 'inf')),
                )

                if messages_init:
                    response.messages.insert(0, messages_init[0])
                report_data = json.loads(
                    response_report.messages[0]['content'])
                report_data["history"] = json.dumps(
                    response.messages, indent=4)
                report_path = create_report(report_data, template)

                console.print(
                    f"[green]Report generated successfully: {report_path}"
                    f"[/green]")

            # Log end of session
            with open(session_log, "a", encoding="utf-8") as f:
                f.write(
                    f"\nSession ended at {
                        datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    f"\n")

            break
