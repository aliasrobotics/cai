"""
Model command for CAI REPL.
This module provides commands for viewing and changing the current LLM model.
"""
import os
import datetime
import requests
from typing import List, Optional, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from cai.core import get_ollama_api_base
from cai.repl.commands.base import Command, register_command

console = Console()


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
        self.cached_model_numbers = {}  # Map of numbers to model names
        self.last_model_fetch = datetime.datetime.now() - datetime.timedelta(minutes=10)

    def handle(self, args: Optional[List[str]] = None) -> bool:
        """Handle the model command.

        Args:
            args: Optional list of command arguments

        Returns:
            True if the command was handled successfully, False otherwise
        """
        return self.handle_model_command(args)

    def handle_model_command(self, args: List[str]) -> bool:
        """Change the model used by CAI.

        Args:
            args: List containing the model name to use or a number to select from the list

        Returns:
            bool: True if the model was changed successfully
        """
        # Define model categories and their models for easy reference
        MODEL_CATEGORIES = {
            "Claude 3.7": [
                {"name": "claude-3-7-sonnet-20250219",
                 "description": "Best model for complex reasoning and creative tasks"}
            ],
            "Claude 3.5": [
                {"name": "claude-3-5-sonnet-20240620",
                 "description": "Excellent balance of performance and efficiency"},
                {"name": "claude-3-5-sonnet-20241022",
                 "description": "Latest Claude 3.5 model with improved capabilities"}
            ],
            "Claude 3": [
                {"name": "claude-3-opus-20240229",
                 "description": "Powerful Claude 3 model for complex tasks"},
                {"name": "claude-3-sonnet-20240229",
                 "description": "Balanced performance and speed"},
                {"name": "claude-3-haiku-20240307",
                 "description": "Fast and efficient model"}
            ],
            "OpenAI O-series": [
                {"name": "o1", "description": "Excellent for mathematical reasoning and problem-solving"},
                {"name": "o1-mini",
                 "description": "Smaller O1 model with good math capabilities"},
                {"name": "o3-mini", "description": "Latest mini model in the O-series"},
                {"name": "gpt-4o",
                 "description": "Latest GPT-4 model with improved capabilities"},
                {"name": "gpt-4o-audio-preview",
                 "description": "GPT-4o with audio capabilities"},
                {"name": "gpt-4o-audio-preview-2024-12-17",
                 "description": "Updated GPT-4o with audio capabilities"},
                {"name": "gpt-4o-audio-preview-2024-10-01",
                 "description": "Previous GPT-4o with audio capabilities"}
            ],
            "OpenAI GPT-4": [
                {"name": "gpt-4", "description": "Original GPT-4 model"},
                {"name": "gpt-4-turbo",
                 "description": "Fast and powerful GPT-4 model"}
            ],
            "OpenAI GPT-4.5": [
                {"name": "gpt-4.5-preview",
                 "description": "Latest non reasoning openai model with improved capabilities"},
                {"name": "gpt-4.5-preview-2025-02-27",
                 "description": "Specific version of GPT-4.5 preview"}
            ],
            "OpenAI GPT-3.5": [
                {"name": "gpt-3.5-turbo",
                 "description": "Fast and cost-effective model"}
            ],
            "DeepSeek": [
                {"name": "deepseek-v3",
                 "description": "DeepSeek's latest general-purpose model"},
                {"name": "deepseek-r1",
                 "description": "DeepSeek's specialized reasoning model"}
            ]
        }

        # Fetch model pricing data from LiteLLM GitHub repository
        model_pricing_data = {}
        try:
            response = requests.get(
                "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json",
                timeout=2
            )
            if response.status_code == 200:
                model_pricing_data = response.json()

                # Add DeepSeek models with their pricing if not already in the
                # data
                if "deepseek/deepseek-v3" in model_pricing_data and "deepseek-v3" not in model_pricing_data:
                    model_pricing_data["deepseek-v3"] = model_pricing_data["deepseek/deepseek-v3"]
                if "deepseek/deepseek-r1" in model_pricing_data and "deepseek-r1" not in model_pricing_data:
                    model_pricing_data["deepseek-r1"] = model_pricing_data["deepseek/deepseek-r1"]
        except Exception:  # pylint: disable=broad-except
            console.print(
                "[yellow]Warning: Could not fetch model pricing data[/yellow]")

        # Create a flat list of all models for numeric selection
        ALL_MODELS = []
        for category, models in MODEL_CATEGORIES.items():
            for model in models:
                # Get pricing info if available
                pricing_info = model_pricing_data.get(model["name"], {})
                input_cost = pricing_info.get("input_cost_per_token", None)
                output_cost = pricing_info.get("output_cost_per_token", None)

                # Convert to dollars per million tokens if values exist
                input_cost_per_million = input_cost * 1000000 if input_cost is not None else None
                output_cost_per_million = output_cost * \
                    1000000 if output_cost is not None else None

                ALL_MODELS.append({
                    "name": model["name"],
                    "provider": "Anthropic" if "claude" in model["name"] else
                    "DeepSeek" if "deepseek" in model["name"] else "OpenAI",
                    "category": category,
                    "description": model["description"],
                    "input_cost": input_cost_per_million,
                    "output_cost": output_cost_per_million
                })

        # Update cached models
        self.cached_models = [model["name"] for model in ALL_MODELS]
        self.cached_model_numbers = {
            str(i): model["name"] for i,
            model in enumerate(
                ALL_MODELS,
                1)}

        if not args:
            # Display current model
            model_info = os.getenv("CAI_MODEL", "Unknown")
            console.print(Panel(f"Current model: [bold green]{model_info}[/bold green]",
                                border_style="green", title="Active Model"))

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

            # Add all predefined models with numbers
            for i, model in enumerate(ALL_MODELS, 1):
                # Format pricing info as dollars per million tokens
                input_cost_str = f"${
                    model['input_cost']:.2f}" if model['input_cost'] is not None else "Unknown"
                output_cost_str = f"${
                    model['output_cost']:.2f}" if model['output_cost'] is not None else "Unknown"

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
            try:
                # Get Ollama models with a short timeout to prevent hanging
                api_base = get_ollama_api_base()
                response = requests.get(
                    f"{api_base.replace('/v1', '')}/api/tags", timeout=1)

                if response.status_code == 200:
                    data = response.json()
                    ollama_models = []

                    if 'models' in data:
                        ollama_models = data['models']
                    else:
                        # Fallback for older Ollama versions
                        ollama_models = data.get('items', [])

                    # Add Ollama models to the table with continuing numbers
                    start_index = len(ALL_MODELS) + 1
                    for i, model in enumerate(ollama_models, start_index):
                        model_name = model.get('name', '')
                        model_size = model.get('size', 0)
                        # Convert size to human-readable format
                        size_str = ""
                        if model_size:
                            if model_size < 1024 * 1024 * 1024:
                                size_str = f"{model_size /
                                              (1024 * 1024):.1f} MB"
                            else:
                                size_str = f"{model_size /
                                              (1024 * 1024 * 1024):.1f} GB"

                        # Ollama models are free to use locally
                        model_table.add_row(
                            str(i),
                            model_name,
                            "Ollama",
                            "Local",
                            "Free",
                            "Free",
                            f"Local model{
                                f' ({size_str})' if size_str else ''}"
                        )

                        # Add to cached models for numeric selection
                        self.cached_models.append(model_name)
                        self.cached_model_numbers[str(i)] = model_name
            except Exception:  # pylint: disable=broad-except
                # Add a note about Ollama if we couldn't fetch models
                start_index = len(ALL_MODELS) + 1
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
                "  [bold]/model <model_name>[/bold] - Select by name (e.g. [bold]/model claude-3-7-sonnet-20250219[/bold])")
            console.print(
                "  [bold]/model <number>[/bold]     - Select by number (e.g. [bold]/model 1[/bold] for first model in list)")
            console.print(
                "  [bold]/model-show[/bold]         - Show all available models from LiteLLM repository")
            return True

        model_arg = args[0]

        # Check if the argument is a number for model selection
        if model_arg.isdigit():
            model_index = int(model_arg) - 1  # Convert to 0-based index
            if 0 <= model_index < len(self.cached_models):
                model_name = self.cached_models[model_index]
            else:
                # Si el número está fuera de rango, usamos el número
                # directamente como nombre del modelo
                model_name = model_arg
        else:
            model_name = model_arg

        # Set the model in environment variable
        os.environ["CAI_MODEL"] = model_name

        console.print(Panel(
            f"Model changed to: [bold green]{model_name}[/bold green]\n"
            "[yellow]Note: This will take effect on the next agent interaction[/yellow]",
            border_style="green",
            title="Model Changed"
        ))
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

    def handle(self, args: Optional[List[str]] = None) -> bool:
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
            with console.status("[bold blue]Fetching model data from GitHub...[/bold blue]"):
                response = requests.get(
                    "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json",
                    timeout=5
                )

                if response.status_code != 200:
                    console.print(
                        f"[red]Error fetching model data: HTTP {
                            response.status_code}[/red]")
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
                header_style="bold yellow")
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

                # Skip if showing only supported models and this one doesn't
                # support function calling
                if show_only_supported and not model_info.get(
                        "supports_function_calling", False):
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
                    # Extract provider from model name if in format
                    # provider/model
                    provider = model_name.split("/")[0].capitalize()

                # Get max tokens
                max_tokens = model_info.get("max_tokens", "N/A")

                # Get pricing info
                input_cost = model_info.get("input_cost_per_token", 0)
                output_cost = model_info.get("output_cost_per_token", 0)

                # Convert to dollars per million tokens
                input_cost_per_million = input_cost * 1000000 if input_cost else 0
                output_cost_per_million = output_cost * 1000000 if output_cost else 0

                # Format pricing info
                input_cost_str = f"${
                    input_cost_per_million:.4f}" if input_cost_per_million else "Free"
                output_cost_str = f"${
                    output_cost_per_million:.4f}" if output_cost_per_million else "Free"

                # Get features
                features = []
                if model_info.get("supports_vision"):
                    features.append("Vision")
                if model_info.get("supports_function_calling"):
                    features.append("Function calling")
                if model_info.get("supports_parallel_function_calling"):
                    features.append("Parallel functions")
                if model_info.get("supports_audio_input") or model_info.get(
                        "supports_audio_output"):
                    features.append("Audio")
                if model_info.get("mode") == "embedding":
                    features.append("Embeddings")
                if model_info.get("mode") == "image_generation":
                    features.append("Image generation")

                features_str = ", ".join(
                    features) if features else "Text generation"

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
                # Get Ollama models with a short timeout to prevent hanging
                api_base = get_ollama_api_base()
                ollama_response = requests.get(
                    f"{api_base.replace('/v1', '')}/api/tags", timeout=1)

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
                        if search_term and search_term not in model_name.lower():
                            continue

                        total_models += 1
                        displayed_models += 1

                        model_size = model.get('size', 0)
                        # Convert size to human-readable format
                        size_str = ""
                        if model_size:
                            if model_size < 1024 * 1024 * 1024:
                                size_str = f"{model_size /
                                              (1024 * 1024):.1f} MB"
                            else:
                                size_str = f"{model_size /
                                              (1024 * 1024 * 1024):.1f} GB"

                        # Add row to table
                        model_table.add_row(
                            str(model_index),
                            model_name,
                            "Ollama",
                            "Varies",
                            "Free",
                            "Free",
                            f"Local model{
                                f' ({size_str})' if size_str else ''}"
                        )

                        model_index += 1
            except Exception:  # pylint: disable=broad-except
                pass

            # Display the table
            console.print(model_table)

            # Display summary
            summary_text = f"\n[cyan]Showing {
                displayed_models} of {total_models} models"
            if show_only_supported:
                summary_text += " with function calling support"
            if search_term:
                summary_text += f" matching '{search_term}'"
            summary_text += "[/cyan]"
            console.print(summary_text)

            # Usage instructions
            console.print("\n[cyan]Usage:[/cyan]")
            console.print(
                "  [bold]/model-show[/bold]                - Show all available models")
            console.print(
                "  [bold]/model-show supported[/bold]      - Show only models with function calling")
            console.print(
                "  [bold]/model-show <search>[/bold]       - Filter models by search term")
            console.print(
                "  [bold]/model-show supported <search>[/bold] - Filter supported models by search term")
            console.print(
                "  [bold]/model <model_name>[/bold]        - Select a model to use")
            console.print(
                "  [bold]/model <number>[/bold]            - Select a model by its number")

            # Data source attribution
            console.print(
                "\n[dim]Data source: https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json[/dim]")

        except Exception as e:  # pylint: disable=broad-except
            console.print(f"[red]Error fetching model data: {str(e)}[/red]")

        return True


# Register the commands
register_command(ModelCommand())
register_command(ModelShowCommand())
