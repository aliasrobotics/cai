"""
Module for CAI REPL prompt functionality.
"""
import time
from functools import lru_cache
from prompt_toolkit import prompt  # pylint: disable=import-error
from prompt_toolkit.history import FileHistory  # pylint: disable=import-error
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory  # pylint: disable=import-error # noqa: E501
from prompt_toolkit.styles import Style  # pylint: disable=import-error
from prompt_toolkit.formatted_text import HTML  # pylint: disable=import-error
from cai.repl.commands import FuzzyCommandCompleter


# Cache for command shadow to avoid recalculating it too frequently
shadow_cache = {
    'text': '',
    'result': '',
    'last_update': 0,
    'update_interval': 0.1  # Update at most every 100ms
}


@lru_cache(maxsize=32)
def get_command_shadow_cached(text):
    """Get command shadow suggestion with caching for repeated calls."""
    return FuzzyCommandCompleter().get_command_shadow(text)


def get_command_shadow(text):
    """Get command shadow suggestion with throttling."""
    current_time = time.time()
    
    # If the text hasn't changed, return the cached result
    if text == shadow_cache['text']:
        return shadow_cache['result']
    
    # If we've updated recently, return the cached result
    if (current_time - shadow_cache['last_update'] < shadow_cache['update_interval'] 
            and shadow_cache['result']):
        return shadow_cache['result']
    
    # Update the cache
    shadow = get_command_shadow_cached(text)
    if shadow and shadow.startswith(text):
        result = shadow[len(text):]
    else:
        result = ""
    
    # Store in cache
    shadow_cache['text'] = text
    shadow_cache['result'] = result
    shadow_cache['last_update'] = current_time
    
    return result


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
        if not shadow:
            return None
        return HTML(f'<ansigray>{shadow}</ansigray>')

    # Get user input with all features
    return prompt(
        [('class:prompt', 'CAI> ')],  # Simple prompt text without toolbar
        completer=command_completer,
        style=create_prompt_style(),
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
        key_bindings=key_bindings,
        bottom_toolbar=toolbar_func,  # This is correct - toolbar only at the bottom
        complete_in_thread=True,
        complete_while_typing=True,  # Enable real-time completion
        enable_system_prompt=True,  # Enable shadow prediction
        mouse_support=False,  # Enable mouse support for menu navigation
        enable_suspend=True,  # Allow suspending with Ctrl+Z
        enable_open_in_editor=True,  # Allow editing with Ctrl+X Ctrl+E
        multiline=False,  # Enable multiline input
        rprompt=get_rprompt,  # Missing comma here
        color_depth=None,  # Auto-detect color support
    )
