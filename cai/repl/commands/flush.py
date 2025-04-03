"""
Flush command for CAI REPL.
This module provides commands for clear the context.
"""
import os
from typing import (
    Dict,
    List,
    Optional
)
from rich.console import Console  # pylint: disable=import-error
from rich.panel import Panel  # pylint: disable=import-error
from cai.util import get_model_input_tokens
from cai.repl.commands.base import Command, register_command
console = Console()


class FlushCommand(Command):
    """Command to flush the conversation history."""

    def __init__(self):
        """Initialize the flush command."""
        super().__init__(
            name="/flush",
            description="Clear the current conversation history.",
            aliases=["/clear"]
        )

    def handle_no_args(self, messages: Optional[List[Dict]] = None) -> bool:
        """Handle the flush command when no args are provided.

        Args:
            messages: The conversation history messages

        Returns:
            True if the command was handled successfully
        """
        if messages:
            initial_length = len(messages)

            # Get token usage information before clearing
            token_info = ""
            context_usage = ""

            # Access client through a function to avoid circular imports
            # We can use globals() to get the client at runtime
            client = self._get_client()

            if client and hasattr(client, 'interaction_input_tokens') and hasattr(  # noqa: E501
                    client, 'total_input_tokens'):
                model = os.getenv('CAI_MODEL', "qwen2.5:14b")
                input_tokens = client.interaction_input_tokens if hasattr(
                    client, 'interaction_input_tokens') else 0
                total_tokens = client.total_input_tokens if hasattr(
                    client, 'total_input_tokens') else 0
                max_tokens = get_model_input_tokens(model)
                context_pct = (input_tokens / max_tokens) * \
                    100 if max_tokens > 0 else 0

                token_info = f"Current tokens: {
                    input_tokens}, Total tokens: {total_tokens}"
                context_usage = f"Context usage: {
                    context_pct:.1f}% of {max_tokens} tokens"

            # Clear the messages
            messages.clear()

            # Display information about the cleared messages
            content = [
                f"Conversation history cleared. Removed {
                    initial_length} messages."
            ]

            if token_info:
                content.append(token_info)
            if context_usage:
                content.append(context_usage)

            console.print(Panel(
                "\n".join(content),
                title="[bold cyan]Context Flushed[/bold cyan]",
                border_style="blue",
                padding=(1, 2)
            ))
        else:
            console.print(Panel(
                "No conversation history to clear.",
                title="[bold cyan]Context Flushed[/bold cyan]",
                border_style="blue",
                padding=(1, 2)
            ))
        return True

    def _get_client(self):
        """Get the CAI client from the global namespace.

        This function avoids circular imports by accessing the client
        at runtime instead of import time.

        Returns:
            The global CAI client instance or None if not available
        """
        try:
            # Import here to avoid circular import
            from cai.repl.repl import client as global_client # pylint: disable=import-outside-toplevel # noqa: E501
            return global_client
        except (ImportError, AttributeError):
            return None


# Register the /flush command
register_command(FlushCommand())
