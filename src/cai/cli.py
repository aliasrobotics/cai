"""
This module provides a CLI interface for testing and
interacting with CAI agents.

Environment Variables
---------------------
    Required:
        N/A

    Optional:
        CTF_NAME: Name of the CTF challenge to
            run (e.g. "picoctf_static_flag")
        CTF_CHALLENGE: Specific challenge name
            within the CTF to test
        CTF_SUBNET: Network subnet for the CTF
            container (default: "192.168.3.0/24")
        CTF_IP: IP address for the CTF
            container (default: "192.168.3.100")
        CTF_INSIDE: Whether to conquer the CTF from
            within container (default: "true")

        CAI_MODEL: Model to use for agents
            (default: "alias1")
        CAI_DEBUG: Set debug output level (default: "1")
            - 0: Only tool outputs
            - 1: Verbose debug output
            - 2: CLI debug output
        CAI_BRIEF: Enable/disable brief output mode (default: "false")
        CAI_MAX_TURNS: Maximum number of turns for
            agent interactions (default: "inf")
        CAI_TRACING: Enable/disable OpenTelemetry tracing
            (default: "true"). When enabled, traces execution
            flow and agent interactions for debugging and analysis.
        CAI_AGENT_TYPE: Specify the agents to use it could take
            the value of (default: "one_tool_agent"). Use "/agent"
            command in CLI to list all available agents.
        CAI_STATE: Enable/disable stateful mode (default: "false").
            When enabled, the agent will use a state agent to keep
            track of the state of the network and the flags found.
        CAI_MEMORY: Enable/disable memory mode (default: "false")
            - episodic: use episodic memory
            - semantic: use semantic memory
            - all: use both episodic and semantic memorys
        CAI_MEMORY_ONLINE: Enable/disable online memory mode
            (default: "false")
        CAI_MEMORY_OFFLINE: Enable/disable offline memory
            (default: "false")
        CAI_ENV_CONTEXT: Add environment context, dirs and
            current env available (default: "true")
        CAI_MEMORY_ONLINE_INTERVAL: Number of turns between
            online memory updates (default: "5")
        CAI_PRICE_LIMIT: Price limit for the conversation in dollars
            (default: "1")
        CAI_SUPPORT_MODEL: Model to use for the support agent
            (default: "o3-mini")
        CAI_SUPPORT_INTERVAL: Number of turns between support agent
            executions (default: "5")
        CAI_STREAM: Enable/disable streaming output in rich panel
            (default: "false")
        CAI_TELEMETRY: Enable/disable telemetry (default: "true")
        CAI_PARALLEL: Number of parallel agent instances to run
            (default: "1"). When set to values greater than 1,
            executes multiple instances of the same agent in
            parallel and displays all results.
        CAI_GUARDRAILS: Enable/disable security guardrails for agents
            (default: "true"). When enabled, applies security guardrails
            to prevent potentially dangerous outputs and inputs. Set to
            "false" to disable all guardrail functionality.

    Extensions (only applicable if the right extension is installed):

        "report"
            CAI_REPORT: Enable/disable reporter mode. Possible values:
                - ctf (default): do a report from a ctf resolution
                - nis2: do a report for nis2
                - pentesting: do a report from a pentesting

Usage Examples:

    # Run against a CTF
    CTF_NAME="kiddoctf" CTF_CHALLENGE="02 linux ii" \
        CAI_AGENT_TYPE="one_tool_agent" CAI_MODEL="alias1" \
        CAI_TRACING="false" cai

    # Run a harder CTF
    CTF_NAME="hackableii" CAI_AGENT_TYPE="redteam_agent" \
        CTF_INSIDE="False" CAI_MODEL="alias1" \
        CAI_TRACING="false" cai

    # Run without a target in human-in-the-loop mode, generating a report
    CAI_TRACING=False CAI_REPORT=pentesting CAI_MODEL="alias1" \
        cai

    # Run with online episodic memory
    #   registers memory every 5 turns:
    #   limits the cost to 5 dollars
    CTF_NAME="hackableII" CAI_MEMORY="episodic" \
        CAI_MODEL="alias1" CAI_MEMORY_ONLINE="True" \
        CTF_INSIDE="False" CTF_HINTS="False"  \
        CAI_PRICE_LIMIT="5" cai

    # Run with custom long_term_memory interval
    # Executes memory long_term_memory every 3 turns:
    CTF_NAME="hackableII" CAI_MEMORY="episodic" \
        CAI_MODEL="alias1" CAI_MEMORY_ONLINE_INTERVAL="3" \
        CAI_MEMORY_ONLINE="False" CTF_INSIDE="False" \
        CTF_HINTS="False" cai
        
    # Run with parallel agents (3 instances)
    CTF_NAME="hackableII" CAI_AGENT_TYPE="redteam_agent" \
        CAI_MODEL="alias1" CAI_PARALLEL="3" cai
"""

# Load environment variables from .env file FIRST, before any imports
import os

from dotenv import load_dotenv

# Load .env file from current working directory with override
# This ensures env vars from .env take precedence over system env vars
load_dotenv(override=True)

# Configure Python warnings BEFORE any other imports
import warnings
import sys

# Custom warning handler to suppress specific warnings
def custom_warning_handler(message, category, filename, lineno, file=None, line=None):
    # Only show warnings in debug mode
    if os.getenv("CAI_DEBUG", "1") == "2":
        # Format and print the warning
        warnings.showwarning(message, category, filename, lineno, file, line)
    # Otherwise, silently ignore

# Set custom warning handler
warnings.showwarning = custom_warning_handler

# Suppress ALL warnings in production mode (unless CAI_DEBUG=2)
if os.getenv("CAI_DEBUG", "1") != "2":
    warnings.filterwarnings("ignore")
    # Also set environment variable to prevent warnings from subprocesses
    os.environ["PYTHONWARNINGS"] = "ignore"

import asyncio
import logging
import shlex
import time

# Configure comprehensive error filtering
class ComprehensiveErrorFilter(logging.Filter):
    """Filter to suppress various expected errors and warnings."""
    def filter(self, record):
        msg = record.getMessage().lower()
        
        # List of patterns to suppress completely
        suppress_patterns = [
            "asynchronous generator",
            "asyncgen",
            "closedresourceerror",
            "didn't stop after athrow",
            "didnt stop after athrow",
            "didn't stop after athrow",
            "generator didn't stop",
            "generator didn't stop",
            "cancel scope",
            "unhandled errors in a taskgroup",
            "error in post_writer",
            "was never awaited",
            "connection error while setting up",
            "error closing",
            "anyio._backends",
            "httpx_sse",
            "connection reset by peer",
            "broken pipe", 
            "connection aborted",
            "runtime warning",
            "runtimewarning",
            "coroutine",
            "task was destroyed",
            "event loop is closed",
            "session is closed",
            # Add specific aiohttp session warnings
            "unclosed client session",
            "unclosed connector",
            "client_session:",
            "connector:",
            "connections:",
        ]
        
        # Check if any suppress pattern matches
        for pattern in suppress_patterns:
            if pattern in msg:
                return False
        
        # SSE connection errors during cleanup
        if "sse" in msg and any(word in msg for word in ["cleanup", "closing", "shutdown", "closed"]):
            return False
            
        # MCP connection errors that we handle
        if "error invoking mcp tool" in msg and "closedresourceerror" in msg:
            return False
            
        # MCP reconnection messages - change to DEBUG level
        if "mcp server session not found" in msg or "successfully reconnected to mcp server" in msg:
            record.levelno = logging.DEBUG
            record.levelname = "DEBUG"
            
        return True

# Apply comprehensive filter to all relevant loggers
comprehensive_filter = ComprehensiveErrorFilter()

# List of loggers to configure
loggers_to_configure = [
    "openai.agents",
    "mcp.client.sse", 
    "httpx",
    "httpx_sse",
    "mcp",
    "asyncio",
    "anyio",
    "anyio._backends._asyncio",
    "cai.sdk.agents",
    "aiohttp",  # Add aiohttp logger to suppress session warnings
]

for logger_name in loggers_to_configure:
    logger = logging.getLogger(logger_name)
    logger.addFilter(comprehensive_filter)
    # Set appropriate level - ERROR for most, WARNING for critical ones
    if logger_name in ["asyncio", "anyio", "anyio._backends._asyncio"]:
        logger.setLevel(logging.ERROR)  # Only show critical errors
    else:
        logger.setLevel(logging.WARNING)

