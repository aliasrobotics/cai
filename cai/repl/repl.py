"""
This module provides a REPL interface for testing and
interacting with CAI agents.
"""
# Standard library imports

import json
import os
from importlib.resources import files
import datetime
import time

# Third party imports
from mako.template import Template  # pylint: disable=import-error
from wasabi import color  # pylint: disable=import-error
from rich.console import Console  # pylint: disable=import-error
from rich.panel import Panel  # pylint: disable=import-error
from rich.box import ROUNDED  # pylint: disable=import-error
from rich.progress import (  # pylint: disable=import-error
    Progress,
    SpinnerColumn,
    TextColumn
)
from rich.text import Text  # pylint: disable=import-error
from rich.console import Group  # pylint: disable=import-error

# Local imports
from cai import (
    is_caiextensions_report_available,
    is_caiextensions_platform_available
)
from cai.core import CAI  # pylint: disable=import-error
from cai.util import GLOBAL_START_TIME, format_time
# Import command system
from cai.repl.commands import (
    handle_command as commands_handle_command,
    FuzzyCommandCompleter
)

# Import UI modules
from cai.repl.ui.banner import display_banner
from cai.repl.ui.toolbar import get_toolbar_with_refresh
from cai.repl.ui.keybindings import create_key_bindings
from cai.repl.ui.logging import setup_session_logging
from cai.repl.ui.prompt import get_user_input

if is_caiextensions_platform_available():
    from caiextensions.platform.base import (  # pylint: disable=ungrouped-imports,line-too-long,import-error,unused-import # noqa: E501,F401
        platform_manager
    )

# Global variables
console = Console()
client = None  # pylint: disable=invalid-name
START_TIME = None
current_agent = None  # pylint: disable=invalid-name
agent = None  # pylint: disable=invalid-name
messages = []  # Global messages list to store conversation history


def get_elapsed_time():
    """Get the elapsed time since the start of the session."""
    if START_TIME is None:
        return "0.0s"

    elapsed = time.time() - START_TIME
    return format_time(elapsed)


def display_execution_time():
    """Display the total execution time in a hacker-like style."""
    if START_TIME is None:
        return

    current_time = time.time()
    session_elapsed = current_time - START_TIME
    session_time_str = format_time(session_elapsed)

    # Get global LLM time from CAI instantiation
    llm_time = None
    if GLOBAL_START_TIME is not None:
        llm_time = current_time - GLOBAL_START_TIME
        llm_time_str = format_time(llm_time)
        llm_percentage = (llm_time / session_elapsed) * \
            100 if session_elapsed > 0 else 0

    # Create a panel for the execution time
    content = []
    content.append(
        f"Session Time: {session_time_str}")  # noqa: E501 #pylint: disable=line-too-long
    if llm_time:
        content.append(
            f"LLM Processing Time: [bold yellow]{
                llm_time_str}[/bold yellow] "
            f"[dim]({llm_percentage:.1f}% of session)[/dim]"
        )

    time_panel = Panel(
        Group(*[Text(line) for line in content]),
        border_style="blue",
        box=ROUNDED,
        padding=(0, 1),
        title="[bold]Session Statistics[/bold]",
        title_align="left"
    )
    console.print(time_panel)


def handle_command(command, args=None):
    """Handle CLI commands using the new command system."""
    return commands_handle_command(command, args)


def get_messages():
    """Get the current conversation messages.

    Returns:
        list: The list of conversation messages
    """
    return messages


