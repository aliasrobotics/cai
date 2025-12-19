"""
Command completer for CAI REPL.
This module provides a fuzzy command completer with autocompletion menu and
command shadowing.
"""
# Standard library imports
import datetime
import threading
import time
from functools import lru_cache
from typing import (
    List,
    Optional,
    Dict,
    Any
)

# Third-party imports
import requests  # pylint: disable=import-error,unused-import,line-too-long # noqa: E501
from prompt_toolkit.completion import (  # pylint: disable=import-error
    Completer,
    Completion
)
from prompt_toolkit.formatted_text import HTML  # pylint: disable=import-error
from prompt_toolkit.styles import Style  # pylint: disable=import-error
from rich.console import Console  # pylint: disable=import-error

from cai.util import get_ollama_api_base
from cai.repl.commands.base import (
    COMMANDS,
    COMMAND_ALIASES
)
from cai.repl.commands.model import get_predefined_model_names

console = Console()

# Global cache for command descriptions and subcommands
COMMAND_DESCRIPTIONS_CACHE = None
SUBCOMMAND_DESCRIPTIONS_CACHE = None
ALL_COMMANDS_CACHE = None


class FuzzyCommandCompleter(Completer):
    """Command completer with fuzzy matching for the REPL.

    This advanced completer provides intelligent suggestions for commands,
    subcommands, and arguments based on what the user is typing.
    It supports fuzzy matching to find commands even with typos.

    Features:
    - Fuzzy matching for commands and subcommands
    - Autocompletion menu with descriptions
    - Command shadowing (showing hints for previously used commands)
    - Model completion for the /model command
    - Agent completion for the /agent command
    """

    # Class-level cache for models
    _cached_models = []
    _cached_model_numbers = {}
    _last_model_fetch = datetime.datetime.now() - datetime.timedelta(minutes=10)
    _fetch_lock = threading.Lock()

    # Class-level cache for agents (with proper threading and time-based caching)
    _cached_agents = []
    _cached_agent_numbers = {}
    _last_agent_fetch = datetime.datetime.now() - datetime.timedelta(minutes=10)
    _agent_fetch_lock = threading.Lock()
    
    def __init__(self):
        """Initialize the command completer with cached model and agent information."""
        super().__init__()
        self.command_history = {}  # Store command usage frequency
        
        # Fetch models in background thread to avoid blocking
        threading.Thread(
            target=self._background_fetch_models,
            daemon=True
        ).start()

        # Fetch agents in background thread to avoid blocking
        threading.Thread(
            target=self._background_fetch_agents,
            daemon=True
        ).start()

        # Styling for the completion menu
        self.completion_style = Style.from_dict({
            'completion-menu': 'bg:#2b2b2b #ffffff',
            'completion-menu.completion': 'bg:#2b2b2b #ffffff',
            'completion-menu.completion.current': 'bg:#004b6b #ffffff',
            'scrollbar.background': 'bg:#2b2b2b',
            'scrollbar.button': 'bg:#004b6b',
        })
    
    def _background_fetch_agents(self):
        """Fetch agents in background to avoid blocking the UI."""
        try:
            self.fetch_all_agents()
        except Exception:  # pylint: disable=broad-except
            # Silently fail if agent fetching is not available
            pass

    def fetch_all_agents(self):
        """Fetch all available agents to match /agent command."""
        # Only fetch every 60 seconds to avoid excessive calls
        now = datetime.datetime.now()
        
        # Use a lock to prevent multiple threads from fetching simultaneously
        with self._agent_fetch_lock:
            if (now - self._last_agent_fetch).total_seconds() < 60:
                return
            
            self._last_agent_fetch = now
            
            try:
                from cai.agents import get_available_agents
                
                # Get agents and filter out parallel patterns (like /agent list does)
                all_agents = get_available_agents()
                regular_agents = []
                
                for agent_key, agent in all_agents.items():
                    # Skip parallel patterns in completion (matches /agent list behavior)
                    if hasattr(agent, "_pattern"):
                        pattern = agent._pattern
                        if hasattr(pattern, "type"):
                            pattern_type_value = getattr(pattern.type, 'value', str(pattern.type))
                            if pattern_type_value == "parallel":
                                continue
                    regular_agents.append(agent_key)
                
                self._cached_agents = regular_agents
                
                # Create number mappings (1-based indexing)
                self._cached_agent_numbers = {}
                for i, agent_key in enumerate(self._cached_agents, 1):
                    self._cached_agent_numbers[str(i)] = agent_key
                    
            except Exception:  # pylint: disable=broad-except
                # Silently fail if agent fetching is not available
                pass
    
    def _background_fetch_models(self):
        """Fetch models in background to avoid blocking the UI."""
        try:
            self.fetch_all_models()
        except Exception:  # pylint: disable=broad-except
            pass

    def fetch_all_models(self):  # pylint: disable=too-many-branches,too-many-statements,inconsistent-return-statements,line-too-long # noqa: E501
        """Fetch all available models (predefined + LiteLLM + Ollama) to match /model command."""
        # Only fetch every 60 seconds to avoid excessive API calls
        now = datetime.datetime.now()
        
        # Use a lock to prevent multiple threads from fetching simultaneously
        with self._fetch_lock:
            if (now - self._last_model_fetch).total_seconds() < 60:
                return
            
            self._last_model_fetch = now
            
            # Start with predefined models from the shared source of truth
            all_models = get_predefined_model_names()

            # Fetch LiteLLM models (matches the /model command behavior)
            try:
                litellm_url = (
                    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
                    "model_prices_and_context_window.json"
                )
                response = requests.get(litellm_url, timeout=2)
                
                if response.status_code == 200:
                    litellm_data = response.json()
                    # Add LiteLLM models (sorted for consistency)
                    litellm_models = sorted(litellm_data.keys())
                    all_models.extend(litellm_models)
            except Exception:  # pylint: disable=broad-except
                # Silently fail if LiteLLM is not available
                pass

            # Fetch Ollama models
            try:
                # Get Ollama models with a short timeout to prevent hanging
                api_base = get_ollama_api_base()
                
                # Add authentication headers for Ollama Cloud if using OPENAI_BASE_URL
                headers = {}
                if "ollama.com" in api_base:
                    api_key = os.getenv("OPENAI_API_KEY")
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"
                
                response = requests.get(
                    f"{api_base.replace('/v1', '')}/api/tags",
                    headers=headers,
                    timeout=0.5)

                if response.status_code == 200:
                    data = response.json()
                    if 'models' in data:
                        models = data['models']
                    else:
                        # Fallback for older Ollama versions
                        models = data.get('items', [])

                    ollama_models = [model.get('name', '') for model in models]
                    all_models.extend(ollama_models)
            except Exception:  # pylint: disable=broad-except
                # Silently fail if Ollama is not available
                pass

            # Cache all models that the /model command can handle
            self._cached_models = all_models

            # Create number mappings for models (1-based indexing)
            # This matches the /model command numbering exactly
            self._cached_model_numbers = {}
            for i, model in enumerate(self._cached_models, 1):
                self._cached_model_numbers[str(i)] = model

    def record_command_usage(self, command: str):
        """Record command usage for command shadowing.

        Args:
            command: The command that was used
        """
        if command.startswith('/'):
            # Extract the main command
            parts = command.split()
            main_command = parts[0]

            # Update usage count
            if main_command in self.command_history:
                self.command_history[main_command] += 1
            else:
                self.command_history[main_command] = 1

    @lru_cache(maxsize=1)
    def get_command_descriptions(self):
        """Get descriptions for all commands.

        Returns:
            A dictionary mapping command names to descriptions
        """
        global COMMAND_DESCRIPTIONS_CACHE
        if COMMAND_DESCRIPTIONS_CACHE is None:
            COMMAND_DESCRIPTIONS_CACHE = {cmd.name: cmd.description for cmd in COMMANDS.values()}
        return COMMAND_DESCRIPTIONS_CACHE

    @lru_cache(maxsize=1)
    def get_subcommand_descriptions(self):
        """Get descriptions for all subcommands.

        Returns:
            A dictionary mapping command paths to descriptions
        """
        global SUBCOMMAND_DESCRIPTIONS_CACHE
        if SUBCOMMAND_DESCRIPTIONS_CACHE is None:
            descriptions = {}
            for cmd in COMMANDS.values():
                for subcmd in cmd.get_subcommands():
                    key = f"{cmd.name} {subcmd}"
                    descriptions[key] = cmd.get_subcommand_description(subcmd)
            SUBCOMMAND_DESCRIPTIONS_CACHE = descriptions
        return SUBCOMMAND_DESCRIPTIONS_CACHE

    @lru_cache(maxsize=1)
    def get_all_commands(self):
        """Get all commands and their subcommands.

        Returns:
            A dictionary mapping command names to lists of subcommand names
        """
        global ALL_COMMANDS_CACHE
        if ALL_COMMANDS_CACHE is None:
            ALL_COMMANDS_CACHE = {cmd.name: cmd.get_subcommands() for cmd in COMMANDS.values()}
        return ALL_COMMANDS_CACHE

    # Cache for command suggestions to avoid recalculating
    _command_suggestions_cache = {}
    _command_suggestions_last_update = 0
    _command_suggestions_update_interval = 1.0  # Update every second

    def get_command_suggestions(self, current_word: str) -> List[Completion]:
        """Get command suggestions with fuzzy matching.

        Args:
            current_word: The current word being typed

        Returns:
            A list of completions for commands
        """
        # Check cache first
        current_time = time.time()
        cache_key = current_word
        
        if (cache_key in self._command_suggestions_cache and
                current_time - self._command_suggestions_last_update < 
                self._command_suggestions_update_interval):
            return self._command_suggestions_cache[cache_key]
        
        suggestions = []

        # Get command descriptions
        command_descriptions = self.get_command_descriptions()

        # Sort commands by usage frequency (for command shadowing)
        sorted_commands = sorted(
            command_descriptions.items(),
            key=lambda x: self.command_history.get(x[0], 0),
            reverse=True
        )

        # Add command completions
        for cmd, description in sorted_commands:
            # Exact prefix match
            if cmd.startswith(current_word):
                suggestions.append(Completion(
                    cmd,
                    start_position=-len(current_word),
                    display=HTML(
                        f"<ansicyan><b>{cmd:<15}</b></ansicyan> "
                        f"{description}"),
                    style="fg:ansicyan bold"
                ))
            # Fuzzy match (contains the substring)
            elif current_word in cmd and not cmd.startswith(current_word):
                suggestions.append(Completion(
                    cmd,
                    start_position=-len(current_word),
                    display=HTML(
                        f"<ansicyan>{cmd:<15}</ansicyan> {description}"),
                    style="fg:ansicyan"
                ))

        # Add alias completions
        for alias, cmd in sorted(COMMAND_ALIASES.items()):
            cmd_description = command_descriptions.get(cmd, "")
            if alias.startswith(current_word):
                suggestions.append(Completion(
                    alias,
                    start_position=-len(current_word),
                    display=HTML(
                        f"<ansigreen><b>{alias:<15}</b></ansigreen> "
                        f"{cmd} - {cmd_description}"),
                    style="fg:ansigreen bold"
                ))
            elif current_word in alias and not alias.startswith(current_word):
                suggestions.append(Completion(
                    alias,
                    start_position=-len(current_word),
                    display=HTML(
                        f"<ansigreen>{alias:<15}</ansigreen> "
                        f"{cmd} - {cmd_description}"),
                    style="fg:ansigreen"
                ))
        
        # Update cache
        self._command_suggestions_cache[cache_key] = suggestions
        self._command_suggestions_last_update = current_time
        
        return suggestions

    # Cache for command shadow
    _command_shadow_cache = {}
    _command_shadow_last_update = 0
    _command_shadow_update_interval = 0.2  # Update every 200ms

    @lru_cache(maxsize=100)
    def _get_command_shadow_cached(self, text: str) -> Optional[str]:
        """Cached version of command shadow lookup."""
        if not text or not text.startswith('/'):
            return None

        # Find commands that start with the current input
        matching_commands = []
        for cmd, count in self.command_history.items():
            if cmd.startswith(text) and cmd != text:
                matching_commands.append((cmd, count))

        # Sort by usage count (descending)
        matching_commands.sort(key=lambda x: x[1], reverse=True)

        # Return the most frequently used command
        if matching_commands:
            return matching_commands[0][0]

        return None

    def get_command_shadow(self, text: str) -> Optional[str]:
        """Get a command shadow suggestion based on command history.

        This method returns a suggestion for command shadowing based on
        the current input and command usage history.

        Args:
            text: The current input text

        Returns:
            A suggested command completion or None if no suggestion
        """
        # Check cache first
        current_time = time.time()
        
        if (text in self._command_shadow_cache and
                current_time - self._command_shadow_last_update < 
                self._command_shadow_update_interval):
            return self._command_shadow_cache[text]
        
        # Get shadow from cached function
        result = self._get_command_shadow_cached(text)
        
        # Update cache
        self._command_shadow_cache[text] = result
        self._command_shadow_last_update = current_time
        
        return result

    # Cache for subcommand suggestions
    _subcommand_suggestions_cache = {}
    _subcommand_suggestions_last_update = 0
    _subcommand_suggestions_update_interval = 1.0  # Update every second
    
    def get_subcommand_suggestions(
            self, cmd: str, current_word: str) -> List[Completion]:
        """Get subcommand suggestions with fuzzy matching.

        Args:
            cmd: The main command
            current_word: The current word being typed

        Returns:
            A list of completions for subcommands
        """
        # Check cache first
        current_time = time.time()
        cache_key = f"{cmd}:{current_word}"
        
        if (cache_key in self._subcommand_suggestions_cache and
                current_time - self._subcommand_suggestions_last_update < 
                self._subcommand_suggestions_update_interval):
            return self._subcommand_suggestions_cache[cache_key]
            
        suggestions = []

        # If using an alias, get the real command
        cmd = COMMAND_ALIASES.get(cmd, cmd)

        all_commands = self.get_all_commands()
        subcommand_descriptions = self.get_subcommand_descriptions()

        if cmd in all_commands:
            for subcmd in sorted(all_commands[cmd]):
                # Get description for this subcommand if available
                subcmd_description = subcommand_descriptions.get(
                    f"{cmd} {subcmd}", "")

                # Exact prefix match
                if subcmd.startswith(current_word):
                    suggestions.append(Completion(
                        subcmd,
                        start_position=-len(current_word),
                        display=HTML(
                            f"<ansiyellow><b>{subcmd:<15}</b></ansiyellow> "
                            f"{subcmd_description}"),
                        style="fg:ansiyellow bold"
                    ))
                # Fuzzy match
                elif (current_word in subcmd and
                      not subcmd.startswith(current_word)):
                    suggestions.append(Completion(
                        subcmd,
                        start_position=-len(current_word),
                        display=HTML(
                            f"<ansiyellow>{subcmd:<15}</ansiyellow> "
                            f"{subcmd_description}"),
                        style="fg:ansiyellow"
                    ))
        
        # Update cache
        self._subcommand_suggestions_cache[cache_key] = suggestions
        self._subcommand_suggestions_last_update = current_time
        
        return suggestions

    def get_model_suggestions(self, current_word: str) -> List[Completion]:
        """Get model suggestions for the /model command.

        Args:
            current_word: The current word being typed

        Returns:
            A list of completions for models
        """
        suggestions = []

        # First try to complete model numbers
        for num, model_name in self._cached_model_numbers.items():
            if num.startswith(current_word):
                suggestions.append(Completion(
                    num,
                    start_position=-len(current_word),
                    display=HTML(
                        f"<ansiwhite><b>{num:<3}</b></ansiwhite> "
                        f"{model_name}"),
                    style="fg:ansiwhite bold"
                ))

        # Then try to complete model names
        for model in self._cached_models:
            model_name = model[0] if isinstance(model, tuple) else model            
            if model_name.startswith(current_word):
                suggestions.append(Completion(
                    model_name,
                    start_position=-len(current_word),
                    display=HTML(
                        f"<ansimagenta><b>{model_name}</b></ansimagenta>"),
                    style="fg:ansimagenta bold"
                ))
            elif (current_word.lower() in model_name.lower() and
                  not model_name.startswith(current_word)):
                suggestions.append(Completion(
                    model_name,
                    start_position=-len(current_word),
                    display=HTML(f"<ansimagenta>{model_name}</ansimagenta>"),
                    style="fg:ansimagenta"
                ))

        return suggestions

    def get_agent_suggestions(self, current_word: str) -> List[Completion]:
        """Get agent suggestions for the /agent command."""
        suggestions = []

        # Refresh agents if needed (non-blocking due to time-based caching)
        self.fetch_all_agents()

        # First try to complete agent numbers
        for num, agent_name in self._cached_agent_numbers.items():
            if num.startswith(current_word):
                # Get agent display name for better UX
                try:
                    from cai.agents import get_available_agents
                    agents = get_available_agents()
                    agent_obj = agents.get(agent_name)
                    display_name = getattr(agent_obj, "name", agent_name) if agent_obj else agent_name
                except (ImportError, AttributeError, KeyError):  # pylint: disable=broad-except
                    display_name = agent_name
                    
                suggestions.append(Completion(
                    num,
                    start_position=-len(current_word),
                    display=HTML(
                        f"<ansiwhite><b>{num:<3}</b></ansiwhite> "
                        f"{display_name}"),
                    style="fg:ansiwhite bold"
                ))

        # Then try to complete agent names
        for agent_key in self._cached_agents:
            if agent_key.startswith(current_word):
                suggestions.append(Completion(
                    agent_key,
                    start_position=-len(current_word),
                    display=HTML(
                        f"<ansimagenta><b>{agent_key}</b></ansimagenta>"),
                    style="fg:ansimagenta bold"
                ))
            elif (current_word.lower() in agent_key.lower() and
                  not agent_key.startswith(current_word)):
                suggestions.append(Completion(
                    agent_key,
                    start_position=-len(current_word),
                    display=HTML(f"<ansimagenta>{agent_key}</ansimagenta>"),
                    style="fg:ansimagenta"
                ))

        return suggestions

    def get_mcp_server_suggestions(self, current_word: str) -> List[Completion]:
        """Get MCP server name suggestions.
        
        Args:
            current_word: The current word being typed
            
        Returns:
            A list of completions for MCP servers
        """
        suggestions = []
        
        try:
            # Import the global MCP servers registry
            from cai.repl.commands.mcp import _GLOBAL_MCP_SERVERS
            
            # Get all active MCP server names
            for server_name in _GLOBAL_MCP_SERVERS.keys():
                # Get server type for display
                server = _GLOBAL_MCP_SERVERS[server_name]
                server_type = type(server).__name__.replace("MCPServer", "")
                
                # Exact prefix match
                if server_name.startswith(current_word):
                    suggestions.append(Completion(
                        server_name,
                        start_position=-len(current_word),
                        display=HTML(
                            f"<ansicyan><b>{server_name}</b></ansicyan> "
                            f"<ansiwhite>({server_type})</ansiwhite>"),
                        style="fg:ansicyan bold"
                    ))
                # Fuzzy match
                elif (current_word.lower() in server_name.lower() and
                      not server_name.startswith(current_word)):
                    suggestions.append(Completion(
                        server_name,
                        start_position=-len(current_word),
                        display=HTML(
                            f"<ansicyan>{server_name}</ansicyan> "
                            f"<ansiwhite>({server_type})</ansiwhite>"),
                        style="fg:ansicyan"
                    ))
        except (ImportError, AttributeError):
            pass  # No MCP servers available
            
        return suggestions

    def get_mcp_suggestions(self, words: List[str], current_word: str) -> List[Completion]:
        """Get context-aware MCP command completions.
        
        Args:
            words: List of words including empty string if trailing space
            current_word: The current word being typed (empty if trailing space)
        
        Returns:
            List of completion suggestions
        """
        suggestions = []
        
        # Get the actual typed words (excluding empty strings from trailing spaces)
        actual_words = [w for w in words if w]
        
        # Position 2: Completing subcommand (e.g., "/mcp <tab>")
        # Use the default subcommand handler - no need to duplicate!
        if len(words) == 2:
            return self.get_subcommand_suggestions(words[0], current_word)
        
        # Position 3: After subcommand (e.g., "/mcp load <tab>")
        elif len(words) == 3 and len(actual_words) > 1:
            subcommand = actual_words[1]
            
            if subcommand == "load":
                # Suggest transport types for load command
                if not current_word.startswith("http"):  # Don't suggest if typing URL
                    transports = [
                        ("stdio", "Local process communication"),
                        ("sse", "Server-Sent Events (HTTP)"),
                    ]
                    for transport, desc in transports:
                        if transport.startswith(current_word):
                            suggestions.append(Completion(
                                transport,
                                start_position=-len(current_word),
                                display=HTML(
                                    f"<ansiyellow><b>{transport}</b></ansiyellow> "
                                    f"<ansiwhite>- {desc}</ansiwhite>"),
                                style="fg:ansiyellow bold"
                            ))
                            
            elif subcommand in ["add", "remove", "tools"]:
                # These commands need an MCP server name
                suggestions.extend(self.get_mcp_server_suggestions(current_word))
        
        # Position 4: After server name in add command (e.g., "/mcp add server <tab>")
        elif len(words) == 4 and len(actual_words) > 1:
            subcommand = actual_words[1]
            
            if subcommand == "add":
                # After server name, suggest agent names
                suggestions.extend(self.get_agent_suggestions(current_word))
                
        return suggestions

    # pylint: disable=unused-argument
    def get_completions(self, document, complete_event):
        """Get completions for the current document
        with fuzzy matching support.

        Args:
            document: The document to complete
            complete_event: The completion event

        Returns:
            A generator of completions
        """
        # Keep original text to detect trailing spaces
        text_original = document.text_before_cursor
        text = text_original.strip()
        words = text.split()
        
        # Check if there's a trailing space (user finished typing a word)
        has_trailing_space = text_original and text_original[-1] == ' '

        # Refresh Ollama models and agents periodically
        self.fetch_all_models()
        self.fetch_all_agents()

        if not text:
            # Show all main commands with descriptions
            command_descriptions = self.get_command_descriptions()

            # Sort commands by usage frequency (for command shadowing)
            sorted_commands = sorted(
                command_descriptions.items(),
                key=lambda x: self.command_history.get(x[0], 0),
                reverse=True
            )

            for cmd, description in sorted_commands:
                yield Completion(
                    cmd,
                    start_position=0,
                    display=HTML(
                        f"<ansicyan><b>{cmd:<15}</b></ansicyan> "
                        f"{description}"),
                    style="fg:ansicyan bold"
                )
            return

        if text.startswith('/'):
            # Determine current word and effective word count based on trailing space
            # Example: "/mcp " has trailing space, so current_word="" and we add empty string to words
            # Example: "/mcp" has no trailing space, so current_word="/mcp" 
            if has_trailing_space:
                current_word = ""
                effective_words = words + [""]  # Add empty string to represent new word position
            else:
                current_word = words[-1] if words else ""
                effective_words = words

            # Main command completion (first word)
            if len(effective_words) == 1 and not has_trailing_space:
                # Get command suggestions
                yield from self.get_command_suggestions(current_word)

            # Subcommand completion (second word)
            elif len(effective_words) == 2:
                cmd = words[0]

                # Special handling for model command
                if cmd in ["/model", "/mod"]:
                    yield from self.get_model_suggestions(current_word)
                # Add special handling for agent command
                elif cmd in ["/agent", "/a"]:
                    yield from self.get_agent_suggestions(current_word)
                # Add special handling for MCP command
                elif cmd in ["/mcp", "/m"]:
                    yield from self.get_mcp_suggestions(effective_words, current_word)
                else:
                    # Get subcommand suggestions
                    yield from self.get_subcommand_suggestions(cmd, current_word)

            # Third word completion
            elif len(effective_words) == 3:
                cmd = words[0]
                subcommand = words[1] if len(words) > 1 else ""
                
                # Agent select completion
                if cmd in ["/agent", "/a"] and subcommand in ["select", "info"]:
                    yield from self.get_agent_suggestions(current_word)
                # MCP command completion for third word
                elif cmd in ["/mcp", "/m"]:
                    yield from self.get_mcp_suggestions(effective_words, current_word)
            
            # Fourth word completion (for MCP add command)
            elif len(effective_words) == 4:
                cmd = words[0]
                
                # MCP add command needs agent name as fourth word
                if cmd in ["/mcp", "/m"]:
                    yield from self.get_mcp_suggestions(effective_words, current_word)
