"""
Module for CAI REPL key bindings.
"""
import os
import subprocess  # nosec B404 - Required for screen clearing
# pylint: disable=import-error
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from cai.repl.commands import FuzzyCommandCompleter


def create_key_bindings(current_text):
    """
    Create key bindings for the REPL.

    Args:
        current_text: Reference to the current text for command shadowing

    Returns:
        KeyBindings object with configured bindings
    """
    kb = KeyBindings()

    @kb.add('c-l')
    def _(event):  # pylint: disable=unused-argument
        """Clear the screen."""
        # Replace os.system with subprocess.run to avoid shell injection
        if os.name == 'nt':
            # Using fixed commands with shell=False is safe
            subprocess.run(
                ['cls'],
                shell=False,
                check=False)  # nosec B603 B607
        else:
            # Using fixed commands with shell=False is safe
            subprocess.run(
                ['clear'],
                shell=False,
                check=False)  # nosec B603 B607

    @kb.add('tab')
    def handle_tab(event):
        """Handle tab key to show completions menu or complete command."""
        buffer = event.current_buffer
        text = buffer.text

        # Update current text for shadow
        current_text[0] = text

        # First check if we have a history suggestion
        history_suggestion = None
        if text:
            # Get suggestion from history
            auto_suggest = AutoSuggestFromHistory()
            suggestion = auto_suggest.get_suggestion(buffer, buffer.document)
            if suggestion and suggestion.text:
                history_suggestion = text + suggestion.text

        # If we have a history suggestion, use it
        if history_suggestion:
            buffer.text = history_suggestion
            buffer.cursor_position = len(history_suggestion)
        else:
            # If no history suggestion, check for command shadow from fuzzy
            # completer
            shadow = FuzzyCommandCompleter().get_command_shadow(text)
            if shadow and shadow.startswith(text):
                # Complete with the shadow
                buffer.text = shadow
                buffer.cursor_position = len(shadow)
            # If no shadow or shadow is the same as current text
            elif buffer.complete_state:
                # If completion menu is already showing, select the next item
                buffer.complete_next()
            else:
                # Otherwise, start completion
                buffer.start_completion(select_first=True)

    @kb.add('escape', 'enter')
    def handle_escape_enter(event):
        """
        Alternative way to insert a newline using Escape followed by Enter.
        """
        event.current_buffer.insert_text('\n')

    return kb
