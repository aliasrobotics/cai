"""
Module for CAI REPL key bindings.
"""
import os
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
    def clear_screen(event):
        """Clear the screen."""
        os.system('cls' if os.name == 'nt' else 'clear')

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
        from cai.repl.commands import FuzzyCommandCompleter
        shadow = FuzzyCommandCompleter().get_command_shadow(text)
        if shadow and shadow.startswith(text):
            # Complete with the shadow
            buffer.text = shadow
            buffer.cursor_position = len(shadow)

    return kb
