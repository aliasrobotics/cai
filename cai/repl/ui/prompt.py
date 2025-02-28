"""
Module for CAI REPL prompt functionality.
"""
from prompt_toolkit import prompt  # pylint: disable=import-error
from prompt_toolkit.history import FileHistory  # pylint: disable=import-error
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory  # pylint: disable=import-error
from prompt_toolkit.styles import Style  # pylint: disable=import-error
from prompt_toolkit.formatted_text import HTML  # pylint: disable=import-error
from cai.repl.commands import FuzzyCommandCompleter


def get_command_shadow(text):
    """Get command shadow suggestion."""
    shadow = FuzzyCommandCompleter().get_command_shadow(text)
    if shadow and shadow.startswith(text):
        return shadow[len(text):]
    return ""


def create_prompt_style():
    """Create a style for the CLI."""
    return Style.from_dict({
        'prompt': 'bold cyan',
        'completion-menu': 'bg:#2b2b2b #ffffff',
        'completion-menu.completion': 'bg:#2b2b2b #ffffff',
        'completion-menu.completion.current': 'bg:#004b6b #ffffff',
        'scrollbar.background': 'bg:#2b2b2b',
        'scrollbar.button': 'bg:#004b6b',
    })


def get_user_input(
    command_completer,
    key_bindings,
    history_file,
    toolbar_func,
    current_text
):
    """
    Get user input with all prompt features.

    Args:
        command_completer: Command completer instance
        key_bindings: Key bindings instance
        history_file: Path to history file
        toolbar_func: Function to get toolbar content
        current_text: Reference to current text for command shadowing

    Returns:
        User input string
    """
    # Function to update current text and get command shadow
    def get_rprompt():
        """Get the right prompt with command shadow."""
        shadow = get_command_shadow(current_text[0])
        return HTML(f'<ansigray>{shadow}</ansigray>')

    # Get user input with all features
    return prompt(
        [('class:prompt', 'CAI> ')],
        completer=command_completer,
        style=create_prompt_style(),
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
        key_bindings=key_bindings,
        bottom_toolbar=toolbar_func,
        complete_in_thread=True,
        complete_while_typing=True,  # Enable real-time completion
        mouse_support=False,  # Enable mouse support for menu navigation
        enable_system_prompt=True,  # Enable shadow prediction
        enable_suspend=True,  # Allow suspending with Ctrl+Z
        enable_open_in_editor=True,  # Allow editing with Ctrl+X Ctrl+E
        rprompt=get_rprompt
    )
