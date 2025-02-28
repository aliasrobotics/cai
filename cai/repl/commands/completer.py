"""
Command completer for CAI REPL.
This module provides a fuzzy command completer with autocompletion menu and
command shadowing.
"""
# Standard library imports
import datetime
from typing import (
    List,
    Optional  # Dict and Any removed as unused
)

# Third-party imports
import requests  # pylint: disable=import-error,unused-import,line-too-long # noqa: E501
from prompt_toolkit.completion import (  # pylint: disable=import-error
    Completer,
    Completion
)
from prompt_toolkit.formatted_text import HTML  # pylint: disable=import-error
from prompt_toolkit.styles import Style  # pylint: disable=import-error
from rich.console import Console  # pylint: disable=import-error

from cai.core import get_ollama_api_base
from cai.repl.commands.base import (
    COMMANDS,
    COMMAND_ALIASES
)

console = Console()


class FuzzyCommandCompleter(Completer):
    """Command completer with fuzzy matching for the REPL.

    This advanced completer provides intelligent suggestions for commands,
    subcommands, and arguments based on what the user is typing.
    It supports fuzzy matching to find commands even with typos.

    Features:
    - Fuzzy matching for commands and subcommands
    - Autocompletion menu with descriptions
    - Command shadowing (showing hints for previously used commands)
    - Model completion for the /model command
    """

    def __init__(self):
        """Initialize the command completer with cached model information."""
        super().__init__()
        self.cached_models = []
        self.cached_model_numbers = {}  # Map of numbers to model names
        self.last_model_fetch = datetime.datetime.now() - datetime.timedelta(
            minutes=10)
        self.command_history = {}  # Store command usage frequency
        self.fetch_ollama_models()

        # Styling for the completion menu
        self.completion_style = Style.from_dict({
            'completion-menu': 'bg:#2b2b2b #ffffff',
            'completion-menu.completion': 'bg:#2b2b2b #ffffff',
            'completion-menu.completion.current': 'bg:#004b6b #ffffff',
            'scrollbar.background': 'bg:#2b2b2b',
            'scrollbar.button': 'bg:#004b6b',
        })

    def fetch_ollama_models(self):  # pylint: disable=too-many-branches,too-many-statements,inconsistent-return-statements,line-too-long # noqa: E501
        """Fetch available models from Ollama if it's running."""
        # Only fetch every 60 seconds to avoid excessive API calls
        now = datetime.datetime.now()
        if (now - self.last_model_fetch).total_seconds() < 60:
            return

        self.last_model_fetch = now
        ollama_models = []

        try:
            # Get Ollama models with a short timeout to prevent hanging
            api_base = get_ollama_api_base()
            response = requests.get(
                f"{api_base.replace('/v1', '')}/api/tags", timeout=1)

            if response.status_code == 200:
                data = response.json()
                if 'models' in data:
                    models = data['models']
                else:
                    # Fallback for older Ollama versions
                    models = data.get('items', [])

                return [(model.get('name', ''), []) for model in models]
        except Exception:  # pylint: disable=broad-except
            # Silently fail if Ollama is not available
            # This is acceptable as Ollama is optional and we don't want to
            # disrupt the user experience if it's not running
            return []

        # Standard models always available
        standard_models = [
            # Claude 3.7 models
            "claude-3-7-sonnet-20250219",

            # Claude 3.5 models
            "claude-3-5-sonnet-20240620",
            "claude-3-5-20241122",

            # Claude 3 models
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",

            # OpenAI O-series models
            "o1",
            "o1-mini",
            "o3-mini",

            # OpenAI GPT models
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-3.5-turbo",

            # DeepSeek models
            "deepseek-v3",
            "deepseek-r1"
        ]

        # Combine standard models with Ollama models
        self.cached_models = standard_models + ollama_models

        # Create number mappings for models (1-based indexing)
        self.cached_model_numbers = {}
        for i, model in enumerate(self.cached_models, 1):
            self.cached_model_numbers[str(i)] = model

    def record_command_usage(self, command: str):
        """Record command usage for command shadowing.

        Args:
            command: The command that was used
        """
        if command.startswith('/'):
            # Extract the main command
            parts = command.split()
            main_command = parts[0]

            # Update usage count
            if main_command in self.command_history:
                self.command_history[main_command] += 1
            else:
                self.command_history[main_command] = 1

    def get_command_descriptions(self):
        """Get descriptions for all commands.

        Returns:
            A dictionary mapping command names to descriptions
        """
        return {cmd.name: cmd.description for cmd in COMMANDS.values()}

    def get_subcommand_descriptions(self):
        """Get descriptions for all subcommands.

        Returns:
            A dictionary mapping command paths to descriptions
        """
        descriptions = {}
        for cmd in COMMANDS.values():
            for subcmd in cmd.get_subcommands():
                key = f"{cmd.name} {subcmd}"
                descriptions[key] = cmd.get_subcommand_description(subcmd)
        return descriptions

    def get_all_commands(self):
        """Get all commands and their subcommands.

        Returns:
            A dictionary mapping command names to lists of subcommand names
        """
        return {cmd.name: cmd.get_subcommands() for cmd in COMMANDS.values()}

    def get_command_suggestions(self, current_word: str) -> List[Completion]:
        """Get command suggestions with fuzzy matching.

        Args:
            current_word: The current word being typed

        Returns:
            A list of completions for commands
        """
        suggestions = []

        # Get command descriptions
        command_descriptions = self.get_command_descriptions()

        # Sort commands by usage frequency (for command shadowing)
        sorted_commands = sorted(
            command_descriptions.items(),
            key=lambda x: self.command_history.get(x[0], 0),
            reverse=True
        )

        # Add command completions
        for cmd, description in sorted_commands:
            # Exact prefix match
            if cmd.startswith(current_word):
                suggestions.append(Completion(
                    cmd,
                    start_position=-len(current_word),
                    display=HTML(
                        f"<ansicyan><b>{cmd:<15}</b></ansicyan> "
                        f"{description}"),
                    style="fg:ansicyan bold"
                ))
            # Fuzzy match (contains the substring)
            elif current_word in cmd and not cmd.startswith(current_word):
                suggestions.append(Completion(
                    cmd,
                    start_position=-len(current_word),
                    display=HTML(
                        f"<ansicyan>{cmd:<15}</ansicyan> {description}"),
                    style="fg:ansicyan"
                ))

        # Add alias completions
        for alias, cmd in sorted(COMMAND_ALIASES.items()):
            cmd_description = command_descriptions.get(cmd, "")
            if alias.startswith(current_word):
                suggestions.append(Completion(
                    alias,
                    start_position=-len(current_word),
                    display=HTML(
                        f"<ansigreen><b>{alias:<15}</b></ansigreen> "
                        f"{cmd} - {cmd_description}"),
                    style="fg:ansigreen bold"
                ))
            elif current_word in alias and not alias.startswith(current_word):
                suggestions.append(Completion(
                    alias,
                    start_position=-len(current_word),
                    display=HTML(
                        f"<ansigreen>{alias:<15}</ansigreen> "
                        f"{cmd} - {cmd_description}"),
                    style="fg:ansigreen"
                ))

        return suggestions

    def get_subcommand_suggestions(
            self, cmd: str, current_word: str) -> List[Completion]:
        """Get subcommand suggestions with fuzzy matching.

        Args:
            cmd: The main command
            current_word: The current word being typed

        Returns:
            A list of completions for subcommands
        """
        suggestions = []

        # If using an alias, get the real command
        cmd = COMMAND_ALIASES.get(cmd, cmd)

        all_commands = self.get_all_commands()
        subcommand_descriptions = self.get_subcommand_descriptions()

        if cmd in all_commands:
            for subcmd in sorted(all_commands[cmd]):
                # Get description for this subcommand if available
                subcmd_description = subcommand_descriptions.get(
                    f"{cmd} {subcmd}", "")

                # Exact prefix match
                if subcmd.startswith(current_word):
                    suggestions.append(Completion(
                        subcmd,
                        start_position=-len(current_word),
                        display=HTML(
                            f"<ansiyellow><b>{subcmd:<15}</b></ansiyellow> "
                            f"{subcmd_description}"),
                        style="fg:ansiyellow bold"
                    ))
                # Fuzzy match
                elif (current_word in subcmd and
                      not subcmd.startswith(current_word)):
                    suggestions.append(Completion(
                        subcmd,
                        start_position=-len(current_word),
                        display=HTML(
                            f"<ansiyellow>{subcmd:<15}</ansiyellow> "
                            f"{subcmd_description}"),
                        style="fg:ansiyellow"
                    ))

        return suggestions

    def get_model_suggestions(self, current_word: str) -> List[Completion]:
        """Get model suggestions for the /model command.

        Args:
            current_word: The current word being typed

        Returns:
            A list of completions for models
        """
        suggestions = []

        # First try to complete model numbers
        for num, model_name in self.cached_model_numbers.items():
            if num.startswith(current_word):
                suggestions.append(Completion(
                    num,
                    start_position=-len(current_word),
                    display=HTML(
                        f"<ansiwhite><b>{num:<3}</b></ansiwhite> "
                        f"{model_name}"),
                    style="fg:ansiwhite bold"
                ))

        # Then try to complete model names
        for model in self.cached_models:
            if model.startswith(current_word):
                suggestions.append(Completion(
                    model,
                    start_position=-len(current_word),
                    display=HTML(
                        f"<ansimagenta><b>{model}</b></ansimagenta>"),
                    style="fg:ansimagenta bold"
                ))
            elif (current_word.lower() in model.lower() and
                  not model.startswith(current_word)):
                suggestions.append(Completion(
                    model,
                    start_position=-len(current_word),
                    display=HTML(f"<ansimagenta>{model}</ansimagenta>"),
                    style="fg:ansimagenta"
                ))

        return suggestions

    def get_command_shadow(self, text: str) -> Optional[str]:
        """Get a command shadow suggestion based on command history.

        This method returns a suggestion for command shadowing based on
        the current input and command usage history.

        Args:
            text: The current input text

        Returns:
            A suggested command completion or None if no suggestion
        """
        if not text or not text.startswith('/'):
            return None

        # Find commands that start with the current input
        matching_commands = []
        for cmd, count in self.command_history.items():
            if cmd.startswith(text) and cmd != text:
                matching_commands.append((cmd, count))

        # Sort by usage count (descending)
        matching_commands.sort(key=lambda x: x[1], reverse=True)

        # Return the most frequently used command
        if matching_commands:
            return matching_commands[0][0]

        return None

    # pylint: disable=unused-argument
    def get_completions(self, document, complete_event):
        """Get completions for the current document
        with fuzzy matching support.

        Args:
            document: The document to complete
            complete_event: The completion event

        Returns:
            A generator of completions
        """
        text = document.text_before_cursor.strip()
        words = text.split()

        # Refresh Ollama models periodically
        self.fetch_ollama_models()

        if not text:
            # Show all main commands with descriptions
            command_descriptions = self.get_command_descriptions()

            # Sort commands by usage frequency (for command shadowing)
            sorted_commands = sorted(
                command_descriptions.items(),
                key=lambda x: self.command_history.get(x[0], 0),
                reverse=True
            )

            for cmd, description in sorted_commands:
                yield Completion(
                    cmd,
                    start_position=0,
                    display=HTML(
                        f"<ansicyan><b>{cmd:<15}</b></ansicyan> "
                        f"{description}"),
                    style="fg:ansicyan bold"
                )
            return

        if text.startswith('/'):
            current_word = words[-1]

            # Main command completion (first word)
            if len(words) == 1:
                # Get command suggestions
                yield from self.get_command_suggestions(current_word)

            # Subcommand completion (second word)
            elif len(words) == 2:
                cmd = words[0]

                # Special handling for model command
                if cmd in ["/model", "/mod"]:
                    yield from self.get_model_suggestions(current_word)
                else:
                    # Get subcommand suggestions
                    yield from self.get_subcommand_suggestions(
                        cmd, current_word)
