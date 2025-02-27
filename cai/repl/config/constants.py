"""
Configuration constants for the CAI REPL.
This module contains configuration constants for the CAI REPL.
"""

# Command descriptions for better help and autocompletion
COMMAND_DESCRIPTIONS = {
    "/memory": "Manage memory collections for episodic and semantic memory",
    "/help": "Display help information about commands and features",
    "/graph": "Visualize the agent interaction graph",
    "/exit": "Exit the CAI REPL",
    "/shell": "Execute shell commands in the current environment",
    "/env": "Display environment variables and their values",
    "/platform": "Interact with platform-specific features",
    "/kill": "Terminate active processes or sessions",
    "/model": "View or change the current LLM model",
    "/turns": "View or change the maximum number of turns"
}

# Subcommand descriptions for better help and autocompletion
SUBCOMMAND_DESCRIPTIONS = {
    "/memory list": "List all available memory collections",
    "/memory load": "Load a specific memory collection",
    "/memory delete": "Delete a specific memory collection",
    "/memory create": "Create a new memory collection",
    "/help memory": "Show help for memory commands",
    "/help agents": "Show help for agent-related features",
    "/help graph": "Show help for graph visualization",
    "/help platform": "Show help for platform-specific features",
    "/help shell": "Show help for shell command execution",
    "/help env": "Show help for environment variables",
    "/help aliases": "Show all command aliases",
    "/help model": "Show help for model selection",
    "/help turns": "Show help for managing turns"
}

# Command aliases for convenience
COMMAND_ALIASES = {
    "/h": "/help",      # Display help information
    "/q": "/exit",      # Exit the application
    "/quit": "/exit",   # Exit the application
    "/k": "/kill",      # Terminate active sessions
    "/e": "/env",       # Show environment variables
    "/g": "/graph",     # Display graph
    "/m": "/memory",    # Access memory
    "/p": "/platform",  # Interact with platform/s
    # shell commands
    "/s": "/shell",     # Execute shell commands
    "$": "/shell",      # Execute shell commands
    # model and turns commands
    "/mod": "/model",   # Change the model
    "/t": "/turns",     # Change max turns
}

# Define available commands and subcommands
COMMANDS = {
    "/memory": [
        "list",
        "load",
        "delete",
        "create"
    ],
    "/help": [
        "memory",
        "agents",
        "graph",
        "platform",
        "shell",
        "env",
        "aliases",
        "model",
        "turns"
    ],
    "/graph": [],
    "/exit": [],
    "/shell": [],
    "/env": [],
    "/platform": [],  # This will be populated dynamically
    "/kill": [],
    "/model": [],
    "/turns": []
}

# Define model categories and their models for easy reference
MODEL_CATEGORIES = {
    "Claude 3.7": [
        {"name": "claude-3-7-sonnet-20250219", "description": "Best model for complex reasoning and creative tasks"}
    ],
    "Claude 3.5": [
        {"name": "claude-3-5-sonnet-20240620", "description": "Excellent balance of performance and efficiency"},
        {"name": "claude-3-5-sonnet-20241022", "description": "Latest Claude 3.5 model with improved capabilities"}
    ],
    "Claude 3": [
        {"name": "claude-3-opus-20240229", "description": "Powerful Claude 3 model for complex tasks"},
        {"name": "claude-3-sonnet-20240229", "description": "Balanced performance and speed"},
        {"name": "claude-3-haiku-20240307", "description": "Fast and efficient model"}
    ],
    "OpenAI O-series": [
        {"name": "o1", "description": "Excellent for mathematical reasoning and problem-solving"},
        {"name": "o1-mini", "description": "Smaller O1 model with good math capabilities"},
        {"name": "o3-mini", "description": "Latest mini model in the O-series"}
    ],
    "OpenAI GPT-4": [
        {"name": "gpt-4o", "description": "Latest GPT-4 model with improved capabilities"},
        {"name": "gpt-4-turbo", "description": "Fast and powerful GPT-4 model"}
    ],
    "OpenAI GPT-4.5": [
        {"name": "gpt-4.5-preview", "description": "Latest non reasoning openai model with improved capabilities"},
    ],
    "OpenAI GPT-3.5": [
        {"name": "gpt-3.5-turbo", "description": "Fast and cost-effective model"}
    ],
    "DeepSeek": [
        {"name": "deepseek-v3", "description": "DeepSeek's latest general-purpose model"},
        {"name": "deepseek-r1", "description": "DeepSeek's specialized reasoning model"}
    ]
}

# Create a flat list of all models for numeric selection
ALL_MODELS = [] 