# Suppress various warnings globally with more comprehensive patterns
warnings.filterwarnings("ignore", category=RuntimeWarning)  # Ignore ALL RuntimeWarnings
warnings.filterwarnings("ignore", category=ResourceWarning)  # Ignore ResourceWarnings (aiohttp sessions)
warnings.filterwarnings("ignore", message=".*asynchronous generator.*")
warnings.filterwarnings("ignore", message=".*was never awaited.*")
warnings.filterwarnings("ignore", message=".*didn't stop after athrow.*")
warnings.filterwarnings("ignore", message=".*didn't stop after athrow.*")
warnings.filterwarnings("ignore", message=".*cancel scope.*")
warnings.filterwarnings("ignore", message=".*coroutine.*was never awaited.*")
warnings.filterwarnings("ignore", message=".*generator.*didn't stop.*")
warnings.filterwarnings("ignore", message=".*Task was destroyed.*")
warnings.filterwarnings("ignore", message=".*Event loop is closed.*")
# Add specific aiohttp session warnings
warnings.filterwarnings("ignore", message=".*Unclosed client session.*")
warnings.filterwarnings("ignore", message=".*Unclosed connector.*")
warnings.filterwarnings("ignore", message=".*client_session:.*")
warnings.filterwarnings("ignore", message=".*connector:.*")
warnings.filterwarnings("ignore", message=".*connections:.*")

# Also configure Python's warning system to be less verbose
import sys
if not sys.warnoptions:
    warnings.simplefilter("ignore", RuntimeWarning)
    warnings.simplefilter("ignore", ResourceWarning)  # Also ignore ResourceWarnings

# Additional aiohttp warning suppression
def suppress_aiohttp_warnings():
    """Suppress aiohttp specific warnings about unclosed sessions."""
    try:
        import aiohttp
        # Suppress aiohttp warnings about unclosed sessions
        aiohttp_logger = logging.getLogger("aiohttp")
        aiohttp_logger.setLevel(logging.ERROR)  # Only show errors, not warnings
        
        # Also suppress aiohttp.client warnings
        aiohttp_client_logger = logging.getLogger("aiohttp.client")
        aiohttp_client_logger.setLevel(logging.ERROR)
        
        # Suppress aiohttp.connector warnings
        aiohttp_connector_logger = logging.getLogger("aiohttp.connector")
        aiohttp_connector_logger.setLevel(logging.ERROR)
        
    except ImportError:
        # aiohttp not installed, skip
        pass

# Call the function to suppress aiohttp warnings
suppress_aiohttp_warnings()

# OpenAI imports
from openai import AsyncOpenAI
from rich.console import Console

from cai import is_pentestperf_available

# CAI agents and metrics imports
from cai.agents import get_agent_by_name
from cai.internal.components.metrics import process_metrics

# CAI REPL imports
from cai.repl.commands import FuzzyCommandCompleter, handle_command as commands_handle_command

# Add import for parallel configs at the top of the file
from cai.repl.commands.parallel import PARALLEL_CONFIGS, ParallelConfig, PARALLEL_AGENT_INSTANCES

# Global storage for shared message histories (keyed by a unique identifier)
UNIFIED_MESSAGE_HISTORIES = {}
from cai.repl.ui.banner import display_banner, display_quick_guide
from cai.repl.ui.keybindings import create_key_bindings
from cai.repl.ui.logging import setup_session_logging
from cai.repl.ui.prompt import get_user_input
from cai.repl.ui.toolbar import get_toolbar_with_refresh

# CAI SDK imports
from cai.sdk.agents import Agent, OpenAIChatCompletionsModel, Runner, set_tracing_disabled
from cai.sdk.agents.items import ToolCallOutputItem
from cai.sdk.agents.exceptions import OutputGuardrailTripwireTriggered, InputGuardrailTripwireTriggered
from cai.sdk.agents.models.openai_chatcompletions import (
    get_agent_message_history,
    get_all_agent_histories,
)
# Import handled where needed to avoid circular imports
from cai.sdk.agents.run_to_jsonl import get_session_recorder
from cai.sdk.agents.global_usage_tracker import GLOBAL_USAGE_TRACKER
from cai.sdk.agents.stream_events import RunItemStreamEvent

# CAI utility imports
from cai.util import (
    color,
    fix_litellm_transcription_annotations,
    setup_ctf,
    start_active_timer,
    start_idle_timer,
    stop_active_timer,
    stop_idle_timer,
)

ctf_global = None
messages_ctf = ""
ctf_init = 1
previous_ctf_name = os.getenv("CTF_NAME", None)
if is_pentestperf_available() and os.getenv("CTF_NAME", None):
    ctf, messages_ctf = setup_ctf()
    ctf_global = ctf
    ctf_init = 0

# NOTE: This is needed when using LiteLLM Proxy Server
#
# external_client = AsyncOpenAI(
#     base_url = os.getenv('LITELLM_BASE_URL', 'http://localhost:4000'),
#     api_key=os.getenv('LITELLM_API_KEY', 'key'))
#
# set_default_openai_client(external_client)

# Global variables for timing tracking
global START_TIME
START_TIME = time.time()

set_tracing_disabled(True)


def update_agent_models_recursively(agent, new_model, visited=None):
    """
    Recursively update the model for an agent and all agents in its handoffs.

    Args:
        agent: The agent to update
        new_model: The new model string to set
        visited: Set of agent names already visited to prevent infinite loops
    """
    if visited is None:
        visited = set()

    # Avoid infinite loops by tracking visited agents
    if agent.name in visited:
        return
    visited.add(agent.name)

    # Update the main agent's model
    if hasattr(agent, "model") and hasattr(agent.model, "model"):
        agent.model.model = new_model
        # Also ensure the agent name is set correctly in the model
        if hasattr(agent.model, "agent_name"):
            agent.model.agent_name = agent.name
        
        # IMPORTANT: Clear any cached state in the model that might be model-specific
        # This ensures the model doesn't have stale state from the previous model
        if hasattr(agent.model, "_client"):
            # Force recreation of the client on next use
            agent.model._client = None
        if hasattr(agent.model, "_converter"):
            # Reset the converter's state
            if hasattr(agent.model._converter, "recent_tool_calls"):
                agent.model._converter.recent_tool_calls.clear()
            if hasattr(agent.model._converter, "tool_outputs"):
                agent.model._converter.tool_outputs.clear()

    # Update models for all handoff agents
    if hasattr(agent, "handoffs"):
        for handoff_item in agent.handoffs:
            # Handle both direct Agent references and Handoff objects
            if hasattr(handoff_item, "on_invoke_handoff"):
                # This is a Handoff object
                # For handoffs created with the handoff() function, the agent is stored
                # in the closure of the on_invoke_handoff function
                # We can try to extract it from the function's closure
                try:
                    # Get the closure variables of the handoff function
                    if (
                        hasattr(handoff_item.on_invoke_handoff, "__closure__")
                        and handoff_item.on_invoke_handoff.__closure__
                    ):
                        for cell in handoff_item.on_invoke_handoff.__closure__:
                            if hasattr(cell.cell_contents, "model") and hasattr(
                                cell.cell_contents, "name"
                            ):
                                # This looks like an agent
                                handoff_agent = cell.cell_contents
                                update_agent_models_recursively(handoff_agent, new_model, visited)
                                break
                except Exception:
                    # If we can't extract the agent from closure, skip it
                    pass
            elif hasattr(handoff_item, "model"):
                # This is a direct Agent reference
                update_agent_models_recursively(handoff_item, new_model, visited)


