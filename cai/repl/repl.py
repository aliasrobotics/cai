"""
This module provides a REPL interface for testing and
interacting with CAI agents.
"""
# Standard library imports
import json
import os
import sys
from configparser import ConfigParser
from importlib.resources import files

# Third party imports
from mako.template import Template  # pylint: disable=import-error
from prompt_toolkit import prompt  # pylint: disable=import-error
from prompt_toolkit.completion import (  # pylint: disable=import-error # noqa: E501
    Completer,
    Completion
)
from prompt_toolkit.styles import Style  # pylint: disable=import-error
from wasabi import color  # pylint: disable=import-error

# Local imports
from caiextensions.report.common import create_report  # pylint: disable=import-error,no-name-in-module # noqa: E501
from cai import is_caiextensions_report_available
from cai.core import CAI  # pylint: disable=import-error
from cai.rag.vector_db import QdrantConnector

# Global variables
client = None  # pylint: disable=invalid-name

COMMANDS = {
    "/memory": [
        "list",
        "load",
        "delete"  # Added delete command
    ],
    "/help": [
        "memory",
        "agents",
        "graph"
    ],
    "/graph": [],
    "/exit": []
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
{color('/memory list', fg='yellow')}
    List all memory collections
{color('/memory load <collection>', fg='yellow')}
    Load a memory collection
{color('/memory delete <collection>', fg='yellow')}
    Delete a memory collection

    <{color('collection', bold=True)}>:
    - {color('<CTF_NAME>', fg='yellow')}
        Episodic memory for a specific CTF
        (e.g. {color('baby_first', bold=True)})
    - {color('_all_', fg='yellow')}
        Semantic memory across all CTFs

{color('Graph Commands:', fg='blue', bold=True, underline=True)}
{color('/graph', fg='blue')}
    Show the graph of the current memory collection

{color('/exit', fg='red')}
    Exit CAI.
""")
    return True


def handle_graph_show():
    """Handle /graph show command"""
    if not client or not client._graph:  # pylint: disable=protected-access # noqa: E501
        print("No conversation graph available.")
        return True

    try:
        print("\nConversation Graph:")
        print("------------------")
        print(client._graph.ascii())  # pylint: disable=protected-access # noqa: E501
        print()
        return True
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error displaying graph: {e}")
        return False


def handle_command(command, args=None):  # pylint: disable=too-many-return-statements # noqa: E501
    """Handle CLI commands"""
    if command == "/memory list":
        return handle_memory_list()
    if command.startswith("/memory load"):
        if not args:
            print("Error: Collection name required")
            return False
        return handle_memory_load(args[0])
    if command.startswith("/graph"):
        return handle_graph_show()
    if command.startswith("/help"):
        return handle_help()
    if command.startswith("/exit"):
        sys.exit(0)
    return False


class FuzzyCommandCompleter(Completer):  # pylint: disable=too-many-branches,too-many-statements,too-few-public-methods,line-too-long # noqa: E501
    """
    A command completer that provides fuzzy completion for the REPL commands.

    This class implements command completion functionality for the CLI:
    - Main command completion (e.g. /memory)
    - Subcommand completion (e.g. /memory list)
    - Fuzzy matching for more flexible completion
    - Color-coded suggestions using ANSI colors

    The completer enhances the user experience by providing real-time
    suggestions as users type commands, making the CLI more intuitive and
    user-friendly.
    """

    def get_completions(self, document, complete_event):  # pylint: disable=unused-argument # noqa: E501
        """
        Predicts the next command based on the current text in the document.

        Args:
            document: The current document state
            complete_event: The event that triggered the completion
        """
        text = document.text_before_cursor.strip()
        words = text.split()

        # Si no hay texto, mostrar todos los comandos principales
        if not text:
            for cmd in COMMANDS:
                yield Completion(cmd,
                                 start_position=0,
                                 style="fg:ansicyan bold")
            return

        # Si el texto empieza con /, procesar comandos
        if text.startswith('/'):
            current_word = words[-1]

            # Si solo hay una palabra, mostrar comandos principales que
            # coincidan
            if len(words) == 1:
                for cmd in COMMANDS:
                    if cmd[1:].startswith(
                            current_word[1:]):  # Ignorar el / inicial
                        yield Completion(cmd,
                                         start_position=-len(current_word),
                                         style="fg:ansicyan bold")

            # Si hay dos palabras, mostrar subcomandos del comando
            # principal
            elif len(words) == 2:
                cmd = words[0]
                if cmd in COMMANDS:
                    for subcmd in COMMANDS[cmd]:
                        if subcmd.startswith(current_word):
                            yield Completion(subcmd,
                                             start_position=-len(current_word),
                                             style="fg:ansiyellow bold")


def run_demo_loop(  # pylint: disable=too-many-locals,too-many-nested-blocks,too-many-arguments,too-many-branches,too-many-statements  # noqa: E501
    starting_agent,
    context_variables=None,
    stream=False,
    debug=False,
    max_turns=float('inf'),
    ctf=None,  # Add CTF parameter
    state_agent=None  # Add state agent parameter
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
            "content": Template(  # nosec B702 - Template content is trusted
                filename="cai/prompts/core/user_master_template.md").render(
                    ctf=ctf,
                    challenge=challenge,
                    ip=ctf.get_ip() if ctf else None
            )
        }]

        messages_init = messages
    agent = starting_agent

    cli_style = Style.from_dict({
        'prompt': '#ff0066 bold',
        '': '#ffcc00',
    })
    command_completer = FuzzyCommandCompleter()

    while True:
        try:
            if ctf and len(messages) == 1:
                pass
            else:
                user_input = prompt([('class:prompt', 'CAI> ')],
                                    completer=command_completer,
                                    style=cli_style)

                # Handle commands
                if user_input.startswith('/'):
                    parts = user_input.strip().split()
                    command = parts[0]
                    if len(parts) > 1:
                        command += f" {parts[1]}"
                    args = parts[2:] if len(parts) > 2 else None

                    if handle_command(command, args):
                        continue

                messages.append({"role": "user", "content": user_input})

            response = client.run(
                agent=agent,
                messages=messages,
                context_variables=context_variables or {},
                stream=stream,
                debug=debug,
                max_turns=max_turns,
            )
            messages = response.messages
            if response.agent:
                agent = response.agent
        except KeyboardInterrupt:
            if is_caiextensions_report_available and os.getenv("CAI_REPORT"):
                if os.getenv("CAI_REPORT", "ctf").lower() == "pentesting":
                    from caiextensions.report.pentesting.pentesting_agent import reporter_agent  # pylint: disable=import-error,import-outside-toplevel,unused-import,line-too-long,no-name-in-module # noqa: E501
                    template = str(
                        files('caiextensions.report.pentesting') /
                        'template.md')
                elif os.getenv("CAI_REPORT", "ctf").lower() == "nis2":
                    from caiextensions.report.nis2.nis2_report_agent import reporter_agent  # pylint: disable=import-error,import-outside-toplevel,unused-import,line-too-long,no-name-in-module # noqa: E501
                    template = str(
                        files('caiextensions.report.nis2') /
                        'template.md')
                else:
                    from caiextensions.report.ctf.ctf_reporter_agent import reporter_agent  # pylint: disable=import-error,import-outside-toplevel,unused-import,line-too-long,no-name-in-module   # noqa: E501
                    template = str(
                        files('caiextensions.report.ctf') /
                        'template.md')

                client = CAI(state_agent=state_agent, force_until_flag=False)
                response_report = client.run(
                    agent=reporter_agent,
                    messages=[{"role": "user", "content": "Do a report from " +
                               "\n".join(
                                   msg['content'] for msg in response.messages
                                   if msg.get('content') is not None
                               )}],
                    debug=float(os.getenv('CAI_DEBUG', '2')),
                    max_turns=float(os.getenv('CAI_MAX_TURNS', 'inf')),
                )

                if messages_init:
                    response.messages.insert(0, messages_init[0])
                report_data = json.loads(
                    response_report.messages[0]['content'])
                report_data["history"] = json.dumps(
                    response.messages, indent=4)
                create_report(report_data, template)
            break
