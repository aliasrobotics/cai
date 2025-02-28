"""
This module provides a REPL interface for testing and
interacting with CAI agents.
"""
# Standard library imports
import json
import os
from importlib.resources import files
import datetime

# Third party imports
from mako.template import Template  # pylint: disable=import-error
from wasabi import color  # pylint: disable=import-error
from rich.console import Console  # pylint: disable=import-error
from rich.progress import (  # pylint: disable=import-error
    Progress,
    SpinnerColumn,
    TextColumn
)

# Local imports
from cai import (
    is_caiextensions_report_available,
    is_caiextensions_platform_available
)
from cai.core import CAI  # pylint: disable=import-error

# Import command system
from cai.repl.commands import (
    handle_command as commands_handle_command,
    FuzzyCommandCompleter
)

# Import UI modules
from cai.repl.ui.banner import display_banner, display_welcome_tips
from cai.repl.ui.toolbar import get_toolbar_with_refresh
from cai.repl.ui.keybindings import create_key_bindings
from cai.repl.ui.logging import setup_session_logging
from cai.repl.ui.prompt import get_user_input

if is_caiextensions_platform_available():
    from caiextensions.platform.base import (  # pylint: disable=ungrouped-imports,line-too-long,import-error,unused-import # noqa: E501,F401
        platform_manager
    )

# Global variables
client = None  # pylint: disable=invalid-name
console = Console()


def handle_command(command, args=None):
    """Handle CLI commands using the new command system."""
    return commands_handle_command(command, args)


def run_demo_loop(  # pylint: disable=too-many-arguments,too-many-locals,too-many-branches,too-many-statements # noqa: E501
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

    # Display banner and welcome message
    display_banner(console)

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

    # Setup logging
    history_file, session_log, log_interaction = setup_session_logging()

    # Log start of session
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

    # Create command completer with fuzzy matching
    command_completer = FuzzyCommandCompleter()

    # Display welcome tips
    display_welcome_tips(console)

    while True:
        try:
            if ctf and len(messages) == 1:
                pass
            else:
                # Create a variable to hold the current text for command
                # shadow
                current_text = ['']

                # Create key bindings
                kb = create_key_bindings(current_text)

                # Get user input
                user_input = get_user_input(
                    command_completer,
                    kb,
                    history_file,
                    get_toolbar_with_refresh,
                    current_text
                )

                # Record command usage for command shadowing
                if user_input.startswith('/'):
                    command_completer.record_command_usage(user_input)

                # Log user input
                log_interaction("user", user_input)

                # Handle commands
                if user_input.startswith('/') or user_input.startswith('$'):
                    parts = user_input.strip().split()
                    command = parts[0]
                    args = parts[1:] if len(parts) > 1 else None

                    # Handle the command
                    if handle_command(command, args):
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

                task = progress.add_task(   # noqa: F841 #pylint: disable=unused-variable # noqa: E501
                    description="Thinking",
                    total=None)

            response = client.run(
                agent=agent,
                messages=messages,
                context_variables=context_variables or {},
                stream=stream,
                debug=debug,
                max_turns=float(os.getenv('CAI_MAX_TURNS', str(max_turns))),
                model_override=os.getenv('CAI_MODEL', None),
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

                    from caiextensions.report.common import create_report  # pylint: disable=import-error,unused-import,line-too-long,import-outside-toplevel,no-name-in-module # noqa: E501
                    report_type = os.environ.get("CAI_REPORT", "ctf").lower()

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
