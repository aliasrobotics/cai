"""
Model command for CAI REPL.
This module provides commands for viewing and changing the current LLM model.
"""
import os
import datetime
# Standard library imports
from typing import List, Optional, Dict, Any 

# Third-party imports
import requests  # pylint: disable=import-error
from rich.console import Console  # pylint: disable=import-error
from rich.table import Table  # pylint: disable=import-error
from rich.panel import Panel  # pylint: disable=import-error
from cai.util import get_ollama_api_base, COST_TRACKER
from cai.repl.commands.base import Command, register_command

console = Console()

LITELLM_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)


def get_predefined_model_categories() -> Dict[str, List[Dict[str, str]]]:
    """Get the predefined model categories as the single source of truth.
    
    This function serves as the authoritative source for all available models
    across the CAI system. Other modules should import and use this function
    to ensure consistency.
    
    Returns:
        Dictionary mapping category names to lists of model dictionaries
    """
    return {
        "Alias": [
            {
                "name": "alias0",
                "description": (
                    "Best model for Cybersecurity AI tasks"
                )
            },
            {
                "name": "alias0-fast",
                "description": (
                    "Fast version of alias0 for quick tasks"
                )
            }
        ],
        "Anthropic Claude": [
            {
                "name": "claude-sonnet-4-20250514",
                "description": (
                    "Excellent balance of performance and efficiency"
                )
            },
            {
                "name": "claude-3-7-sonnet-20250219",
                "description": (
                    "Excellent model for complex reasoning and creative tasks"
                )
            },
            {
                "name": "claude-3-5-sonnet-20240620",
                "description": (
                    "Excellent balance of performance and efficiency"
                )
            },
            {
                "name": "claude-3-5-haiku-20240307",
                "description": (
                    "Fast and efficient model"
                )
            },
        ],
        "OpenAI": [
            {
                "name": "o3-mini",
                "description": "Latest mini model in the O-series"
            },
            {
                "name": "gpt-4o",
                "description": (
                    "Latest GPT-4 model with improved capabilities"
                )
            },
        ],
        "DeepSeek": [
            {
                "name": "deepseek-v3",
                "description": "DeepSeek's latest general-purpose model"
            },
            {
                "name": "deepseek-r1",
                "description": "DeepSeek's specialized reasoning model"
            }
        ]
    }


def get_all_predefined_models() -> List[Dict[str, Any]]:
    """Get all predefined models as a flat list with enriched data.
    
    Returns:
        List of model dictionaries with name, provider, category, description, and pricing
    """
    model_categories = get_predefined_model_categories()
    all_models = []
    
    # Simple mapping from category to provider name
    category_to_provider = {
        "Alias": "OpenAI",  # Alias models use OpenAI as base
        "Anthropic Claude": "Anthropic",
        "OpenAI": "OpenAI", 
        "DeepSeek": "DeepSeek"
    }
    
    for category, models in model_categories.items():
        provider = category_to_provider.get(category, "Unknown")
        
        for model in models:
            # Get pricing info using COST_TRACKER
            input_cost_per_token, output_cost_per_token = COST_TRACKER.get_model_pricing(model["name"])

            # Convert to dollars per million tokens
            input_cost_per_million = None
            output_cost_per_million = None

            if input_cost_per_token is not None and input_cost_per_token > 0:
                input_cost_per_million = input_cost_per_token * 1000000
            if output_cost_per_token is not None and output_cost_per_token > 0:
                output_cost_per_million = output_cost_per_token * 1000000

            all_models.append({
                "name": model["name"],
                "provider": provider,
                "category": category,
                "description": model["description"],
                "input_cost": input_cost_per_million,
                "output_cost": output_cost_per_million
            })
    
    return all_models


def get_predefined_model_names() -> List[str]:
    """Get a simple list of all predefined model names.
    
    This is useful for autocompletion and simple model name lists.
    
    Returns:
        List of model name strings
    """
    return [model["name"] for model in get_all_predefined_models()]