def run_cai_cli(
    starting_agent, context_variables=None, max_turns=float("inf"), force_until_flag=False, initial_prompt=None
):
    """
    Run a simple interactive CLI loop for CAI.

    Args:
        starting_agent: The initial agent to use for the conversation
        context_variables: Optional dictionary of context variables to initialize the session
        max_turns: Maximum number of interaction turns before terminating (default: infinity)
        force_until_flag: Whether to force execution until a flag is found
        initial_prompt: Optional initial prompt to execute immediately before entering interactive mode

    Returns:
        None
    """
    ACTIVE_TIME = 0  # TODO: review this variable

    agent = starting_agent
    turn_count = 0
    idle_time = 0
    console = Console()
    last_model = os.getenv("CAI_MODEL", "alias1")
    last_agent_type = os.getenv("CAI_AGENT_TYPE", "one_tool_agent")
    parallel_count = int(os.getenv("CAI_PARALLEL", "1"))
    use_initial_prompt = initial_prompt is not None
    
    # Reset cost tracking at the start
    from cai.util import COST_TRACKER
    COST_TRACKER.reset_agent_costs()
    
    # Reset simple agent manager for clean start
    from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
    AGENT_MANAGER.reset_registry()
    
    # Register the starting agent with AGENT_MANAGER
    starting_agent_name = getattr(starting_agent, "name", last_agent_type)
    AGENT_MANAGER.switch_to_single_agent(starting_agent, starting_agent_name)

    # Initialize command completer and key bindings
    command_completer = FuzzyCommandCompleter()
    current_text = [""]
    kb = create_key_bindings(current_text)

    # Setup session logging
    history_file = setup_session_logging()

    # Initialize session logger and display the filename
    session_logger = get_session_recorder()
    
    # Start global usage tracking session
    GLOBAL_USAGE_TRACKER.start_session(
        session_id=session_logger.session_id,
        agent_name=None  # Will be updated when agent is selected
    )

    # Display banner
    display_banner(console)
    print("\n")
    display_quick_guide(console)

    # Function to get the short name of the agent for display
    def get_agent_short_name(agent):
        if hasattr(agent, "name"):
            # Return the full agent name instead of just the first word
            return agent.name
        return "Agent"

    # Prevent the model from using its own rich streaming to avoid conflicts
    # but allow final output message to ensure all agent responses are shown
    if hasattr(agent, "model"):
        if hasattr(agent.model, "disable_rich_streaming"):
            agent.model.disable_rich_streaming = False  # Now True as the model handles streaming
        if hasattr(agent.model, "suppress_final_output"):
            agent.model.suppress_final_output = False  # Changed to False to show all agent messages

        # Set the agent name in the model for proper display in streaming panel
        if hasattr(agent.model, "set_agent_name"):
            agent.model.set_agent_name(get_agent_short_name(agent))

    prev_max_turns = max_turns
    turn_limit_reached = False

    while True:
        # Check if the ctf name has changed and instanciate the ctf
        global previous_ctf_name
        global ctf_global
        global messages_ctf
        global ctf_init
        if previous_ctf_name != os.getenv("CTF_NAME", None):
            if is_pentestperf_available():
                if ctf_global:
                    ctf_global.stop_ctf()
                ctf, messages_ctf = setup_ctf()
                ctf_global = ctf
                previous_ctf_name = os.getenv("CTF_NAME", None)
                ctf_init = 0
        # Check if CAI_MAX_TURNS has been updated via /config
        current_max_turns = os.getenv("CAI_MAX_TURNS", "inf")
        if current_max_turns != str(prev_max_turns):
            max_turns = float(current_max_turns)
            prev_max_turns = max_turns

            if turn_limit_reached and turn_count < max_turns:
                turn_limit_reached = False
                console.print(
                    "[green]Turn limit increased. You can now continue using CAI.[/green]"
                )

        # Check if max turns is reached
        if turn_count >= max_turns and max_turns != float("inf"):
            if not turn_limit_reached:
                turn_limit_reached = True
                console.print(
                    f"[bold red]Error: Maximum turn limit ({int(max_turns)}) reached.[/bold red]"
                )
                console.print(
                    "[yellow]You must increase the limit using the /config command: /config CAI_MAX_TURNS=<new_value>[/yellow]"
                )
                console.print(
                    "[yellow]Only CLI commands (starting with '/') will be processed until the limit is increased.[/yellow]"
                )

        try:
            # Start measuring user idle time
            start_idle_timer()
            import time
            idle_start_time = time.time()

            # Check if model has changed and update if needed
            current_model = os.getenv("CAI_MODEL", "alias1")
            # Check for agent-specific model override
            agent_specific_model = os.getenv(f"CAI_{last_agent_type.upper()}_MODEL")
            if agent_specific_model:
                current_model = agent_specific_model

            if current_model != last_model and hasattr(agent, "model"):
                # Update the model recursively for the agent and all handoff agents
                update_agent_models_recursively(agent, current_model)
                last_model = current_model

            # Check if agent type has changed and recreate agent if needed
            current_agent_type = os.getenv("CAI_AGENT_TYPE", "one_tool_agent")
            # Update parallel_count to reflect changes from /parallel command
            parallel_count = int(os.getenv("CAI_PARALLEL", "1"))
            
            
            if current_agent_type != last_agent_type:
                # Check if the /agent command already handled the switch
                if os.environ.get("CAI_AGENT_SWITCH_HANDLED") == "1":
                    os.environ["CAI_AGENT_SWITCH_HANDLED"] = "0"  # Reset flag
                    
                    # Just get the existing agent that was already switched
                    from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
                    
                    # First try to get the strong reference if available
                    if hasattr(AGENT_MANAGER, '_current_agent_strong_ref'):
                        agent = AGENT_MANAGER._current_agent_strong_ref
                        # Clear the strong reference after using it
                        delattr(AGENT_MANAGER, '_current_agent_strong_ref')
                    else:
                        agent = AGENT_MANAGER.get_active_agent()
                    
                    if agent:
                        last_agent_type = current_agent_type
                    else:
                        # If the agent is None (weak reference expired), recreate it
                        agent = get_agent_by_name(current_agent_type, agent_id="P1")
                        last_agent_type = current_agent_type
                        # Re-register with AGENT_MANAGER
                        agent_name = agent.name if hasattr(agent, "name") else current_agent_type
                        AGENT_MANAGER.set_active_agent(agent, agent_name, "P1")
                    continue
                
                try:
                    # CRITICAL: Set up history transfer BEFORE creating the new agent
                    from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
                    
                    # Get the current agent's history before switching
                    if hasattr(agent, "name"):
                        current_agent_name = agent.name
                        current_history = AGENT_MANAGER.get_message_history(current_agent_name)
                        if current_history:
                            AGENT_MANAGER._pending_history_transfer = list(current_history)  # Make a copy
                    
                    # Now create the new agent
                    agent = get_agent_by_name(current_agent_type, agent_id="P1")
                    last_agent_type = current_agent_type
                    
                    # Reset cost tracking for the new agent
                    from cai.util import COST_TRACKER
                    COST_TRACKER.reset_agent_costs()
                    
                    # Use the new switch_to_single_agent method for proper cleanup
                    # IMPORTANT: Always use the agent's proper name, not the agent key
                    agent_name = agent.name if hasattr(agent, "name") else current_agent_type
                    
                    # Check if this agent has already been switched to by /agent command
                    # If so, don't switch again to avoid clearing the history
                    current_active_agent = AGENT_MANAGER.get_active_agent()
                    current_active_name = AGENT_MANAGER._active_agent_name
                    
                    if current_active_name == agent_name:
                        # Just update the agent reference
                        agent = current_active_agent
                    else:
                        # Switch to the new agent
                        AGENT_MANAGER.switch_to_single_agent(agent, agent_name)
                    
                    # Sync the model's history with AGENT_MANAGER's history
                    # This ensures the model has its own history from AGENT_MANAGER
                    if hasattr(agent, "model") and hasattr(agent.model, "message_history"):
                        agent_history = AGENT_MANAGER.get_message_history(agent_name)
                        # Clear model's history and sync with AGENT_MANAGER
                        agent.model.message_history.clear()
                        if agent_history:
                            # Use extend() to avoid circular addition
                            agent.model.message_history.extend(agent_history)

                    # Configure the new agent's model flags
                    if hasattr(agent, "model"):
                        if hasattr(agent.model, "disable_rich_streaming"):
                            agent.model.disable_rich_streaming = (
                                False  # Now False to let model handle streaming
                            )
                        if hasattr(agent.model, "suppress_final_output"):
                            agent.model.suppress_final_output = (
                                False  # Changed to False to show all agent messages
                            )

                        # Apply current model to the new agent and all its handoff agents
                        # Check for agent-specific model override
                        agent_specific_model = os.getenv(f"CAI_{current_agent_type.upper()}_MODEL")
                        model_to_apply = (
                            agent_specific_model if agent_specific_model else current_model
                        )
                        update_agent_models_recursively(agent, model_to_apply)
                        last_model = model_to_apply

                        # Set agent name in the model for streaming display
                        if hasattr(agent.model, "set_agent_name"):
                            agent.model.set_agent_name(get_agent_short_name(agent))
                        
                        # Clear any asyncio tasks that might be lingering from the previous agent
                        # This helps prevent event loop issues after agent switching
                        try:
                            # Get all running tasks
                            all_tasks = asyncio.all_tasks() if hasattr(asyncio, 'all_tasks') else asyncio.Task.all_tasks()
                            # Cancel tasks that aren't the current task
                            current_task = asyncio.current_task() if hasattr(asyncio, 'current_task') else asyncio.Task.current_task()
                            for task in all_tasks:
                                if task != current_task and not task.done():
                                    task.cancel()
                        except RuntimeError:
                            # Not in an async context, which is fine
                            pass
                            
                except Exception as e:
                    # Log the error but don't display it unless in debug mode
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Error switching agent: {str(e)}")
                    if os.getenv("CAI_DEBUG", "1") == "2":
                        console.print(f"[red]Error switching agent: {str(e)}[/red]")

            if not force_until_flag and ctf_init != 0:
                # Use initial prompt on first iteration if provided
                if use_initial_prompt:
                    user_input = initial_prompt
                    use_initial_prompt = False  # Only use it once
                else:
                    # Get user input with command completion and history
                    user_input = get_user_input(
                        command_completer, kb, history_file, get_toolbar_with_refresh, current_text
                    )

            else:
                user_input = messages_ctf
                ctf_init = 1
            idle_time += time.time() - idle_start_time

            # Stop measuring user idle time and start measuring active time
            stop_idle_timer()
            start_active_timer()
            
            if not user_input.strip():
                user_input = "User input is empty, maybe wants to continue"  # Set a default message to continue the conversation

            # In parallel mode, all configured agents will run automatically
            # No agent selection menu - just run all agents

        except KeyboardInterrupt:
            # Print newline to ensure clean prompt display after interrupt
            print()

            def format_time(seconds):
                mins, secs = divmod(int(seconds), 60)
                hours, mins = divmod(mins, 60)
                return f"{hours:02d}:{mins:02d}:{secs:02d}"

            Total = time.time() - START_TIME
            idle_time += time.time() - idle_start_time

            # Save parallel agents' histories if we were in parallel mode
            try:
                if PARALLEL_CONFIGS and PARALLEL_ISOLATION.is_parallel_mode():
                    # Save each parallel agent's history
                    saved_count = 0
                    for idx, config in enumerate(PARALLEL_CONFIGS, 1):
                        instance_key = (config.agent_name, idx)
                        if instance_key in PARALLEL_AGENT_INSTANCES:
                            instance_agent = PARALLEL_AGENT_INSTANCES[instance_key]
                            if hasattr(instance_agent, 'model') and hasattr(instance_agent.model, 'message_history'):
                                # The agent's message history should already be updated in PARALLEL_ISOLATION
                                # via the add_to_message_history method, but let's make sure
                                agent_id = config.id or f"P{idx}"
                                if instance_agent.model.message_history:
                                    PARALLEL_ISOLATION.replace_isolated_history(agent_id, instance_agent.model.message_history)
                                    saved_count += 1
                    
                    if saved_count > 0:
                        # Sync isolated histories with AGENT_MANAGER for display
                        for idx, config in enumerate(PARALLEL_CONFIGS, 1):
                            agent_id = config.id or f"P{idx}"
                            isolated_history = PARALLEL_ISOLATION.get_isolated_history(agent_id)
                            if isolated_history:
                                # Get the agent display name
                                from cai.agents import get_available_agents
                                available_agents = get_available_agents()
                                if config.agent_name in available_agents:
                                    agent = available_agents[config.agent_name]
                                    agent_display_name = getattr(agent, "name", config.agent_name)
                                    
                                    # Add instance number if needed
                                    total_count = sum(1 for c in PARALLEL_CONFIGS if c.agent_name == config.agent_name)
                                    if total_count > 1:
                                        instance_num = 0
                                        for c in PARALLEL_CONFIGS:
                                            if c.agent_name == config.agent_name:
                                                instance_num += 1
                                                if c.id == config.id:
                                                    break
                                        agent_display_name = f"{agent_display_name} #{instance_num}"
                                    
                                    # Clear and replace the history in AGENT_MANAGER
                                    AGENT_MANAGER.clear_history(agent_display_name)
                                    for msg in isolated_history:
                                        AGENT_MANAGER.add_to_history(agent_display_name, msg)
            except Exception as e:
                # Only log this error in debug mode
                logger = logging.getLogger(__name__)
                logger.debug(f"Error saving parallel agents' histories: {str(e)}")

            # Clean up any pending tool calls before exiting
            try:
                # Access the converter directly to clean up any pending tool calls
                # converter is instance-based, access via agent.model._converter

                # Check if any tool calls are pending (have been issued but don't have responses)
                pending_calls = []
                if hasattr(agent.model, "_converter") and hasattr(
                    agent.model._converter, "recent_tool_calls"
                ):
                    for call_id, call_info in list(
                        agent.model._converter.recent_tool_calls.items()
                    ):
                        # Check if this tool call has a corresponding response in message_history
                        tool_response_exists = False
                        for msg in agent.model.message_history:
                            if msg.get("role") == "tool" and msg.get("tool_call_id") == call_id:
                                tool_response_exists = True
                                break

                        # If no tool response exists, create a synthetic one
                        if not tool_response_exists:
                            # First ensure there's a matching assistant message with this tool call
                            assistant_exists = False
                            for msg in agent.model.message_history:
                                if (
                                    msg.get("role") == "assistant"
                                    and msg.get("tool_calls")
                                    and any(
                                        tc.get("id") == call_id for tc in msg.get("tool_calls", [])
                                    )
                                ):
                                    assistant_exists = True
                                    break

                            # Add assistant message if needed
                            if not assistant_exists:
                                tool_call_msg = {
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": [
                                        {
                                            "id": call_id,
                                            "type": "function",
                                            "function": {
                                                "name": call_info.get("name", "unknown_function"),
                                                "arguments": call_info.get("arguments", "{}"),
                                            },
                                        }
                                    ],
                                }
                                agent.model.add_to_message_history(tool_call_msg)

                            # Add a synthetic tool response
                            tool_msg = {
                                "role": "tool",
                                "tool_call_id": call_id,
                                "content": "Operation interrupted by user (Keyboard Interrupt during shutdown)",
                            }
                            agent.model.add_to_message_history(tool_msg)
                            pending_calls.append(call_info.get("name", "unknown"))

                # Apply message list fixes to ensure consistency
                if pending_calls:
                    from cai.util import fix_message_list

                    agent.model.message_history[:] = fix_message_list(agent.model.message_history)
            except Exception:
                pass

            try:
                # Get more accurate active and idle time measurements from the timer functions
                from cai.util import COST_TRACKER, get_active_time_seconds, get_idle_time_seconds

                # Use the precise measurements from our timers
                active_time_seconds = get_active_time_seconds()
                idle_time_seconds = get_idle_time_seconds()

                # Format for display
                active_time_formatted = format_time(active_time_seconds)
                idle_time_formatted = format_time(idle_time_seconds)

                # Get session cost from the global cost tracker
                session_cost = COST_TRACKER.session_total_cost

                metrics = {
                    "session_time": format_time(Total),
                    "active_time": active_time_formatted,
                    "idle_time": idle_time_formatted,
                    "llm_time": format_time(active_time_seconds),  # Using active time as LLM time
                    "llm_percentage": round((active_time_seconds / Total) * 100, 1)
                    if Total > 0
                    else 0.0,
                    "session_cost": f"${session_cost:.6f}",  # Add formatted session cost
                }
                logging_path = (
                    session_logger.filename if hasattr(session_logger, "filename") else None
                )

                content = []
                content.append(f"Session Time: {metrics['session_time']}")
                content.append(
                    f"Active Time: {metrics['active_time']} ({metrics['llm_percentage']}%)"
                )
                content.append(f"Idle Time: {metrics['idle_time']}")
                content.append(
                    f"Total Session Cost: {metrics['session_cost']}"
                )  # Add cost to display
                if logging_path:
                    content.append(f"Log available at: {logging_path}")

                def print_session_summary(console, metrics, logging_path=None):
                    """
                    Print a session summary panel using Rich.
                    """
                    from rich.box import ROUNDED
                    from rich.console import Group
                    from rich.panel import Panel
                    from rich.text import Text

                    # Create Rich Text objects for each line
                    text_content = []
                    for i, line in enumerate(content):
                        if "Total Session Cost" in line:
                            # Format cost line with special styling
                            cost_text = Text()
                            parts = line.split(":")
                            cost_text.append(parts[0] + ":", style="bold")
                            cost_text.append(parts[1], style="bold green")
                            text_content.append(cost_text)
                        else:
                            text_content.append(Text(line))

                    time_panel = Panel(
                        Group(*text_content),
                        border_style="blue",
                        box=ROUNDED,
                        padding=(0, 1),
                        title="[bold]Session Summary[/bold]",
                        title_align="left",
                    )
                    console.print(time_panel, end="")

                print_session_summary(console, metrics, logging_path)

                # Upload logs if telemetry is enabled by checking the
                # env. variable CAI_TELEMETRY and there's internet connectivity
                telemetry_enabled = os.getenv("CAI_TELEMETRY", "true").lower() != "false"
                if (
                    telemetry_enabled
                    and hasattr(session_logger, "session_id")
                    and hasattr(session_logger, "filename")
                ):
                    process_metrics(
                        session_logger.filename,  # should match logging_path
                        sid=session_logger.session_id,
                    )

                # Log session end
                if session_logger:
                    session_logger.log_session_end()
                
                # End global usage tracking session
                GLOBAL_USAGE_TRACKER.end_session(final_cost=COST_TRACKER.session_total_cost)

                # Create symlink to the last log file
                if session_logger and hasattr(session_logger, "filename"):
                    create_last_log_symlink(session_logger.filename)

                # Prevent duplicate cost display from the COST_TRACKER exit handler
                os.environ["CAI_COST_DISPLAYED"] = "true"

                if is_pentestperf_available() and os.getenv("CTF_NAME", None):
                    ctf.stop_ctf()

            except Exception:
                pass
            break

        try:
            # Check if turn limit is reached and allow only CLI commands
            if (
                turn_limit_reached
                and not user_input.startswith("/")
                and not user_input.startswith("$")
            ):
                console.print(
                    "[bold red]Error: Turn limit reached. Only CLI commands are allowed.[/bold red]"
                )
                console.print(
                    "[yellow]Please use /config to increase CAI_MAX_TURNS limit.[/yellow]"
                )
                # Skip processing this input but continue the main loop
                stop_active_timer()
                start_idle_timer()
                continue

            # Check if we have parallel configurations to run
            if (
                PARALLEL_CONFIGS
                and not user_input.startswith("/")
                and not user_input.startswith("$")
            ):
                # Use parallel configurations instead of normal processing
                
                # Show which agents have custom prompts
                agents_with_prompts = [(idx, config) for idx, config in enumerate(PARALLEL_CONFIGS, 1) if config.prompt]
                
                # First ensure ALL parallel configs have agent instances (not just selected ones)
                # This prevents agents from disappearing from history when not selected
                from cai.agents import get_available_agents
                
                # Setup parallel isolation for these agents
                from cai.sdk.agents.parallel_isolation import PARALLEL_ISOLATION
                
                # Get agent IDs
                agent_ids = [config.id or f"P{idx}" for idx, config in enumerate(PARALLEL_CONFIGS, 1)]
                
                # Check if we already have isolated histories (e.g., from /load parallel)
                # If not, transfer the current agent's history to all parallel agents
                already_has_histories = False
                if PARALLEL_ISOLATION.is_parallel_mode():
                    # Check if at least one agent has a non-empty isolated history
                    for agent_id in agent_ids:
                        isolated_history = PARALLEL_ISOLATION.get_isolated_history(agent_id)
                        if isolated_history:
                            already_has_histories = True
                            break
                
                if not already_has_histories:
                    # Get the current agent's history to transfer
                    current_history = []
                    if hasattr(agent, 'model') and hasattr(agent.model, 'message_history'):
                        current_history = agent.model.message_history
                    elif hasattr(agent, 'name'):
                        from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
                        current_history = AGENT_MANAGER.get_message_history(agent.name)
                    
                    # Check if we should transfer history to all agents or just the first one
                    # Pattern 17 (Red/Blue team with different contexts) should only transfer to P1
                    transfer_to_all = True
                    
                    # Check if this is a pattern that requires different contexts
                    # This is typically pattern 17 or similar patterns with "different contexts" in the description
                    pattern_description = os.getenv("CAI_PATTERN_DESCRIPTION", "")
                    if "different contexts" in pattern_description.lower():
                        transfer_to_all = False
                    
                    if transfer_to_all:
                        # Transfer to parallel mode - creates isolated copies for each agent
                        PARALLEL_ISOLATION.transfer_to_parallel(current_history, len(PARALLEL_CONFIGS), agent_ids)
                    else:
                        # Only transfer to the first agent (P1)
                        PARALLEL_ISOLATION._parallel_mode = True
                        if current_history and agent_ids:
                            # Clear any existing histories first
                            PARALLEL_ISOLATION.clear_all_histories()
                            # Set history only for the first agent
                            PARALLEL_ISOLATION.replace_isolated_history(agent_ids[0], current_history.copy())
                            # Initialize empty histories for other agents
                            for agent_id in agent_ids[1:]:
                                PARALLEL_ISOLATION.replace_isolated_history(agent_id, [])
                else:
                    # Already have isolated histories, just ensure we're in parallel mode
                    PARALLEL_ISOLATION._parallel_mode = True
                
                for idx, config in enumerate(PARALLEL_CONFIGS, 1):
                    instance_key = (config.agent_name, idx)
                    if instance_key not in PARALLEL_AGENT_INSTANCES:
                        # Create instance for this config
                        base_agent = get_available_agents().get(config.agent_name.lower())
                        if base_agent:
                            agent_display_name = getattr(base_agent, "name", config.agent_name)
                            custom_name = f"{agent_display_name} #{idx}"
                            
                            # Determine model
                            model_to_use = config.model or os.getenv("CAI_MODEL", "alias1")
                            
                            # Create and store the instance
                            # No shared_message_history - each agent gets its own isolated copy
                            instance_agent = get_agent_by_name(
                                config.agent_name, custom_name=custom_name, model_override=model_to_use,
                                agent_id=config.id
                            )
                            PARALLEL_AGENT_INSTANCES[instance_key] = instance_agent

                # Build conversation history context before parallel execution
                # Each agent will get its own isolated history to prevent mixing
                

                async def run_agent_instance(
                    config: ParallelConfig, input_text: str
                ):
                    """Run a single agent instance with its own configuration."""
                    instance_agent = None
                    agent_id = None
                    try:
                        # Get instance number based on position in PARALLEL_CONFIGS
                        # Use all PARALLEL_CONFIGS to ensure consistent numbering
                        instance_number = PARALLEL_CONFIGS.index(config) + 1
                        agent_id = config.id or f"P{instance_number}"
                        
                        # Get the existing instance from PARALLEL_AGENT_INSTANCES
                        instance_key = (config.agent_name, instance_number)
                        instance_agent = PARALLEL_AGENT_INSTANCES.get(instance_key)
                        
                        
                        if not instance_agent:
                            # Fallback: create instance if not found (shouldn't happen normally)
                            from cai.agents import get_available_agents
                            from cai.agents.patterns import get_pattern
                            
                            # Check if this is a pattern
                            agent_display_name = None
                            actual_agent_name = config.agent_name
                            
                            if config.agent_name.endswith("_pattern"):
                                # This is a pattern, get the entry agent
                                pattern = get_pattern(config.agent_name)
                                if pattern and hasattr(pattern, 'entry_agent'):
                                    agent_display_name = getattr(pattern.entry_agent, "name", config.agent_name)
                                    # For patterns, we create the pattern itself, not individual agents
                                    actual_agent_name = config.agent_name
                            else:
                                base_agent = get_available_agents().get(config.agent_name.lower())
                                agent_display_name = base_agent.name if base_agent else config.agent_name
                            
                            # For display, we don't add instance number to pattern entry agents
                            # since they already have unique names like "Red team manager"
                            if not config.agent_name.endswith("_pattern"):
                                custom_name = f"{agent_display_name} #{instance_number}"
                            else:
                                custom_name = agent_display_name
                            
                            # Determine which model to use
                            model_to_use = config.model or os.getenv("CAI_MODEL", "alias1")
                            
                            # Create agent instance with the determined model
                            # Each agent gets its own isolated history from PARALLEL_ISOLATION
                            instance_agent = get_agent_by_name(
                                actual_agent_name, custom_name=custom_name, model_override=model_to_use,
                                agent_id=config.id
                            )
                            
                            # Store a strong reference to prevent garbage collection
                            PARALLEL_AGENT_INSTANCES[instance_key] = instance_agent
                        
                        # Register the agent with AGENT_MANAGER for parallel mode
                        # This ensures it shows up in /history
                        from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
                        agent_display_name = getattr(instance_agent, 'name', config.agent_name)
                        AGENT_MANAGER.set_parallel_agent(agent_id, instance_agent, agent_display_name)

                        # Ensure the model is properly set for the agent and all handoff agents
                        model_to_use = config.model or os.getenv("CAI_MODEL", "alias1")
                        if model_to_use:
                            update_agent_models_recursively(instance_agent, model_to_use)

                        # For parallel agents, the history is already loaded in the model instance
                        # Check if there's a custom prompt for this config
                        if config.prompt:
                            # Use the custom prompt instead of regular user input
                            instance_input = config.prompt
                        else:
                            # Just pass the user input as a string
                            instance_input = input_text
                        
                        # Run the agent with its own isolated context
                        result = await Runner.run(instance_agent, instance_input)
                        
                        # Clean up any streaming resources created by this agent's tools
                        try:
                            from cai.util import finish_tool_streaming, cli_print_tool_output, _LIVE_STREAMING_PANELS
                            
                            # In parallel mode, we need to update the final status of panels
                            if hasattr(cli_print_tool_output, "_streaming_sessions"):
                                agent_display_name = getattr(instance_agent, 'name', config.agent_name)
                                
                                # Find sessions belonging to this agent
                                for session_id, session_info in list(cli_print_tool_output._streaming_sessions.items()):
                                    if (session_info.get("agent_name") == agent_display_name and 
                                        not session_info.get("is_complete", False)):
                                        # Properly finish the streaming session
                                        finish_tool_streaming(
                                            tool_name=session_info.get("tool_name", "unknown"),
                                            args=session_info.get("args", {}),
                                            output=session_info.get("current_output", "Tool execution completed"),
                                            call_id=session_id,
                                            execution_info={
                                                "status": "completed",
                                                "is_final": True
                                            },
                                            token_info={
                                                "agent_name": agent_display_name,
                                                "agent_id": getattr(instance_agent.model, "agent_id", None) if hasattr(instance_agent, 'model') else None
                                            }
                                        )
                                        
                        except Exception:
                            # Silently ignore cleanup errors
                            pass
                        
                        # Save the agent's history after successful completion
                        if instance_agent and agent_id:
                            if hasattr(instance_agent, 'model') and hasattr(instance_agent.model, 'message_history'):
                                PARALLEL_ISOLATION.replace_isolated_history(agent_id, instance_agent.model.message_history)

                        return (config, result)
                    except asyncio.CancelledError:
                        # Task was cancelled (e.g., by Ctrl+C)
                        # Clean up any streaming resources before propagating cancellation
                        try:
                            from cai.util import cleanup_agent_streaming_resources
                            
                            # Clean up streaming sessions for this specific agent
                            if instance_agent:
                                agent_display_name = getattr(instance_agent, 'name', config.agent_name)
                                cleanup_agent_streaming_resources(agent_display_name)
                        except Exception:
                            pass
                            
                        # Save the agent's history before propagating the cancellation
                        if instance_agent and agent_id:
                            if hasattr(instance_agent, 'model') and hasattr(instance_agent.model, 'message_history'):
                                PARALLEL_ISOLATION.replace_isolated_history(agent_id, instance_agent.model.message_history)
                        raise
                    except Exception as e:
                        # Clean up any streaming resources before handling exception
                        try:
                            from cai.util import cleanup_agent_streaming_resources
                            
                            # Clean up streaming sessions for this specific agent
                            if instance_agent:
                                agent_display_name = getattr(instance_agent, 'name', config.agent_name)
                                cleanup_agent_streaming_resources(agent_display_name)
                        except Exception:
                            pass
                            
                        # Also save history on other exceptions
                        if instance_agent and agent_id:
                            if hasattr(instance_agent, 'model') and hasattr(instance_agent.model, 'message_history'):
                                PARALLEL_ISOLATION.replace_isolated_history(agent_id, instance_agent.model.message_history)
                        
                        # Log error details for debugging
                        logger = logging.getLogger(__name__)
                        error_details = f"Error in {config.agent_name}"
                        if config.model:
                            error_details += f" (model: {config.model})"
                        error_details += f": {str(e)}"
                        logger.error(error_details, exc_info=True)
                        
                        # Only show error in debug mode
                        if os.getenv("CAI_DEBUG", "1") == "2":
                            console.print(f"[bold red]{error_details}[/bold red]")
                        return (config, None)

                async def run_parallel_agents():
                    """Run all configured agents in parallel."""
                    # Create tasks for each agent with their own isolated contexts
                    # Note: If a config has a custom prompt, it will be used instead of user_input
                    tasks = []
                    for config in PARALLEL_CONFIGS:
                        # Determine what input to use for this config
                        input_for_config = config.prompt if config.prompt else user_input
                        tasks.append(run_agent_instance(config, input_for_config))

                    # Wait for all to complete
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Filter out exceptions and failed results
                    valid_results = []
                    for item in results:
                        if isinstance(item, tuple) and len(item) == 2 and item[1] is not None:
                            valid_results.append(item)

                    return valid_results

                # Run in asyncio event loop
                try:
                    results = asyncio.run(run_parallel_agents())
                except KeyboardInterrupt:
                    # When interrupted during parallel execution, ensure all agent histories are saved
                    # Force save all parallel agent histories to PARALLEL_ISOLATION
                    for idx, config in enumerate(PARALLEL_CONFIGS, 1):
                        instance_key = (config.agent_name, idx)
                        if instance_key in PARALLEL_AGENT_INSTANCES:
                            instance_agent = PARALLEL_AGENT_INSTANCES[instance_key]
                            if hasattr(instance_agent, 'model') and hasattr(instance_agent.model, 'message_history'):
                                agent_id = config.id or f"P{idx}"
                                # Force update the isolated history
                                PARALLEL_ISOLATION.replace_isolated_history(agent_id, instance_agent.model.message_history)
                                
                                # Also sync with AGENT_MANAGER for display
                                from cai.agents import get_available_agents
                                available_agents = get_available_agents()
                                if config.agent_name in available_agents:
                                    agent = available_agents[config.agent_name]
                                    agent_display_name = getattr(agent, "name", config.agent_name)
                                    
                                    # Add instance number if needed
                                    total_count = sum(1 for c in PARALLEL_CONFIGS if c.agent_name == config.agent_name)
                                    if total_count > 1:
                                        instance_num = 0
                                        for c in PARALLEL_CONFIGS:
                                            if c.agent_name == config.agent_name:
                                                instance_num += 1
                                                if c.id == config.id:
                                                    break
                                        agent_display_name = f"{agent_display_name} #{instance_num}"
                                    
                                    # Clear and replace the history in AGENT_MANAGER
                                    AGENT_MANAGER.clear_history(agent_display_name)
                                    for msg in instance_agent.model.message_history:
                                        AGENT_MANAGER.add_to_history(agent_display_name, msg)
                    
                    # Re-raise to trigger the main KeyboardInterrupt handler
                    raise
                    
                turn_count += 1
                stop_active_timer()
                start_idle_timer()
                continue

            # Handle special commands
            if user_input.startswith("/") or user_input.startswith("$"):
                # Remove newlines from pasted input
                cleaned_input = user_input.strip().replace('\n', '').replace('\r', '')

                try:
                    # Parse with shell-like quoting support
                    parts = shlex.split(cleaned_input)
                except ValueError:
                    # Fallback to simple split on error
                    parts = cleaned_input.split()

                if not parts:
                    continue

                command = parts[0]
                args = parts[1:] if len(parts) > 1 else None

                # Process the command with the handler
                if commands_handle_command(command, args):
                    continue  # Command was handled, continue to next iteration

                # If command wasn't recognized, show error (skip for /shell or /s)
                if command not in ("/shell", "/s"):
                    console.print(f"[red]Command failed or unknown: {command}[/red]")
                continue
            from rich.text import Text

            log_text = Text(
                f"Log file: {session_logger.filename}",
                style="yellow on black",
            )
            console.print(log_text)

            # Build conversation context from previous turns to give the
            # model short-term memory. We only keep messages that have plain
            # text content and ignore tool call entries to prevent schema
            # mismatches when converting to OpenAI chat format.
            history_context = []
            # Use the agent's model's message history directly instead of AGENT_MANAGER
            # This ensures compaction actually clears the history
            if hasattr(agent, 'model') and hasattr(agent.model, 'message_history'):
                for msg in agent.model.message_history:
                    role = msg.get("role")
                    content = msg.get("content")
                    tool_calls = msg.get("tool_calls")

                    if role == "user":
                        history_context.append({"role": "user", "content": content or ""})
                    elif role == "system":
                        history_context.append({"role": "system", "content": content or ""})
                    elif role == "assistant":
                        if tool_calls:
                            history_context.append(
                                {
                                    "role": "assistant",
                                    "content": content,  # Can be None
                                    "tool_calls": tool_calls,
                                }
                            )
                        elif content is not None:
                            history_context.append({"role": "assistant", "content": content})
                        elif (
                            content is None and not tool_calls
                        ):  # Explicitly handle empty assistant message
                            history_context.append({"role": "assistant", "content": None})
                    elif role == "tool":
                        history_context.append(
                            {
                                "role": "tool",
                                "tool_call_id": msg.get("tool_call_id"),
                                "content": msg.get("content"),  # Tool output
                            }
                        )

            # Fix message list structure BEFORE sending to the model to prevent errors
            try:
                from cai.util import fix_message_list

                history_context = fix_message_list(history_context)
            except Exception:
                pass

            # Append the current user input as the last message in the list.
            conversation_input: list | str
            if history_context:
                history_context.append({"role": "user", "content": user_input})
                conversation_input = history_context
            else:
                conversation_input = messages_ctf + user_input

            # Process the conversation with the agent - with parallel execution if enabled
            if parallel_count > 1:
                # Parallel execution mode (always non-streaming)
                async def run_agent_instance(instance_number, conversation_context):
                    """Run a single agent instance with its own complete context"""
                    try:
                        # Create a fresh agent instance with unique name to ensure complete isolation
                        from cai.agents import get_available_agents

                        base_agent = get_available_agents().get(last_agent_type.lower())
                        agent_display_name = base_agent.name if base_agent else last_agent_type
                        custom_name = f"{agent_display_name} #{instance_number + 1}"
                        instance_agent = get_agent_by_name(last_agent_type, custom_name=custom_name, agent_id=f"P{instance_number + 1}")

                        # Configure agent instance to match main agent settings
                        if hasattr(instance_agent, "model") and hasattr(agent, "model"):
                            if hasattr(instance_agent.model, "model") and hasattr(
                                agent.model, "model"
                            ):
                                # Check for instance-specific model override first
                                instance_specific_model = os.getenv(
                                    f"CAI_{last_agent_type.upper()}_{instance_number + 1}_MODEL"
                                )

                                if instance_specific_model:
                                    # Use instance-specific model (e.g., CAI_BUG_BOUNTER_1_MODEL)
                                    model_to_use = instance_specific_model
                                else:
                                    # Check for agent-specific model override
                                    agent_specific_model = os.getenv(
                                        f"CAI_{last_agent_type.upper()}_MODEL"
                                    )
                                    model_to_use = (
                                        agent_specific_model
                                        if agent_specific_model
                                        else agent.model.model
                                    )

                                update_agent_models_recursively(instance_agent, model_to_use)

                        # Use the full conversation context including history
                        instance_input = conversation_context

                        # Run the agent with its own isolated context
                        result = await Runner.run(instance_agent, instance_input)

                        return (instance_number, result)
                    except Exception as e:
                        # Log error for debugging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error in instance {instance_number}: {str(e)}", exc_info=True)
                        
                        # Only show error in debug mode
                        if os.getenv("CAI_DEBUG", "1") == "2":
                            console.print(
                                f"[bold red]Error in instance {instance_number}: {str(e)}[/bold red]"
                            )
                        return (instance_number, None)

                async def process_parallel_responses():
                    """Process multiple parallel agent executions"""
                    # Create tasks for each instance
                    tasks = [
                        run_agent_instance(i, conversation_input) for i in range(parallel_count)
                    ]

                    # Wait for all to complete, no matter if some fail
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Filter out exceptions and failed results
                    valid_results = []
                    for result in results:
                        if isinstance(result, tuple) and len(result) == 2:
                            idx, res = result
                            if res is not None and not isinstance(res, Exception):
                                valid_results.append((idx, res))

                    return valid_results

                # Execute all parallel instances
                results = asyncio.run(process_parallel_responses())

                # Print summary info about the results

                # Display the results
                for idx, result in results:
                    if result and hasattr(result, "final_output") and result.final_output:
                        # Add to main message history for context
                        agent.model.add_to_message_history(
                            {"role": "assistant", "content": f"{result.final_output}"}
                        )
            else:
                # Disable streaming by default, unless specifically enabled
                cai_stream = os.getenv("CAI_STREAM", "false")
                # Handle empty string or None values
                if not cai_stream or cai_stream.strip() == "":
                    cai_stream = "false"
                stream = cai_stream.lower() == "true"

                # Single agent execution (original behavior)
                if stream:

                    async def process_streamed_response(agent, conversation_input):
                        tool_calls_seen = {}  # Track tool calls by their ID
                        tool_results_seen = set()  # Track tool results by call_id
                        result = None
                        stream_iterator = None
                        
                        try:
                            result = Runner.run_streamed(agent, conversation_input)
                            stream_iterator = result.stream_events()

                            # Consume events so the async generator is executed.
                            async for event in stream_iterator:
                                if isinstance(event, RunItemStreamEvent):
                                    if event.name == "tool_called":
                                        # Track tool calls that were issued
                                        if hasattr(event.item, 'raw_item'):
                                            # For ToolCallItem, raw_item is a ResponseFunctionToolCall (or similar)
                                            # which has a direct call_id attribute
                                            call_id = getattr(event.item.raw_item, 'call_id', None)
                                            if call_id:
                                                tool_calls_seen[call_id] = event.item
                                    elif event.name == "tool_output":
                                        # Ensure item is a ToolCallOutputItem before accessing attributes
                                        if isinstance(event.item, ToolCallOutputItem):
                                            call_id = event.item.raw_item["call_id"]
                                            tool_results_seen.add(call_id)
                                            tool_msg = {
                                                "role": "tool",
                                                "tool_call_id": call_id,
                                                "content": event.item.output,
                                            }
                                            agent.model.add_to_message_history(tool_msg)

                            return result
                        except (KeyboardInterrupt, asyncio.CancelledError) as e:
                            # Handle interruption specifically
                            
                            # Clean up the async generator
                            if stream_iterator is not None:
                                try:
                                    await stream_iterator.aclose()
                                except Exception:
                                    pass
                            
                            # Clean up the result object if it has cleanup methods
                            if result is not None and hasattr(result, '_cleanup_tasks'):
                                try:
                                    result._cleanup_tasks()
                                except Exception:
                                    pass
                            
                            # Add synthetic results for any tool calls that don't have results
                            try:
                                for call_id, tool_item in tool_calls_seen.items():
                                    if call_id not in tool_results_seen:
                                        # This tool was called but no result was received
                                        synthetic_msg = {
                                            "role": "tool",
                                            "tool_call_id": call_id,
                                            "content": "Tool execution interrupted"
                                        }
                                        agent.model.add_to_message_history(synthetic_msg)
                            except Exception as cleanup_error:
                                # Silently ignore cleanup errors during interrupt
                                pass
                            
                            raise e
                        except Exception as e:
                            # Clean up on any other exception
                            if stream_iterator is not None:
                                try:
                                    await stream_iterator.aclose()
                                except Exception:
                                    pass
                                    
                            if result is not None and hasattr(result, '_cleanup_tasks'):
                                try:
                                    result._cleanup_tasks()
                                except Exception:
                                    pass
                                    
                            # Log error for debugging
                            logger = logging.getLogger(__name__)
                            logger.error(f"Error occurred during streaming: {str(e)}", exc_info=True)
                            
                            # Only show error details in debug mode
                            if os.getenv("CAI_DEBUG", "1") == "2":
                                import traceback
                                tb = traceback.format_exc()
                                print(f"\n[Error occurred during streaming: {str(e)}]\nLocation: {tb}")
                            return None

                    try:
                        asyncio.run(process_streamed_response(agent, conversation_input))
                    except OutputGuardrailTripwireTriggered as e:
                        # Display a user-friendly warning instead of crashing (streaming mode)
                        guardrail_name = e.guardrail_result.guardrail.get_name()
                        reason = e.guardrail_result.output.output_info.get("reason", "Security policy violation")
                        
                        # Use red color for the warning message
                        print(f"\n\033[91m🛡️  SECURITY GUARDRAIL TRIGGERED\033[0m")
                        print(f"\033[91mGuardrail: {guardrail_name}\033[0m")
                        print(f"\033[91mReason: {reason}\033[0m")
                        print(f"\033[93mThe agent's output was blocked for security reasons.\033[0m")
                        print(f"\033[96mYou can continue the conversation with a different request.\033[0m\n")
                        
                        # Continue the conversation loop instead of crashing
                        continue
                    except KeyboardInterrupt:
                        # This will catch the re-raised KeyboardInterrupt from process_streamed_response
                        # The cleanup will happen in the outer try-except block
                        raise
                    except RuntimeError as e:
                        # Handle event loop issues gracefully
                        if "This event loop is already running" in str(e) or "Cannot close a running event loop" in str(e):
                            # Try to recover by creating a new event loop
                            import sys
                            if sys.platform.startswith('win'):
                                # Windows specific event loop policy
                                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                            else:
                                # Unix/Linux/Mac
                                asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
                            
                            # Create a fresh event loop
                            new_loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(new_loop)
                            try:
                                new_loop.run_until_complete(process_streamed_response(agent, conversation_input))
                            except OutputGuardrailTripwireTriggered as e:
                                # Display a user-friendly warning instead of crashing (new event loop)
                                guardrail_name = e.guardrail_result.guardrail.get_name()
                                reason = e.guardrail_result.output.output_info.get("reason", "Security policy violation")
                                
                                # Use red color for the warning message
                                print(f"\n\033[91m🛡️  SECURITY GUARDRAIL TRIGGERED\033[0m")
                                print(f"\033[91mGuardrail: {guardrail_name}\033[0m")
                                print(f"\033[91mReason: {reason}\033[0m")
                                print(f"\033[93mThe agent's output was blocked for security reasons.\033[0m")
                                print(f"\033[96mYou can continue the conversation with a different request.\033[0m\n")
                                
                                # Close the loop and continue the conversation loop
                                new_loop.close()
                                continue
                            finally:
                                if not new_loop.is_closed():
                                    new_loop.close()
                        else:
                            raise
                else:
                    # Use non-streamed response
                    try:
                        response = asyncio.run(Runner.run(agent, conversation_input))
                    except InputGuardrailTripwireTriggered as e:
                        # Display a user-friendly warning for input guardrails
                        reason = "Potential security threat detected in input"
                        if hasattr(e, 'guardrail_result') and e.guardrail_result:
                            if hasattr(e.guardrail_result, 'output') and e.guardrail_result.output:
                                reason = e.guardrail_result.output.output_info.get("reason", reason)
                        
                        # Use red color for the warning message
                        print(f"\n\033[91m🛡️  INPUT SECURITY GUARDRAIL TRIGGERED\033[0m")
                        print(f"\033[91mReason: {reason}\033[0m")
                        print(f"\033[93mYour input was blocked for security reasons.\033[0m")
                        
                        # Check if this is likely due to conversation history
                        if "base64" in reason.lower() or "pattern" in reason.lower():
                            print(f"\n\033[96mThis may be due to malicious content in the conversation history.\033[0m")
                            print(f"\033[96mOptions:\033[0m")
                            print(f"  1. Type \033[92m/clear\033[0m to clear the conversation history")
                            print(f"  2. Type \033[92m/config set 26 false\033[0m to temporarily disable guardrails")
                            print(f"  3. Type \033[92m/exit\033[0m to exit CAI")
                        else:
                            print(f"\033[96mPlease rephrase your request or try a different approach.\033[0m\n")
                        
                        # Continue the conversation loop instead of crashing
                        continue
                    except OutputGuardrailTripwireTriggered as e:
                        # Display a user-friendly warning instead of crashing
                        guardrail_name = e.guardrail_result.guardrail.get_name()
                        reason = e.guardrail_result.output.output_info.get("reason", "Security policy violation")
                        
                        # Use red color for the warning message
                        print(f"\n\033[91m🛡️  SECURITY GUARDRAIL TRIGGERED\033[0m")
                        print(f"\033[91mGuardrail: {guardrail_name}\033[0m")
                        print(f"\033[91mReason: {reason}\033[0m")
                        print(f"\033[93mThe agent's output was blocked for security reasons.\033[0m")
                        print(f"\033[96mYou can continue the conversation with a different request.\033[0m\n")
                        
                        # Continue the conversation loop instead of crashing
                        continue

                    # En modo no-streaming, procesamos SOLO los tool outputs de response.new_items
                    # Los tool calls (assistant messages) ya se añaden correctamente en openai_chatcompletions.py
                    for item in response.new_items:
                        # Handle ONLY tool call output items (tool results)
                        if isinstance(item, ToolCallOutputItem):
                            tool_call_id = item.raw_item["call_id"]

                            # Verificar si ya existe este tool output en message_history para evitar duplicación
                            tool_msg_exists = any(
                                msg.get("role") == "tool"
                                and msg.get("tool_call_id") == tool_call_id
                                for msg in agent.model.message_history
                            )

                            if not tool_msg_exists:
                                # Añadir solo el tool output al message_history
                                tool_msg = {
                                    "role": "tool",
                                    "tool_call_id": tool_call_id,
                                    "content": item.output,
                                }
                                agent.model.add_to_message_history(tool_msg)

                # Final validation to ensure message history follows OpenAI's requirements
                # Ensure every tool message has a preceding assistant message with matching tool_call_id
                from cai.util import fix_message_list

                agent.model.message_history[:] = fix_message_list(agent.model.message_history)
            turn_count += 1

            # Stop measuring active time and start measuring idle time again
            stop_active_timer()
            start_idle_timer()

        except KeyboardInterrupt:
            # Print newline to ensure clean prompt display after interrupt
            print()

            # Clean up any active streaming panels
            try:
                from cai.util import cleanup_all_streaming_resources
                cleanup_all_streaming_resources()
            except Exception:
                pass

            # Handle pending tool calls to prevent errors on next iteration
            try:
                # Look for orphaned tool calls in the message history
                orphaned_tool_calls = []
                for msg in agent.model.message_history:
                    if msg.get("role") == "assistant" and msg.get("tool_calls"):
                        for tool_call in msg["tool_calls"]:
                            call_id = tool_call.get("id")
                            if call_id:
                                # Check if this tool call has a corresponding tool result
                                has_result = any(
                                    m.get("role") == "tool" and m.get("tool_call_id") == call_id
                                    for m in agent.model.message_history
                                )
                                if not has_result:
                                    orphaned_tool_calls.append((call_id, tool_call))

                # Add synthetic tool results for orphaned tool calls
                if orphaned_tool_calls:
                    for call_id, tool_call in orphaned_tool_calls:
                        tool_response_msg = {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": "Tool execution interrupted"
                        }
                        agent.model.add_to_message_history(tool_response_msg)

                    # Apply message list fixes to ensure consistency
                    from cai.util import fix_message_list

                    agent.model.message_history[:] = fix_message_list(agent.model.message_history)
                    
            except Exception as cleanup_error:
                pass

            # Add a small delay to allow the system to settle after interruption
            import time
            time.sleep(0.1)
            
            # Clear any asyncio event loop state to ensure clean restart
            try:
                # Get the current event loop if it exists
                loop = asyncio.get_event_loop()
                if loop and loop.is_running():
                    # Can't close a running loop, but we can clear pending tasks
                    pending = asyncio.all_tasks(loop) if hasattr(asyncio, 'all_tasks') else asyncio.Task.all_tasks(loop)
                    for task in pending:
                        task.cancel()
            except Exception:
                pass
            
            # Reset the event loop policy to ensure fresh loops
            try:
                asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
            except Exception:
                pass
        except Exception as e:
            import sys
            import traceback

            # Only show detailed errors in debug mode
            if os.getenv("CAI_DEBUG", "1") == "2":
                exc_type, exc_value, exc_traceback = sys.exc_info()
                tb_info = traceback.extract_tb(exc_traceback)
                filename, line, func, text = tb_info[-1]
                console.print(f"[bold red]Error: {str(e)}[/bold red]")
                console.print(f"[bold red]Traceback: {tb_info}[/bold red]")
            else:
                # In normal mode, just log the error
                logger = logging.getLogger(__name__)
                logger.error(f"Error in main loop: {str(e)}", exc_info=True)

            # Make sure we switch back to idle mode even if there's an error
            stop_active_timer()
            start_idle_timer()


