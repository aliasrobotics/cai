"""
Memory command for CAI REPL.
This module provides commands for managing memory collections.
"""
from typing import (
    Dict,
    List,
    Optional
)
import os
from wasabi import color  # pylint: disable=import-error
from rich.console import Console  # pylint: disable=import-error
from rich.table import Table  # pylint: disable=import-error
from rich.panel import Panel  # pylint: disable=import-error
from rich.text import Text  # pylint: disable=import-error

from cai.rag.vector_db import QdrantConnector
from cai.repl.commands.base import Command, register_command

console = Console()


class MemoryCommand(Command):
    """Command for managing memory collections."""

    def __init__(self):
        """Initialize the memory command."""
        super().__init__(
            name="/memory",
            description=(
                "Manage memory collections for episodic and semantic"
                "memory"
            ),
            aliases=["/m"]
        )

        # Add subcommands
        self.add_subcommand(
            "list",
            "List all available memory collections",
            self.handle_list)
        self.add_subcommand(
            "load",
            "Load a specific memory collection",
            self.handle_load)
        self.add_subcommand(
            "delete",
            "Delete a specific memory collection",
            self.handle_delete)
        self.add_subcommand(
            "create",
            "Create a new memory collection",
            self.handle_create)

    def handle_list(self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:  # pylint: disable=unused-argument # noqa: E501
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

    def handle_load(self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:  # pylint: disable=unused-argument # noqa: E501
        """Handle /memory load command"""
        if not args:
            console.print("[red]Error: Collection name required[/red]")
            return False

        collection_name = args[0]
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

    def handle_delete(self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:  # pylint: disable=unused-argument # noqa: E501
        """Handle /memory delete command"""
        if not args:
            console.print("[red]Error: Collection name required[/red]")
            return False

        collection_name = args[0]
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

    def handle_create(self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:  # pylint: disable=unused-argument # noqa: E501
        """Handle /memory create command"""
        if not args:
            console.print("[red]Error: Collection name required[/red]")
            return False

        collection_name = args[0]
        distance = "Cosine"
        if len(args) > 1:
            distance = args[1]

        try:
            db = QdrantConnector()
            success = db.create_collection(
                collection_name=collection_name,
                distance=distance)
            if success:
                console.print(
                    f"\nCreated collection: {
                        color(
                            collection_name,
                            fg='green',
                            bold=True)}\n")
                return True
            print(f"Error creating collection: {collection_name}")
            return False
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error creating collection: {e}")
            return False

    def handle_no_args(self, messages: Optional[List[Dict]] = None) -> bool:  # pylint: disable=unused-argument # noqa: E501
        """Handle the command when no arguments are provided."""
        # Show memory help
        self.show_help()
        return True

    def show_help(self) -> None:  # pylint: disable=unused-argument # noqa: E501
        """Show help for memory commands with rich formatting."""
        # Create a styled header
        header = Text("Memory Command Help", style="bold yellow")
        console.print(Panel(header, border_style="yellow"))

        # Usage table
        usage_table = Table(
            title="Usage",
            show_header=True,
            header_style="bold white")
        usage_table.add_column("Command", style="yellow")
        usage_table.add_column("Description", style="white")

        usage_table.add_row(
            "/memory list",
            "Display all available memory collections")
        usage_table.add_row(
            "/memory load <collection>",
            "Set the active memory collection")
        usage_table.add_row(
            "/memory delete <collection>",
            "Delete a memory collection")
        usage_table.add_row(
            "/memory create <collection>",
            "Create a new memory collection")
        usage_table.add_row("/m", "Alias for /memory")

        console.print(usage_table)

        # Examples table
        examples_table = Table(
            title="Examples",
            show_header=True,
            header_style="bold cyan")
        examples_table.add_column("Example", style="cyan")
        examples_table.add_column("Description", style="white")

        examples_table.add_row(
            "/memory list",
            "List all available collections")
        examples_table.add_row(
            "/memory load _all_",
            "Load the semantic memory collection")
        examples_table.add_row(
            "/memory load my_ctf",
            "Load the episodic memory for 'my_ctf'")
        examples_table.add_row(
            "/memory create new_collection",
            "Create a new collection named 'new_collection'")
        examples_table.add_row(
            "/memory delete old_collection",
            "Delete the collection named 'old_collection'")

        console.print(examples_table)

        # Collection types table
        types_table = Table(
            title="Collection Types",
            show_header=True,
            header_style="bold green")
        types_table.add_column("Type", style="green")
        types_table.add_column("Description", style="white")

        types_table.add_row("_all_", "Semantic memory across all CTFs")
        types_table.add_row("<CTF_NAME>", "Episodic memory for a specific CTF")
        types_table.add_row("<custom_name>", "Custom memory collection")

        console.print(types_table)

        # Notes panel
        notes = Panel(
            Text.from_markup(
                "• Memory collections are stored in the Qdrant vector "
                "database\n"
                "• The active collection is stored in the "
                "CAI_MEMORY_COLLECTION environment variable\n"
                "• Episodic memory is used for specific CTFs or "
                "tasks\n"
                "• Semantic memory (_all_) is used across all "
                "CTFs\n"
                "• Memory is used to provide context to the "
                "agent"
            ),
            title="Notes",
            border_style="yellow"
        )
        console.print(notes)


# Register the command
register_command(MemoryCommand())