class ModelCommand(Command):
    """Command for viewing and changing the current LLM model."""

    def __init__(self):
        """Initialize the model command."""
        super().__init__(
            name="/model",
            description="View or change the current LLM model",
            aliases=["/mod"]
        )

        # Cache for model information
        self.cached_models = []
        # Map of numbers to model names
        self.cached_model_numbers = {}
        self.last_model_fetch = (
            datetime.datetime.now() - datetime.timedelta(minutes=10)
        )

    def handle(self, args: Optional[List[str]] = None) -> bool:
        """Handle the model command.

        Args:
            args: Optional list of command arguments

        Returns:
            True if the command was handled successfully, False otherwise
        """
        return self.handle_model_command(args)

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    def handle_model_command(self, args: List[str]) -> bool:
        """Change the model used by CAI.

        Args:
            args: List containing the model name to use or a number to select
                from the list

        Returns:
            bool: True if the model was changed successfully
        """
        # Get all predefined models from the shared source of truth
        # pylint: disable=invalid-name
        ALL_MODELS = get_all_predefined_models()

        # Also fetch LiteLLM model names to make numbering consistent with /model-show
        litellm_model_names = []
        try:
            response = requests.get(LITELLM_URL, timeout=5)
            if response.status_code == 200:
                litellm_data = response.json()
                # Add LiteLLM model names (sorted for consistency with /model-show)
                litellm_model_names = sorted(litellm_data.keys())
        except Exception:  # pylint: disable=broad-except
            # Silently fail if LiteLLM is not available
            pass

        # Update cached models to include all models for number selection (consistent with /model-show)
        predefined_model_names = [model["name"] for model in ALL_MODELS]
        self.cached_models = predefined_model_names + litellm_model_names
        self.cached_model_numbers = {
            str(i): model_name
            for i, model_name in enumerate(self.cached_models, 1)
        }

        if not args:  # pylint: disable=too-many-nested-blocks
            # Display current model
            model_info = os.getenv("CAI_MODEL", "Unknown")
            console.print(
                Panel(
                    f"Current model: [bold green]{model_info}[/bold green]",
                    border_style="green",
                    title="Active Model"
                )
            )

            # Show available models in a table
            model_table = Table(
                title="Available Models",
                show_header=True,
                header_style="bold yellow")
            model_table.add_column("#", style="bold white", justify="right")
            model_table.add_column("Model", style="cyan")
            model_table.add_column("Provider", style="magenta")
            model_table.add_column("Category", style="blue")
            model_table.add_column(
                "Input Cost ($/M)",
                style="green",
                justify="right")
            model_table.add_column(
                "Output Cost ($/M)",
                style="red",
                justify="right")
            model_table.add_column("Description", style="white")

            # Add predefined models with numbers
            for i, model in enumerate(ALL_MODELS, 1):
                # Format pricing info as dollars per million tokens
                input_cost_str = (
                    f"${model['input_cost']:.2f}"
                    if model['input_cost'] is not None else "Unknown"
                )
                output_cost_str = (
                    f"${model['output_cost']:.2f}"
                    if model['output_cost'] is not None else "Unknown"
                )

                model_table.add_row(
                    str(i),
                    model["name"],
                    model["provider"],
                    model["category"],
                    input_cost_str,
                    output_cost_str,
                    model["description"]
                )

            # Ollama models (if available)
            # pylint: disable=too-many-nested-blocks
            try:
                # Get Ollama models with a short timeout to prevent hanging
                api_base = get_ollama_api_base()
                ollama_base = api_base.replace('/v1', '')
                response = requests.get(
                    f"{ollama_base}/api/tags",
                    timeout=1
                )

                if response.status_code == 200:
                    data = response.json()
                    ollama_models = []

                    if 'models' in data:
                        ollama_models = data['models']
                    else:
                        # Fallback for older Ollama versions
                        ollama_models = data.get('items', [])

                    # Add Ollama models to the table with continuing numbers
                    # (after predefined models + LiteLLM models in numbering)
                    start_index = len(predefined_model_names) + len(litellm_model_names) + 1
                    for i, model in enumerate(ollama_models, start_index):
                        model_name = model.get('name', '')
                        model_size = model.get('size', 0)
                        # Convert size to human-readable format
                        size_str = ""
                        if model_size:
                            size_mb = model_size / (1024 * 1024)
                            if model_size < 1024 * 1024 * 1024:
                                size_str = f"{size_mb:.1f} MB"
                            else:
                                size_gb = size_mb / 1024
                                size_str = f"{size_gb:.1f} GB"

                        # Ollama models are free to use locally
                        model_description = "Local model"
                        if size_str:
                            model_description += f" ({size_str})"

                        model_table.add_row(
                            str(i),
                            model_name,
                            "Ollama",
                            "Local",
                            "Free",
                            "Free",
                            model_description
                        )
                        # Add to cached models for numeric selection
                        self.cached_models.append(model_name)
                        self.cached_model_numbers[str(i)] = model_name
            except Exception:  # pylint: disable=broad-except
                # Add a note about Ollama if we couldn't fetch models
                start_index = len(predefined_model_names) + len(litellm_model_names) + 1
                model_table.add_row(
                    str(start_index),
                    "llama3",
                    "Ollama",
                    "Local",
                    "Free",
                    "Free",
                    "Local Llama 3 model (if installed)")
                model_table.add_row(str(start_index + 1),
                                    "mistral",
                                    "Ollama",
                                    "Local",
                                    "Free",
                                    "Free",
                                    "Local Mistral model (if installed)")
                model_table.add_row(str(start_index + 2),
                                    "...",
                                    "Ollama",
                                    "Local",
                                    "Free",
                                    "Free",
                                    "Other local models (if installed)")

            console.print(model_table)

            # Usage instructions
            console.print("\n[cyan]Usage:[/cyan]")
            console.print(
                "  [bold]/model <model_name>[/bold] - Select by name (e.g. "
                "[bold]/model claude-3-7-sonnet-20250219[/bold])"
            )
            console.print(
                "  [bold]/model <number>[/bold]     - Select by number (e.g. "
                "[bold]/model 1[/bold] for first model in list)"
            )
            console.print(
                "  [bold]/model-show[/bold]         - Show all available "
                "models from LiteLLM repository"
            )
            return True

        model_arg = args[0]

        # Check if the argument is a number for model selection
        if model_arg.isdigit():
            model_index = int(model_arg) - 1  # Convert to 0-based index
            if 0 <= model_index < len(self.cached_models):
                model_name = self.cached_models[model_index]
            else:
                # If the number is out of range, we use the number
                # directly as the model name
                model_name = model_arg
        else:
            model_name = model_arg

        # Set the model in environment variable
        os.environ["CAI_MODEL"] = model_name

        # Display model change notification
        change_message = (
            f"Model changed to: [bold green]{model_name}[/bold green]\n"
            "[yellow]Note: This will take effect on the next agent "
            "interaction[/yellow]"
        )
        console.print(
            Panel(
                change_message,
                border_style="green",
                title="Model Changed"
            ), end=""
        )
        return True


