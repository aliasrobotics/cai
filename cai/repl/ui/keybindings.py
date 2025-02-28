"""
Module for CAI REPL key bindings.
"""
import os
import subprocess  # nosec B404 - Required for screen clearing
# pylint: disable=import-error
from prompt_toolkit.key_binding import KeyBindings


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
            # nosec B603 B607
            subprocess.run(['cls'], shell=False, check=False)
        else:
            # Using fixed commands with shell=False is safe
            # nosec B603 B607
            subprocess.run(['clear'], shell=False, check=False)

    @kb.add('tab')
    def handle_tab(event):
        """Handle tab key to show completions menu."""
        # Complete the buffer
        event.current_buffer.complete_state = None
        event.current_buffer.start_completion(select_first=False)

    @kb.add('right')
    def handle_right_arrow(event):
        """Handle right arrow key to complete command shadow."""
        buffer = event.current_buffer
        text = buffer.text

        # Update current text for shadow
        current_text[0] = text

        # Check if we have a command shadow
        # pylint: disable=import-outside-toplevel
        from cai.repl.commands import FuzzyCommandCompleter
        shadow = FuzzyCommandCompleter().get_command_shadow(text)
        if shadow and shadow.startswith(text):
            # Complete with the shadow
            buffer.text = shadow
            buffer.cursor_position = len(shadow)

    return kb