def create_last_log_symlink(log_filename):
    """
    Create a symbolic link 'logs/last' pointing to the current log file.

    Args:
        log_filename: Path to the current log file
    """
    try:
        from pathlib import Path

        if not log_filename:
            return

        log_path = Path(log_filename)
        if not log_path.exists():
            return

        # Create the symlink path
        symlink_path = Path("logs/last")

        # Remove existing symlink if it exists
        if symlink_path.exists() or symlink_path.is_symlink():
            symlink_path.unlink()

        # Create new symlink pointing to just the filename (relative path within logs dir)
        symlink_path.symlink_to(log_path.name)

    except Exception:
        # Silently ignore errors to avoid disrupting the main flow
        pass


def main():
    # Apply litellm patch to fix the __annotations__ error
    patch_applied = fix_litellm_transcription_annotations()
    if not patch_applied:
        print(
            color(
                "Something went wrong patching LiteLLM fix_litellm_transcription_annotations",
                color="red",
            )
        )

    # Check for command-line arguments to use as initial prompt
    initial_prompt = None
    if len(sys.argv) > 1:
        initial_prompt = sys.argv[1]

    # Get agent type from environment variables or use default
    agent_type = os.getenv("CAI_AGENT_TYPE", "one_tool_agent")

    # Get the agent instance by name with default ID P1
    agent = get_agent_by_name(agent_type, agent_id="P1")
    
    # Use the switch_to_single_agent method for proper initialization
    from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
    # IMPORTANT: Always use the agent's proper name, not the agent key
    agent_name = agent.name if hasattr(agent, "name") else agent_type
    AGENT_MANAGER.switch_to_single_agent(agent, agent_name)

    # Configure model flags to work well with CLI
    if hasattr(agent, "model"):
        # Disable rich streaming in the model to avoid conflicts
        if hasattr(agent.model, "disable_rich_streaming"):
            agent.model.disable_rich_streaming = True
        # Allow final output to ensure all agent messages are shown
        if hasattr(agent.model, "suppress_final_output"):
            agent.model.suppress_final_output = False  # Changed to False to show all agent messages

    # Ensure the agent and all its handoff agents use the current model
    current_model = os.getenv("CAI_MODEL", "alias1")
    update_agent_models_recursively(agent, current_model)

    # Run the CLI with the selected agent and optional initial prompt
    run_cai_cli(agent, initial_prompt=initial_prompt)


if __name__ == "__main__":
    main()