class ModelShowCommand(Command):
    """Command for showing all available models from LiteLLM repository."""

    def __init__(self):
        """Initialize the model-show command."""
        super().__init__(
            name="/model-show",
            description="Show all available models from LiteLLM repository",
            aliases=["/mod-show"]
        )

    def handle(self, args: Optional[List[str]] = None) -> bool:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements,line-too-long # noqa: E501
        """Handle the model-show command.

        Args:
            args: Optional list of command arguments

        Returns:
            True if the command was handled successfully, False otherwise
        """
        # Check if we should only show supported models
        show_only_supported = False
        search_term = None

        if args:
            if "supported" in args:
                show_only_supported = True
                # Remove 'supported' from args to handle search term
                args = [arg for arg in args if arg != "supported"]

            if args:  # If there are still args left, use as search term
                search_term = args[0].lower()

        # Fetch model pricing data from LiteLLM GitHub repository
        try:
            with console.status(
                "[bold blue]Fetching model data...[/bold blue]"
            ):
                response = requests.get(LITELLM_URL, timeout=5)

                if response.status_code != 200:
                    error_msg = (
                        f"[red]Error fetching model data: "
                        f"HTTP {response.status_code}[/red]"
                    )
                    console.print(error_msg)
                    return True

                model_data = response.json()

            # Create a table to display the models
            title = "All Available Models"
            if show_only_supported:
                title = "Supported Models (with Function Calling)"
            if search_term:
                title += f" - Search: '{search_term}'"

            model_table = Table(
                title=title,
                show_header=True,
                header_style="bold yellow"
            )
            model_table.add_column("#", style="bold white", justify="right")
            model_table.add_column("Model", style="cyan")
            model_table.add_column("Provider", style="magenta")
            model_table.add_column("Max Tokens", style="blue", justify="right")
            model_table.add_column(
                "Input Cost ($/M)",
                style="green",
                justify="right")
            model_table.add_column(
                "Output Cost ($/M)",
                style="red",
                justify="right")
            model_table.add_column("Features", style="white")

            # Count models for summary
            total_models = 0
            displayed_models = 0
            model_index = 1

            # Process and display models
            for model_name, model_info in sorted(model_data.items()):
                total_models += 1

                # Skip if showing only supported models and no function calling
                supports_functions = model_info.get(
                    "supports_function_calling",
                    False
                )
                if show_only_supported and not supports_functions:
                    continue

                # Skip if search term provided and not in model name
                if search_term and search_term not in model_name.lower():
                    continue

                displayed_models += 1

                # Extract provider from litellm_provider if available
                provider = model_info.get("litellm_provider", "Unknown")
                if provider == "text-completion-openai":
                    provider = "OpenAI"
                elif provider == "openai":
                    provider = "OpenAI"
                elif "/" in model_name:
                    # Extract provider from model name
                    provider = model_name.split("/")[0].capitalize()

                # Get max tokens
                max_tokens = model_info.get("max_tokens", "N/A")

                # Get pricing info
                input_cost = model_info.get("input_cost_per_token", 0)
                output_cost = model_info.get("output_cost_per_token", 0)

                # Convert to dollars per million tokens
                input_cost_per_million = (
                    input_cost * 1000000 if input_cost else 0
                )
                output_cost_per_million = (
                    output_cost * 1000000 if output_cost else 0
                )

                # Format pricing info
                if input_cost_per_million:
                    input_cost_str = f"${input_cost_per_million:.4f}"
                else:
                    input_cost_str = "Free"

                if output_cost_per_million:
                    output_cost_str = f"${output_cost_per_million:.4f}"
                else:
                    output_cost_str = "Free"

                # Get features
                features = []
                if model_info.get("supports_vision"):
                    features.append("Vision")
                if model_info.get("supports_function_calling"):
                    features.append("Function calling")
                if model_info.get("supports_parallel_function_calling"):
                    features.append("Parallel functions")
                if (model_info.get("supports_audio_input") or
                        model_info.get("supports_audio_output")):
                    features.append("Audio")
                if model_info.get("mode") == "embedding":
                    features.append("Embeddings")
                if model_info.get("mode") == "image_generation":
                    features.append("Image generation")

                features_str = (
                    ", ".join(features) if features else "Text generation"
                )

                # Add row to table
                model_table.add_row(
                    str(model_index),
                    model_name,
                    provider,
                    str(max_tokens),
                    input_cost_str,
                    output_cost_str,
                    features_str
                )

                model_index += 1

            # Now add Ollama models if available
            try:
                # Get Ollama models with a short timeout
                api_base = get_ollama_api_base()
                api_tags = f"{api_base.replace('/v1', '')}/api/tags"
                ollama_response = requests.get(api_tags, timeout=1)

                if ollama_response.status_code == 200:
                    ollama_data = ollama_response.json()
                    ollama_models = []

                    if 'models' in ollama_data:
                        ollama_models = ollama_data['models']
                    else:
                        # Fallback for older Ollama versions
                        ollama_models = ollama_data.get('items', [])

                    # Add Ollama models to the table
                    for model in ollama_models:
                        model_name = model.get('name', '')

                        # Skip if search term provided and not in model name
                        if (search_term and
                                search_term not in model_name.lower()):
                            continue

                        total_models += 1
                        displayed_models += 1

                        model_size = model.get('size', 0)
                        # Convert size to human-readable format
                        size_str = ""
                        if model_size:
                            size_mb = model_size / (1024 * 1024)
                            if model_size < 1024 * 1024 * 1024:
                                size_str = f"{size_mb:.1f} MB"
                            else:
                                size_gb = size_mb / 1024
                                size_str = f"{size_gb:.1f} GB"

                        # Add row to table
                        model_description = "Local model"
                        if size_str:
                            model_description += f" ({size_str})"

                        model_table.add_row(
                            str(model_index),
                            model_name,
                            "Ollama",
                            "Varies",
                            "Free",
                            "Free",
                            model_description
                        )

                        model_index += 1
            except Exception:  # pylint: disable=broad-except
                # Silently fail if Ollama is not available
                # This is acceptable as Ollama is optional and we don't want to
                # disrupt the user experience if it's not running
                console.print(
                    "[dim]Ollama models not available[/dim]",
                    style="dim")

            # Display the table
            console.print(model_table)

            # Display summary
            displayed_str = str(displayed_models)
            total_str = str(total_models)
            summary_text = (
                f"\n[cyan]Showing {displayed_str} of {total_str} models"
            )
            if show_only_supported:
                summary_text += " with function calling support"
            if search_term:
                summary_text += f" matching '{search_term}'"
            summary_text += "[/cyan]"
            console.print(summary_text)

            # Usage instructions
            console.print("\n[cyan]Usage:[/cyan]")
            console.print(
                "  [bold]/model-show[/bold]                - Show all "
                "available models")
            console.print(
                "  [bold]/model-show supported[/bold]      - Show only "
                "models with function calling")
            console.print(
                "  [bold]/model-show <search>[/bold]       - Filter "
                "models by search term")
            console.print(
                "  [bold]/model-show supported <search>[/bold] - Filter "
                "supported models by search term")
            console.print(
                "  [bold]/model <model_name>[/bold]        - Select a "
                "model to use")
            console.print(
                "  [bold]/model <number>[/bold]            - Select a "
                "model by its number")

            # Data source attribution
            data_source = (
                "https://github.com/BerriAI/litellm/blob/main/"
                "model_prices_and_context_window.json"
            )
            console.print(f"\n[dim]Data source: {data_source}[/dim]")

        except Exception as e:  # pylint: disable=broad-except
            console.print(f"[red]Error fetching model data: {str(e)}[/red]")

        return True


# Register the commands
register_command(ModelCommand())
register_command(ModelShowCommand())
