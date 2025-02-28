"""
Platform command for CAI REPL.
This module provides commands for interacting with platform-specific features.
"""
from typing import (
    List,
    Optional
)
from rich.console import Console  # pylint: disable=import-error
from rich.panel import Panel  # pylint: disable=import-error

from cai import is_caiextensions_platform_available
from cai.repl.commands.base import Command, register_command

console = Console()


class PlatformCommand(Command):
    """Command for interacting with platform-specific features."""

    def __init__(self):
        """Initialize the platform command."""
        super().__init__(
            name="/platform",
            description="Interact with platform-specific features",
            aliases=["/p"]
        )

        # Add subcommands dynamically based on available platforms
        if is_caiextensions_platform_available():
            from caiextensions.platform.base import platform_manager  # pylint: disable=import-error,import-outside-toplevel,unused-import,line-too-long,no-name-in-module # noqa: E501

            # Add list subcommand
            self.add_subcommand(
                "list",
                "List available platforms",
                self.handle_list)

            # Add platform-specific subcommands
            platforms = platform_manager.list_platforms()
            for platform in platforms:
                platform_cmds = platform_manager.get_platform(
                    platform).get_commands()
                for cmd in platform_cmds:
                    # Add platform-specific commands as subcommands
                    self.add_subcommand(
                        f"{platform}:{cmd}",
                        f"Execute {cmd} command on {platform} platform",
                        lambda args, p=platform, c=cmd:
                            self.handle_platform_command([p, c] + (args or []))
                    )

    def handle(self, args: Optional[List[str]] = None) -> bool:
        """Handle the platform command.

        Args:
            args: Optional list of command arguments

        Returns:
            True if the command was handled successfully, False otherwise
        """
        if not is_caiextensions_platform_available():
            console.print("[red]Platform extensions are not available[/red]")
            return False

        return self.handle_platform_command(args)

    def handle_list(self, args: Optional[List[str]] = None) -> bool:  # pylint: disable=unused-argument # noqa: E501
        """Handle /platform list command."""
        if not is_caiextensions_platform_available():
            console.print("[red]Platform extensions are not available[/red]")
            return False

        from caiextensions.platform.base import platform_manager  # pylint: disable=import-error,import-outside-toplevel,unused-import,line-too-long,no-name-in-module # noqa: E501
        platforms = platform_manager.list_platforms()

        console.print(Panel(
            "\n".join(f"[green]{p}[/green]" for p in platforms),
            title="Available Platforms",
            border_style="blue"
        ))
        return True

    def handle_platform_command(
            self, args: Optional[List[str]] = None) -> bool:
        """Handle platform specific commands."""
        if not is_caiextensions_platform_available():
            console.print("[red]Platform extensions are not available[/red]")
            return False

        from caiextensions.platform.base import platform_manager  # pylint: disable=import-error,import-outside-toplevel,unused-import,line-too-long,no-name-in-module # noqa: E501

        if not args:
            # Show available platforms
            platforms = platform_manager.list_platforms()
            console.print(Panel(
                "\n".join(f"[green]{p}[/green]" for p in platforms),
                title="Available Platforms",
                border_style="blue"
            ))
            return True

        platform_name = args[0].lower()
        platform = platform_manager.get_platform(platform_name)

        if not platform:
            console.print(f"[red]Unknown platform: {platform_name}[/red]")
            return False

        if len(args) == 1:
            # Show platform help
            console.print(Panel(
                platform.get_help(),
                title=f"{platform_name.upper()} Help",
                border_style="blue"
            ))
            return True

        # Pass the command to the platform (without the platform name)
        platform.handle_command(args[1:])
        return True


# Register the command
if is_caiextensions_platform_available():
    register_command(PlatformCommand())
