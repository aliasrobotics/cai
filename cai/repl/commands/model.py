"""
Model command for CAI REPL.
This module provides commands for viewing and changing the current LLM model.
"""
import os
import datetime
# Standard library imports
from typing import Dict, List, Optional  # Dict and Any removed as unused

# Third-party imports
import requests  # pylint: disable=import-error
from rich.console import Console  # pylint: disable=import-error
from rich.table import Table  # pylint: disable=import-error
from rich.panel import Panel  # pylint: disable=import-error
from cai.core import get_ollama_api_base
from cai.repl.commands.base import Command, register_command

console = Console()

LITELLM_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)


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

    def handle(self, args: Optional[List[str]] = None,
               messages: Optional[List[Dict]] = None) -> bool:
        """Handle the model command.

        Args:
            args: Optional list of command arguments
            messages: Optional list of conversation messages

        Returns:
            True if the command was handled successfully, False otherwise
        """
        return self.handle_model_command(args)

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    def handle_model_command(
            self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:  # noqa: E501
        """Change the model used by CAI.

        Args:
            args: List containing the model name to use or a number to select
                from the list
            messages: Optional list of conversation messages

        Returns:
            bool: True if the model was changed successfully
        """
        # Define model categories and their models for easy reference
        # pylint: disable=invalid-name
        MODEL_CATEGORIES = {
            "Google Gemini 2.X": [
                {
                    "name": "gemini/gemini-2.5-pro-exp-03-25",
                    "description": (
                        """Advanced model with enhanced reasoning,
                         SOTA comparable to Claude 3.7"""
                    )
                },
                {
                    "name": "gemini/gemini-2.0-pro-exp-02-05",
                    "description": (
                        "Current SOTA model from Google, comparable to Claude"
                        " 3.7"
                    )
                },
                {
                    "name": "gemini/gemini-2.0-flash",
                    "description": "Fast and capable Gemini 2.0 model"
                },
                {
                    "name": "gemini/gemini-2.0-flash-lite",
                    "description": "Lighter version of Gemini 2.0 Flash"
                },
                {
                    "name": "gemini/gemini-2.0-flash-001",
                    "description": "Specific version of Gemini 2.0 Flash"
                },
                {
                    "name": "gemini/gemini-2.0-flash-exp",
                    "description": "Experimental version of Gemini 2.0 Flash"
                },
                {
                    "name": "gemini/gemini-2.0-flash-lite-preview-02-05",
                    "description": "Preview version of Gemini 2.0 Flash Lite"
                },
                {
                    "name": "gemini/gemini-2.0-flash-thinking-exp",
                    "description": (
                        "Experimental Gemini 2.0 Flash with thinking "
                        "capabilities"
                    )
                },
                {
                    "name": "gemini/gemini-2.0-flash-thinking-exp-01-21",
                    "description": (
                        "Specific experimental version of Gemini 2.0 Flash "
                        "with thinking"
                    )
                }
            ],
            "Claude 3.7": [
                {
                    "name": "claude-3-7-sonnet-20250219",
                    "description": (
                        "Best model for complex reasoning and creative tasks"
                    )
                }
            ],
            "Claude 3.5": [
                {
                    "name": "claude-3-5-sonnet-20240620",
                    "description": (
                        "Excellent balance of performance and efficiency"
                    )
                },
                {
                    "name": "claude-3-5-sonnet-20241022",
                    "description": (
                        "Latest Claude 3.5 model with improved capabilities"
                    )
                }
            ],
            "Claude 3": [
                {
                    "name": "claude-3-opus-20240229",
                    "description": "Powerful Claude 3 model for complex tasks"
                },
                {
                    "name": "claude-3-sonnet-20240229",
                    "description": "Balanced performance and speed"
                },
                {
                    "name": "claude-3-haiku-20240307",
                    "description": "Fast and efficient model"
                }
            ],
            "OpenAI O-series": [
                {
                    "name": "o1",
                    "description": (
                        "Excellent for mathematical reasoning and "
                        "problem-solving"
                    )
                },
                {
                    "name": "o1-mini",
                    "description": (
                        "Smaller O1 model with good math capabilities"
                    )
                },
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
                {
                    "name": "gpt-4o-audio-preview",
                    "description": "GPT-4o with audio capabilities"
                },
                {
                    "name": "gpt-4o-audio-preview-2024-12-17",
                    "description": "Updated GPT-4o with audio capabilities"
                },
                {
                    "name": "gpt-4o-audio-preview-2024-10-01",
                    "description": "Previous GPT-4o with audio capabilities"
                }
            ],
            "OpenAI GPT-4": [
                {"name": "gpt-4", "description": "Original GPT-4 model"},
                {"name": "gpt-4-turbo",
                 "description": "Fast and powerful GPT-4 model"}
            ],
            "OpenAI GPT-4.5": [
                {
                    "name": "gpt-4.5-preview",
                    "description": (
                        "Latest non reasoning openai model with "
                        "improved capabilities"
                    )
                },
                {
                    "name": "gpt-4.5-preview-2025-02-27",
                    "description": "Specific version of GPT-4.5 preview"
                }
            ],
            "OpenAI GPT-3.5": [
                {
                    "name": "gpt-3.5-turbo",
                    "description": "Fast and cost-effective model"
                }
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

        # Fetch model pricing data from LiteLLM GitHub repository
        model_pricing_data = {}
        try:
            response = requests.get(LITELLM_URL, timeout=2)
            if response.status_code == 200:
                model_pricing_data = response.json()

                # Add DeepSeek models with their pricing if not in data
                deepseek_v3_path = "deepseek/deepseek-v3"
                deepseek_r1_path = "deepseek/deepseek-r1"

                if (deepseek_v3_path in model_pricing_data and
                        "deepseek-v3" not in model_pricing_data):
                    model_pricing_data["deepseek-v3"] = (
                        model_pricing_data[deepseek_v3_path]
                    )
                if (deepseek_r1_path in model_pricing_data and
                        "deepseek-r1" not in model_pricing_data):
                    model_pricing_data["deepseek-r1"] = (
                        model_pricing_data[deepseek_r1_path]
                    )
        except Exception:  # pylint: disable=broad-except
            console.print(
                "[yellow]Warning: Could not fetch model pricing data[/yellow]"
            )

        # Create a flat list of all models for numeric selection
        # pylint: disable=invalid-name
        ALL_MODELS = []
        for category, models in MODEL_CATEGORIES.items():
            for model in models:
                # Get pricing info if available
                pricing_info = model_pricing_data.get(model["name"], {})
                input_cost = pricing_info.get("input_cost_per_token", None)
                output_cost = pricing_info.get("output_cost_per_token", None)

                # Convert to dollars per million tokens if values exist
                input_cost_per_million = None
                output_cost_per_million = None

                if input_cost is not None:
                    input_cost_per_million = input_cost * 1000000
                if output_cost is not None:
                    output_cost_per_million = output_cost * 1000000

                # Determine provider
                provider = "Unknown"
                if "claude" in model["name"]:
                    provider = "Anthropic"
                elif "deepseek" in model["name"]:
                    provider = "DeepSeek"
                elif "gemini" in model["name"]:
                    provider = "Google"
                elif "gpt" in model["name"] or "o1" in model["name"] or "o3" in model["name"]:  # noqa: E501
                    provider = "OpenAI"

                ALL_MODELS.append({
                    "name": model["name"],
                    "provider": provider,
                    "category": category,
                    "description": model["description"],
                    "input_cost": input_cost_per_million,
                    "output_cost": output_cost_per_million
                })

        # Update cached models
        self.cached_models = [model["name"] for model in ALL_MODELS]
        self.cached_model_numbers = {
            str(i): model["name"]
            for i, model in enumerate(ALL_MODELS, 1)
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
            model_table.add_column("API Key Env Var", style="dim")
            model_table.add_column("Description", style="white")

            # Add all predefined models with numbers
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

                # Determine API Key Env Var
                api_key_var = "N/A"
                provider_lower = model["provider"].lower()
                if provider_lower == "google":
                    api_key_var = "GEMINI_API_KEY"
                elif provider_lower == "anthropic":
                    api_key_var = "ANTHROPIC_API_KEY"
                elif provider_lower == "openai":
                    api_key_var = "OPENAI_API_KEY"
                elif provider_lower == "deepseek":
                    api_key_var = "DEEPSEEK_API_KEY"

                model_table.add_row(
                    str(i),
                    model["name"],
                    model["provider"],
                    model["category"],
                    input_cost_str,
                    output_cost_str,
                    api_key_var,
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
                    start_index = len(ALL_MODELS) + 1
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
                            "OLLAMA_API_BASE",
                            model_description
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
                    "OLLAMA_API_BASE",
                    "Local Llama 3 model (if installed)")
                model_table.add_row(str(start_index + 1),
                                    "mistral",
                                    "Ollama",
                                    "Local",
                                    "Free",
                                    "Free",
                                    "OLLAMA_API_BASE",
                                    "Local Mistral model (if installed)")
                model_table.add_row(str(start_index + 2),
                                    "...",
                                    "Ollama",
                                    "Local",
                                    "Free",
                                    "Free",
                                    "OLLAMA_API_BASE",
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
            )
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

    def handle(self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements,line-too-long # noqa: E501
        """Handle the model-show command.

        Args:
            args: Optional list of command arguments
            messages: Optional list of conversation messages

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
            model_table.add_column("API Key Env Var", style="dim")
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
                elif provider == "anthropic":
                    provider = "Anthropic"
                elif provider == "bedrock":  # Bedrock often proxies Anthropic/others # noqa: E501
                    # Try to guess based on name for Bedrock
                    if "claude" in model_name.lower():
                        provider = "Anthropic (Bedrock)"
                    # Add other Bedrock providers if needed
                    else:
                        provider = "AWS Bedrock"
                elif "gemini" in model_name.lower():
                    provider = "Google"
                elif "deepseek" in model_name.lower():
                    provider = "DeepSeek"
                elif "groq" in model_name.lower():
                    provider = "Groq"
                elif "azure" in model_name.lower():
                    provider = "Azure OpenAI"
                elif "perplexity" in model_name.lower():
                    provider = "Perplexity"
                elif "cohere" in model_name.lower():
                    provider = "Cohere"
                elif "together_ai" in model_name.lower():
                    provider = "Together AI"
                elif "huggingface" in model_name.lower():
                    provider = "HuggingFace"
                elif "mistral" in model_name.lower():
                    provider = "Mistral AI"
                elif "databricks" in model_name.lower():
                    provider = "Databricks"
                elif "cloudflare" in model_name.lower():
                    provider = "Cloudflare"
                elif "voyage" in model_name.lower():
                    provider = "Voyage AI"
                elif "replicate" in model_name.lower():
                    provider = "Replicate"
                elif "anyscale" in model_name.lower():
                    provider = "Anyscale"
                elif "vertex" in model_name.lower():
                    provider = "Google Vertex AI"
                elif "nvidia" in model_name.lower():
                    provider = "NVIDIA"
                elif "ai21" in model_name.lower():
                    provider = "AI21"
                elif "nlp_cloud" in model_name.lower():
                    provider = "NLP Cloud"
                elif "aleph_alpha" in model_name.lower():
                    provider = "Aleph Alpha"
                elif "baseten" in model_name.lower():
                    provider = "Baseten"
                elif "petals" in model_name.lower():
                    provider = "Petals"
                elif "marqo" in model_name.lower():
                    provider = "Marqo"
                elif "openrouter" in model_name.lower():
                    provider = "OpenRouter"
                elif "cloudflare" in model_name.lower():
                    provider = "Cloudflare"
                elif "palm" in model_name.lower():  # Older Google
                    provider = "Google PaLM"
                elif "ollama" in model_name.lower():
                    provider = "Ollama"
                elif "databricks" in model_name.lower():
                    provider = "Databricks"
                elif "maritaca" in model_name.lower():
                    provider = "Maritaca"
                elif "clarifai" in model_name.lower():
                    provider = "Clarifai"
                elif "fireworks_ai" in model_name.lower():
                    provider = "Fireworks AI"
                elif provider == "Unknown" and "/" in model_name:
                    # Fallback: Extract provider from model name if structure
                    # is provider/model
                    provider_guess = model_name.split("/")[0].capitalize()
                    if provider_guess:
                        provider = provider_guess

                # Determine API Key Var
                api_key_var = "N/A"
                provider_lower = provider.lower()
                if "google" in provider_lower or "vertex" in provider_lower or "palm" in provider_lower:  # noqa: E501
                    api_key_var = "GOOGLE_API_KEY"
                elif "anthropic" in provider_lower or ("bedrock" in provider_lower and "claude" in model_name.lower()):  # noqa: E501
                    api_key_var = "ANTHROPIC_API_KEY"
                elif "openai" in provider_lower or "azure" in provider_lower:
                    api_key_var = "OPENAI_API_KEY"
                elif "deepseek" in provider_lower:
                    api_key_var = "DEEPSEEK_API_KEY"
                elif "cohere" in provider_lower:
                    api_key_var = "COHERE_API_KEY"
                elif "groq" in provider_lower:
                    api_key_var = "GROQ_API_KEY"
                elif "together_ai" in provider_lower:
                    api_key_var = "TOGETHER_API_KEY"
                elif "perplexity" in provider_lower:
                    api_key_var = "PERPLEXITY_API_KEY"
                elif "mistral" in provider_lower:
                    api_key_var = "MISTRAL_API_KEY"
                elif "huggingface" in provider_lower:
                    api_key_var = "HUGGINGFACE_API_KEY"
                elif "ai21" in provider_lower:
                    api_key_var = "AI21_API_KEY"
                elif "replicate" in provider_lower:
                    api_key_var = "REPLICATE_API_KEY"
                elif "voyage" in provider_lower:
                    api_key_var = "VOYAGE_API_KEY"
                elif "bedrock" in provider_lower:  # Catch-all for other Bedrock # noqa: E501
                    api_key_var = "AWS Keys (Configured)"
                elif "ollama" in provider_lower:
                    api_key_var = "OLLAMA_API_BASE"
                elif provider != "Unknown" and provider != "Ollama":  # Many other providers exist # noqa: E501
                    api_key_var = f"{
                        provider.upper().replace(
                            ' ', '_')}_API_KEY"

                # Get max tokens
                max_tokens = model_info.get("max_input_tokens", "N/A")

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
                    api_key_var,
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

                        # Skip if showing only supported models (Ollama doesn't
                        # report this)
                        if show_only_supported:
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
                            "OLLAMA_API_BASE",
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