def run_cai_cli(  # pylint: disable=too-many-arguments,too-many-locals,too-many-branches,too-many-statements # noqa: E501
    starting_agent,
    context_variables=None,
    stream=False,
    debug=False,
    max_turns=float('inf'),
    ctf=None,
    state_agent=None,
    source="cli"  # Add source parameter with default value
) -> None:
    """
    Run the interactive CLI loop for Cybersecurity AI
    (CAI) with enhanced timing and visual feedback.

    This function initializes the CAI environment, displays
    the banner, and manages the interactive session with
    the user. It handles CTF challenges if provided and maintains
    session history and logging.

    Args:
        starting_agent:
            The initial agent to use for the conversation
        context_variables:
            Optional dictionary of context variables to initialize
            the session
        stream:
            Boolean flag to enable/disable streaming responses
            (default: False)
        debug:
            Boolean flag to enable/disable debug output
            (default: False)
        max_turns:
            Maximum number of interaction turns before terminating
            (default: infinity)
        ctf:
            Optional CTF configuration object for Capture The
            Flag challenges
        state_agent:
            Optional state tracking agent for maintaining network state

    Returns:
        None

    Note:
        This function uses global variables for timing
        and client management. Session logs are stored
        in the ~/.cai/history directory.
    """
    # Using globals to maintain state across function calls
    # pylint: disable=global-statement
    global client, START_TIME, current_agent, agent, messages
    START_TIME = time.time()  # Start the global timer
    # Initialize CAI with CTF and state agent if provided
    client = CAI(
        ctf=ctf if os.getenv(
            'CTF_INSIDE',
            "true").lower() == "true" else None,
        state_agent=state_agent,
        source=source)  # Pass source parameter

    # Set the initial active agent
    client.active_agent = starting_agent

    # Initialize the current_agent global variable
    current_agent = starting_agent
    agent = starting_agent  # Initialize the agent variable as well

    # Display CAI banner and welcome message
    display_banner(console)

    # Check for active VPN connection
    if is_caiextensions_platform_available():
        try:
            from caiextensions.platform.htb.cli import (  # pylint: disable=import-error,import-outside-toplevel,line-too-long # noqa: E501
                is_vpn_connected, get_vpn_ip
            )
            if is_vpn_connected():
                console.print(Panel(
                    "\n".join([
                        "[green]VPN Connected[/green]",
                        f"IP: {get_vpn_ip()}",
                        "Use [bold]/platform vpn-status[/bold] to check "
                        "status",
                        "Use [bold]/platform keep-vpn[/bold] to make "
                        "connection persistent"
                    ]),
                    title="HackTheBox VPN Status",
                    border_style="green"
                ))
        except ImportError:
            pass

    messages = []  # Initialize the global messages list
    messages_init = []
    if ctf:
        # Determine which challenge to use
        challenge_key = os.getenv('CTF_CHALLENGE')
        challenges = list(ctf.get_challenges().keys())
        # Use specified challenge if valid, otherwise use first available
        # challenge
        challenge = challenge_key if challenge_key in challenges else (
            challenges[0] if len(challenges) > 0 else None)

        # Display the active challenge information
        if challenge:
            print(color("Testing challenge: ", fg="white", bg="blue")
                  + color(f"'{challenge}'", fg="white", bg="blue"))

        # Create initial message with CTF context using the template
        # This sets up the conversation with necessary CTF details
        messages += [{
            "role": "user",
            "content": Template(  # nosec B702
                filename="cai/prompts/core/user_master_template.md").render(
                    ctf=ctf,
                    challenge=challenge,
                    ip=ctf.get_ip() if ctf else None
            )
        }]

        messages_init = messages.copy()
    current_agent = starting_agent  # Set the global current_agent
    agent = starting_agent  # Set the global agent variable as well

    # Setup session logging to track conversation history
    history_file, session_log, log_interaction = setup_session_logging()

    # Initialize the session log file with metadata
    with open(session_log, "w", encoding="utf-8") as f:
        f.write(
            f"CAI Session started at {
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Version: {os.getenv('CAI_VERSION', 'unknown')}\n")
        if ctf:
            f.write(f"CTF: {ctf.__class__.__name__}\n")
            if challenge:
                f.write(f"Challenge: {challenge}\n")
        f.write("\n")

    # Initialize command completer with fuzzy matching for better UX
    command_completer = FuzzyCommandCompleter()

    # # Display welcome tips
    # #
    # # reconsider in the future if necessary
    # # or alternatively, push into a /tips command
    #
    # display_welcome_tips(console)

    # Main interaction loop
    while True:
        try:
            # Skip user input prompt for the first message in CTF mode
            # This allows the initial CTF context to be sent automatically
            if ctf and len(messages) == 1:
                pass
            else:
                # Create a variable to hold the current text
                # for command shadow (showing command suggestions)
                current_text = ['']

                # Create key bindings for terminal input handling
                kb = create_key_bindings(current_text)

                # Get user input with command completion and history
                user_input = get_user_input(
                    command_completer,
                    kb,
                    history_file,
                    get_toolbar_with_refresh,
                    current_text
                )

                # Record command usage to improve command suggestions over time
                if user_input.startswith('/'):
                    command_completer.record_command_usage(user_input)

                # Log user input to the session log
                log_interaction("user", user_input)

                # Handle special commands (starting with / or $)
                if user_input.startswith('/') or user_input.startswith('$'):
                    parts = user_input.strip().split()
                    command = parts[0]
                    args = parts[1:] if len(parts) > 1 else None

                    # Process the command with the handler
                    if handle_command(command, args):
                        continue  # Command was handled, continue
                        # to next iteration

                    # If command wasn't recognized, show error
                    console.print(f"[red]Unknown command: {command}[/red]")
                    continue

                # If not a command, add as a regular message to the
                # conversation
                messages.append({"role": "user", "content": user_input})

            # Show a spinner while waiting for the agent's response
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:

                task = progress.add_task(   # noqa: F841,E501 #pylint: disable=unused-variable,line-too-long
                    description="Thinking",
                    total=None)

            # Process the conversation with the agent
            response = client.run(
                agent=current_agent,  # Use the global current_agent
                messages=messages,
                context_variables=context_variables or {},
                stream=stream,
                debug=debug,
                max_turns=float(os.getenv('CAI_MAX_TURNS', str(max_turns))),
                model_override=os.getenv('CAI_MODEL', None),
            )

            messages.extend(response.messages)
            # Update both agent variables if the response contains a new agent
            if response.agent:
                agent = response.agent
                current_agent = response.agent
        except KeyboardInterrupt:
            # Handle report generation when user interrupts the session
            if is_caiextensions_report_available and os.getenv("CAI_REPORT"):
                # Show a spinner while generating the report
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    transient=True,
                ) as progress:
                    progress.add_task(
                        description="Generating report...", total=None)

                    # Import the appropriate report module based on report type
                    from caiextensions.report.common import create_report  # pylint: disable=import-error,unused-import,line-too-long,import-outside-toplevel,no-name-in-module # noqa: E501
                    report_type = os.environ.get("CAI_REPORT", "ctf").lower()

                    # Select the appropriate report agent and template based on
                    # report type
                    if report_type == "pentesting":
                        from caiextensions.report.pentesting.pentesting_agent import reporter_agent  # pylint: disable=import-error,unused-import,line-too-long,import-outside-toplevel,no-name-in-module # noqa: E501
                        template = str(
                            files('caiextensions.report.pentesting') /
                            'template.md')
                    elif report_type == "nis2":
                        from caiextensions.report.nis2.nis2_report_agent import reporter_agent  # pylint: disable=import-error,unused-import,line-too-long,import-outside-toplevel,no-name-in-module # noqa: E501
                        template = str(
                            files('caiextensions.report.nis2') /
                            'template.md')
                    else:
                        from caiextensions.report.ctf.ctf_reporter_agent import reporter_agent  # pylint: disable=import-error,unused-import,line-too-long,import-outside-toplevel,no-name-in-module # noqa: E501
                        template = str(
                            files('caiextensions.report.ctf') /
                            'template.md')

                    # Initialize a new CAI client for report generation
                    client = CAI(
                        state_agent=state_agent,
                        force_until_flag=False)

                # Generate the report by sending the conversation history to
                # the reporter agent
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

                # Add the initial context message back to the history
                # if it exists. This ensures the report includes the
                # original CTF setup
                if messages_init:
                    response.messages.insert(0, messages_init[0])

                # Parse the report data and include the full conversation
                # history
                report_data = json.loads(
                    response_report.messages[0]['content'])
                report_data["history"] = json.dumps(
                    response.messages, indent=4)

                # Generate the final report using the template
                create_report(report_data, template)

            # Log the end of the session
            with open(session_log, "a", encoding="utf-8") as f:
                f.write(
                    f"\nSession ended at {
                        datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    f"\n")

            # Display the total execution time before exiting
            display_execution_time()
            break
