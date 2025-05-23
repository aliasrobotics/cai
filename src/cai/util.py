"""
Util model for CAI
"""
import os
import sys
import subprocess
import importlib.resources
import pathlib
import json
from rich.console import Console
from rich.tree import Tree
from mako.template import Template  # pylint: disable=import-error
from wasabi import color
from rich.text import Text  # pylint: disable=import-error
from rich.panel import Panel  # pylint: disable=import-error
from rich.box import ROUNDED  # pylint: disable=import-error
from rich.theme import Theme  # pylint: disable=import-error
from rich.traceback import install  # pylint: disable=import-error
from rich.pretty import install as install_pretty  # pylint: disable=import-error # noqa: 501
from datetime import datetime
import atexit
from dataclasses import dataclass, field
from typing import Dict, Optional
import time
import threading
from rich.syntax import Syntax  # Import Syntax for highlighting
from rich.panel import Panel
from rich.console import Group
from rich.box import ROUNDED
from rich.table import Table
import re
import uuid
from cai import is_pentestperf_available
if is_pentestperf_available():
    import pentestperf as ptt 

# Global timing variables for tracking active and idle time
_active_timer_start = None
_active_time_total = 0.0
_idle_timer_start = None
_idle_time_total = 0.0
_timing_lock = threading.Lock()

# Set up a global tracker for live streaming panels
_LIVE_STREAMING_PANELS = {}

# ======================== CLAUDE THINKING STREAMING FUNCTIONS ========================

# Global tracker for Claude thinking streaming panels
_CLAUDE_THINKING_PANELS = {}

def start_active_timer():
    """
    Start measuring active time (when LLM is processing or tool is executing).
    Pauses the idle timer if it's running.
    """
    global _active_timer_start, _idle_timer_start, _idle_time_total
    
    with _timing_lock:
        # If idle timer is running, pause it and accumulate time
        if _idle_timer_start is not None:
            idle_duration = time.time() - _idle_timer_start
            _idle_time_total += idle_duration
            _idle_timer_start = None
            
        # Start active timer if not already running
        if _active_timer_start is None:
            _active_timer_start = time.time()

def stop_active_timer():
    """
    Stop measuring active time and accumulate the total.
    Restarts the idle timer.
    """
    global _active_timer_start, _active_time_total, _idle_timer_start
    
    with _timing_lock:
        # If active timer is running, pause it and accumulate time
        if _active_timer_start is not None:
            active_duration = time.time() - _active_timer_start
            _active_time_total += active_duration
            _active_timer_start = None
            
        # Start idle timer if not already running
        if _idle_timer_start is None:
            _idle_timer_start = time.time()

def start_idle_timer():
    """
    Start measuring idle time (when waiting for user input).
    Pauses the active timer if it's running.
    """
    global _idle_timer_start, _active_timer_start, _active_time_total
    
    with _timing_lock:
        # If active timer is running, pause it and accumulate time
        if _active_timer_start is not None:
            active_duration = time.time() - _active_timer_start
            _active_time_total += active_duration
            _active_timer_start = None
            
        # Start idle timer if not already running
        if _idle_timer_start is None:
            _idle_timer_start = time.time()

def stop_idle_timer():
    """
    Stop measuring idle time and accumulate the total.
    Restarts the active timer.
    """
    global _idle_timer_start, _idle_time_total, _active_timer_start
    
    with _timing_lock:
        # If idle timer is running, pause it and accumulate time
        if _idle_timer_start is not None:
            idle_duration = time.time() - _idle_timer_start
            _idle_time_total += idle_duration
            _idle_timer_start = None
            
        # Start active timer if not already running
        if _active_timer_start is None:
            _active_timer_start = time.time()

def get_active_time():
    """
    Get the total active time (LLM processing, tool execution).
    Returns a formatted string like "1h 30m 45s" or "45s" or "5m 30s".
    """
    global _active_time_total, _active_timer_start
    
    with _timing_lock:
        # Calculate total active time including current active period if running
        total_active_seconds = _active_time_total
        if _active_timer_start is not None:
            current_active_duration = time.time() - _active_timer_start
            total_active_seconds += current_active_duration
    
    # Format the time string
    hours, remainder = divmod(int(total_active_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def get_idle_time():
    """
    Get the total idle time (waiting for user input).
    Returns a formatted string like "1h 30m 45s" or "45s" or "5m 30s".
    """
    global _idle_time_total, _idle_timer_start
    
    with _timing_lock:
        # Calculate total idle time including current idle period if running
        total_idle_seconds = _idle_time_total
        if _idle_timer_start is not None:
            current_idle_duration = time.time() - _idle_timer_start
            total_idle_seconds += current_idle_duration
    
    # Format the time string
    hours, remainder = divmod(int(total_idle_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def get_active_time_seconds():
    """
    Get the total active time in seconds for precise measurement.
    Returns a float representing the total number of seconds.
    """
    global _active_time_total, _active_timer_start
    
    with _timing_lock:
        # Calculate total active time including current active period if running
        total_active_seconds = _active_time_total
        if _active_timer_start is not None:
            current_active_duration = time.time() - _active_timer_start
            total_active_seconds += current_active_duration
    
    return total_active_seconds

def get_idle_time_seconds():
    """
    Get the total idle time in seconds for precise measurement.
    Returns a float representing the total number of seconds.
    """
    global _idle_time_total, _idle_timer_start
    
    with _timing_lock:
        # Calculate total idle time including current idle period if running
        total_idle_seconds = _idle_time_total
        if _idle_timer_start is not None:
            current_idle_duration = time.time() - _idle_timer_start
            total_idle_seconds += current_idle_duration
    
    return total_idle_seconds

# Initialize idle timer at module load - system starts in idle state
start_idle_timer()

# Instead of direct import
try:
    from cai.cli import START_TIME
except ImportError:
    START_TIME = None

# Shared stats tracking object to maintain consistent costs across calls
@dataclass
class CostTracker:
    # Session-level stats
    session_total_cost: float = 0.0
    
    # Current agent stats
    current_agent_total_cost: float = 0.0
    current_agent_input_tokens: int = 0
    current_agent_output_tokens: int = 0
    current_agent_reasoning_tokens: int = 0
    
    # Current interaction stats
    interaction_input_tokens: int = 0
    interaction_output_tokens: int = 0
    interaction_reasoning_tokens: int = 0
    interaction_cost: float = 0.0
    
    # Calculation cache
    model_pricing_cache: Dict[str, tuple] = field(default_factory=dict)
    calculated_costs_cache: Dict[str, float] = field(default_factory=dict)
    
    # Track the last calculation to debug inconsistencies
    last_interaction_cost: float = 0.0
    last_total_cost: float = 0.0

    def check_price_limit(self, new_cost: float) -> None:
        """Check if adding the new cost would exceed the price limit."""
        from cai.sdk.agents.exceptions import PriceLimitExceeded
        import os
        price_limit_env = os.getenv("CAI_PRICE_LIMIT")
        try:
            price_limit = float(price_limit_env) if price_limit_env is not None else float("inf")
        except ValueError:
            price_limit = float("inf")

        if price_limit != float("inf"):
            total_cost = self.session_total_cost + new_cost
            if total_cost > price_limit:
                raise PriceLimitExceeded(total_cost, price_limit)
    
    def update_session_cost(self, new_cost: float) -> None:
        """Add cost to session total and log the update"""
        # Check price limit before updating
        self.check_price_limit(new_cost)
        
        old_total = self.session_total_cost
        self.session_total_cost += new_cost
        
    def add_interaction_cost(self, new_cost: float) -> None:
        """
        Add an interaction cost to the session total and check price limit.
        This is a convenience method that combines check_price_limit and update_session_cost.
        """
        # Skip updating costs if the cost is zero (common with local models)
        if new_cost <= 0:
            self.last_interaction_cost = 0.0
            return
            
        # Check price limit first
        self.check_price_limit(new_cost)
        
        # Then update the session cost
        self.session_total_cost += new_cost
        
        # Update the last interaction cost for tracking
        self.last_interaction_cost = new_cost
        
    def reset_cost_for_local_model(self, model_name: str) -> bool:
        """
        Reset interaction cost tracking when switching to a local model.
        Returns True if the model was identified as local and cost was reset.
        """
        # Check if this is a local/free model
        model_str = model_name.lower()
        is_local_model = (
            "ollama" in model_str or
            "qwen" in model_str or
            "llama" in model_str or
            "mistral" in model_str or
            ":" in model_str or
            (os.getenv('OLLAMA') is not None and os.getenv('OLLAMA').lower() != 'false')
        ) and "alias" not in model_str
        
        if is_local_model:
            # Reset the current interaction costs but keep total session costs
            self.interaction_cost = 0.0
            self.last_interaction_cost = 0.0
            # Don't reset session_total_cost as that includes previous paid models
            return True
            
        return False
        
    def log_final_cost(self) -> None:
        """Display final cost information at exit"""
        # Skip displaying cost if already shown in the session summary
        if os.environ.get("CAI_COST_DISPLAYED", "").lower() == "true":
            return
        print(f"\nTotal CAI Session Cost: ${self.session_total_cost:.6f}")

    def get_model_pricing(self, model_name: str) -> tuple:
        """Get and cache pricing information for a model"""
        # Use the centralized function to standardize model names
        model_name = get_model_name(model_name)
        
        # Check if using Ollama or local model
        model_str = model_name.lower()
        is_local_model = (
            "ollama" in model_str or
            "qwen" in model_str or
            "llama" in model_str or
            "mistral" in model_str or
            ":" in model_str or  # Ollama uses formats like qwen2.5:7b
            (os.getenv('OLLAMA') is not None and os.getenv('OLLAMA').lower() != 'false')
        ) and "alias" not in model_str
        
        # For local models, always return zero cost
        if is_local_model:
            # Set and cache zero cost for local models
            free_pricing = (0.0, 0.0)
            self.model_pricing_cache[model_name] = free_pricing
            return free_pricing
        
        # Check cache for non-local models
        if model_name in self.model_pricing_cache:
            return self.model_pricing_cache[model_name]

        # Try to load pricing from local pricing.json first
        try:
            pricing_path = pathlib.Path("pricing.json")
            if pricing_path.exists():
                with open(pricing_path, "r", encoding="utf-8") as f:
                    local_pricing = json.load(f)
                    pricing_info = local_pricing.get("alias0", {})
                    input_cost = pricing_info.get("input_cost_per_token", 0)
                    output_cost = pricing_info.get("output_cost_per_token", 0)
                    
                    # Cache and return local pricing
                    self.model_pricing_cache[model_name] = (input_cost, output_cost)
                    return input_cost, output_cost
        except Exception as e:
            print(f"  WARNING: Error loading local pricing.json: {str(e)}")
        
        # Fallback to LiteLLM API if local pricing not found
        LITELLM_URL = (
            "https://raw.githubusercontent.com/BerriAI/litellm/main/"
            "model_prices_and_context_window.json"
        )
        
        try:
            import requests
            response = requests.get(LITELLM_URL, timeout=2)
            if response.status_code == 200:
                model_pricing_data = response.json()
                
                # Get pricing info for the model
                pricing_info = model_pricing_data.get(model_name, {})
                input_cost_per_token = pricing_info.get("input_cost_per_token", 0)
                output_cost_per_token = pricing_info.get("output_cost_per_token", 0)
                
                # Cache the results
                self.model_pricing_cache[model_name] = (input_cost_per_token, output_cost_per_token)
                return input_cost_per_token, output_cost_per_token
        except Exception as e:
            print(f"  WARNING: Error fetching model pricing: {str(e)}")
        
        # Default values if no pricing found
        default_pricing = (0, 0)
        self.model_pricing_cache[model_name] = default_pricing
        return default_pricing
    
    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int, 
                       label: Optional[str] = None, force_calculation: bool = False) -> float:
        """Calculate and cache cost for a given model and token counts"""
        # Standardize model name using the central function
        model_name = get_model_name(model)
        
        # Check if this is a local model (always free) first
        model_str = model_name.lower()
        is_local_model = (
            "ollama" in model_str or
            "qwen" in model_str or
            "llama" in model_str or
            "mistral" in model_str or
            ":" in model_str or
            (os.getenv('OLLAMA') is not None and os.getenv('OLLAMA').lower() != 'false')
        ) and "alias" not in model_str
        
        # For local models, always return zero cost
        if is_local_model:
            return 0.0
        
        # Generate a cache key
        cache_key = f"{model_name}_{input_tokens}_{output_tokens}"
        
        # Return cached result if available (unless force_calculation is True)
        if cache_key in self.calculated_costs_cache and not force_calculation:
            return self.calculated_costs_cache[cache_key]
        
        # Get pricing information
        input_cost_per_token, output_cost_per_token = self.get_model_pricing(model_name)
        
        # Calculate costs - use high precision for calculations
        input_cost = input_tokens * input_cost_per_token
        output_cost = output_tokens * output_cost_per_token
        total_cost = input_cost + output_cost

        # Cache the result with full precision
        self.calculated_costs_cache[cache_key] = total_cost
        
        return total_cost
    
    def process_interaction_cost(self, model: str, 
                                input_tokens: int, 
                                output_tokens: int, 
                                reasoning_tokens: int = 0,
                                provided_cost: Optional[float] = None) -> float:
        """Process and track costs for a new interaction"""
        # Standardize model name
        model_name = get_model_name(model)
        
        # Update token counts
        self.interaction_input_tokens = input_tokens
        self.interaction_output_tokens = output_tokens
        self.interaction_reasoning_tokens = reasoning_tokens
        
        # Use provided cost or calculate
        if provided_cost is not None and provided_cost > 0:
            self.interaction_cost = float(provided_cost)
        else:
            self.interaction_cost = self.calculate_cost(
                model_name, input_tokens, output_tokens, 
                label="OFFICIAL CALCULATION: Interaction")
        
        self.last_interaction_cost = self.interaction_cost
        
        return self.interaction_cost
    
    def process_total_cost(self, model: str, 
                          total_input_tokens: int, 
                          total_output_tokens: int,
                          total_reasoning_tokens: int = 0,
                          provided_cost: Optional[float] = None) -> float:
        """Process and track costs for total (cumulative) usage"""
        # Standardize model name
        model_name = get_model_name(model)
        
        # Update token counts
        self.current_agent_input_tokens = total_input_tokens
        self.current_agent_output_tokens = total_output_tokens
        self.current_agent_reasoning_tokens = total_reasoning_tokens
        
        # Get previous total and add current interaction cost
        previous_total = self.current_agent_total_cost
        
        # Add the new interaction cost
        if provided_cost is not None and provided_cost > 0:
            # If a total cost is explicitly provided, use it
            new_total_cost = float(provided_cost)
            # Calculate how much was added in this interaction
            cost_diff = new_total_cost - previous_total
        else:
            # Simply add the current interaction cost to the previous total
            cost_diff = self.interaction_cost
            new_total_cost = previous_total + cost_diff
        
        # Only add to session total if there's genuinely new cost (and it's positive)
        if cost_diff > 0:
            self.update_session_cost(cost_diff)
        
        # Update the current agent's total cost
        self.current_agent_total_cost = new_total_cost
        
        # Track the last total for debugging
        self.last_total_cost = new_total_cost
        
        return new_total_cost

# Initialize the global cost tracker
COST_TRACKER = CostTracker()

# Register exit handler for final cost display
atexit.register(COST_TRACKER.log_final_cost)
theme = Theme({
    "timestamp": "#00BCD4",
    "agent": "#4CAF50",
    "arrow": "#FFFFFF",
    "content": "#ECEFF1",
    "tool": "#F44336",

    "cost": "#009688",
    "args_str": "#FFC107",

    "border": "#2196F3",
    "border_state": "#FFD700",
    "model": "#673AB7",
    "dim": "#9E9E9E",
    "current_token_count": "#E0E0E0",
    "total_token_count": "#757575",
    "context_tokens": "#0A0A0A",

    "success": "#4CAF50",
    "warning": "#FF9800",
    "error": "#F44336"
})

console = Console(theme=theme)
install()
install_pretty()


def get_ollama_api_base():
    """Get the Ollama API base URL from environment variable or default to localhost:8000."""
    return os.environ.get("OLLAMA_API_BASE", "http://localhost:8000/v1")

def load_prompt_template(template_path):
    """
    Load a prompt template from the package resources.
    
    Args:
        template_path: Path to the template file relative to the cai package,
                      e.g., "prompts/system_bug_bounter.md"
    
    Returns:
        The rendered template as a string
    """
    try:
        # Get the template file from package resources
        template_path_parts = template_path.split('/')
        package_path = ['cai'] + template_path_parts[:-1]
        package = '.'.join(package_path)
        filename = template_path_parts[-1]
        
        # Read the content from the package resources
        # Handle different importlib.resources APIs between Python versions
        try:
            # Python 3.9+ API
            template_content = importlib.resources.read_text(package, filename)
        except (TypeError, AttributeError):
            # Fallback for Python 3.8 and earlier
            with importlib.resources.path(package, filename) as path:
                template_content = pathlib.Path(path).read_text(encoding='utf-8')
        
        # Render the template
        return Template(template_content).render()
    except Exception as e:
        raise ValueError(f"Failed to load template '{template_path}': {str(e)}")

# Start of Selection
def visualize_agent_graph(start_agent):
    """
    Visualize agent graph showing all bidirectional connections between agents.
    Uses Rich library for pretty printing.
    """
    console = Console()
    if start_agent is None:
        console.print("[red]No agent provided to visualize.[/red]")
        return

    tree = Tree(f"🤖 {start_agent.name} (Current Agent)", guide_style="bold blue")

    visited = set()
    agent_nodes = {}
    agent_positions = {}
    position_counter = 0

    def add_agent_node(agent, parent=None, is_transfer=False):
        """Add an agent node and track for cross-connections."""
        nonlocal position_counter
        if agent is None:
            return None
        aid = id(agent)
        if aid in visited:
            if is_transfer and parent:
                original_pos = agent_positions.get(aid)
                parent.add(f"[cyan]↩ Return to {agent.name} (Agent #{original_pos})[/cyan]")
            return agent_nodes.get(aid)

        visited.add(aid)
        position_counter += 1
        agent_positions[aid] = position_counter

        if is_transfer and parent:
            node = parent
        elif parent:
            node = parent.add(f"[green]{agent.name} (#{position_counter})[/green]")
        else:
            node = tree
        agent_nodes[aid] = node

        # Add tools
        tools_node = node.add("[yellow]Tools[/yellow]")
        for tool in getattr(agent, "tools", []):
            tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", "")
            tools_node.add(f"[blue]{tool_name}[/blue]")

        # Add handoffs
        transfers_node = node.add("[magenta]Handoffs[/magenta]")
        
        # First, handle old-style handoffs through handoffs list
        for handoff_fn in getattr(agent, "handoffs", []):
            if callable(handoff_fn) and not hasattr(handoff_fn, "agent_name"): 
                try:
                    next_agent = handoff_fn()
                    if next_agent:
                        transfer_node = transfers_node.add(f"🤖 {next_agent.name}")
                        add_agent_node(next_agent, transfer_node, True)
                except Exception:
                    continue
            elif hasattr(handoff_fn, "agent_name"):
                # Handle SDK handoff objects
                try:
                    handoff_name = handoff_fn.agent_name
                    # Find the actual agent instance if available
                    next_agent = None
                    
                    # Try to find the agent by name in the global namespace
                    # This is a heuristic and might not always work
                    import sys
                    for module_name, module in sys.modules.items():
                        if module_name.startswith('cai.agents'):
                            agent_var_name = handoff_name.lower().replace(' ', '_') + '_agent'
                            if hasattr(module, agent_var_name):
                                next_agent = getattr(module, agent_var_name)
                                break
                    
                    if next_agent:
                        transfer_node = transfers_node.add(
                            f"🤖 {handoff_name} via {handoff_fn.tool_name}")
                        add_agent_node(next_agent, transfer_node, True)
                    else:
                        # If we can't find the agent, just show the name
                        transfers_node.add(
                            f"[yellow]🤖 {handoff_name} via {handoff_fn.tool_name}[/yellow]")
                except Exception as e:
                    transfers_node.add(f"[red]Error: {str(e)}[/red]")
            elif isinstance(handoff_fn, dict) and "agent_name" in handoff_fn:
                # Handle dictionary handoff objects
                handoff_name = handoff_fn["agent_name"]
                tool_name = handoff_fn.get("tool_name", f"transfer_to_{handoff_name}")
                transfers_node.add(f"[yellow]🤖 {handoff_name} via {tool_name}[/yellow]")

        return node

    # Start traversal from the root agent
    add_agent_node(start_agent)
    console.print(tree)

def fix_litellm_transcription_annotations():
    """
    Apply a monkey patch to fix the TranscriptionCreateParams.__annotations__ issue in LiteLLM.
    
    This is a temporary fix until the issue is fixed in the LiteLLM library itself.
    """
    try:
        import litellm.litellm_core_utils.model_param_helper as model_param_helper
        
        # Override the problematic method to avoid the error
        original_get_transcription_kwargs = model_param_helper.ModelParamHelper._get_litellm_supported_transcription_kwargs
        
        def safe_get_transcription_kwargs():
            """A safer version that doesn't rely on __annotations__."""
            return set(["file", "model", "language", "prompt", "response_format", 
                       "temperature", "api_base", "api_key", "api_version", 
                       "timeout", "custom_llm_provider"])
        
        # Apply the monkey patch
        model_param_helper.ModelParamHelper._get_litellm_supported_transcription_kwargs = safe_get_transcription_kwargs        
        return True
    except (ImportError, AttributeError):
        # If the import fails or the attribute doesn't exist, the patch couldn't be applied
        return False

def fix_message_list(messages):  # pylint: disable=R0914,R0915,R0912
    """
    Sanitizes the message list passed as a parameter to align with the
    OpenAI API message format.

    Adjusts the message list to comply with the following rules:
        1. A tool call id appears no more than twice.
        2. Each tool call id appears as a pair, and both messages
            must have content.
        3. If a tool call id appears alone (without a pair), it is removed.
        4. There cannot be empty messages.
        5. Each tool_use block (assistant with tool_calls) must be followed by
           a tool_result block (tool message with matching tool_call_id).
        6. Each 'tool' message must be immediately preceded by an 'assistant' message
           with matching tool_call_id in its tool_calls.

    Args:
        messages (List[dict]): List of message dictionaries containing
                            role, content, and optionally tool_calls or
                            tool_call_id fields.

    Returns:
        List[dict]: Sanitized list of messages with invalid tool calls
                   and empty messages removed.
    """
    # Deep-copy to ensure we don't modify the input
    sanitized_messages = []
    
    # First pass - identify tool_call_ids from assistant messages and tool messages
    tool_call_map = {}  # Map from tool_call_id to (assistant_idx, tool_idx)
    
    for i, msg in enumerate(messages):
        # Skip empty messages (considered empty if 'content' is None or only whitespace)
        if msg.get("role") in ["user", "system"] and (msg.get("content") is None or not str(msg.get("content", "")).strip()):
            # Special case: if it's a system message, set content to empty string instead of skipping
            if msg.get("role") == "system":
                # Replace None with empty string
                msg["content"] = ""
                sanitized_messages.append(msg)
            # Skip empty user messages entirely
            continue
            
        # Add valid messages to our sanitized list first
        sanitized_messages.append(msg)
        
        # Now track tool calls and tool messages for pairing 
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                if tc.get("id"):
                    tool_id = tc.get("id")
                    if tool_id not in tool_call_map:
                        tool_call_map[tool_id] = {"assistant_idx": len(sanitized_messages) - 1, "tool_idx": None}
        
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            tool_id = msg.get("tool_call_id")
            if tool_id in tool_call_map:
                tool_call_map[tool_id]["tool_idx"] = len(sanitized_messages) - 1
            else:
                # Tool response without a matching tool call - create a synthetic pair
                # by adding a dummy assistant message with a tool_call
                assistant_msg = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tool_id,
                        "type": "function",
                        "function": {
                            "name": "unknown_function",
                            "arguments": "{}"
                        }
                    }]
                }
                # Insert the assistant message *before* the tool message
                sanitized_messages.insert(len(sanitized_messages) - 1, assistant_msg)
                # Update mapping
                tool_call_map[tool_id] = {"assistant_idx": len(sanitized_messages) - 2, "tool_idx": len(sanitized_messages) - 1}
    
    # Second pass - ensure correct sequence (tool messages must directly follow their assistant messages)
    # This fixes the error "messages with role 'tool' must be a response to a preceeding message with 'tool_calls'"
    i = 0
    while i < len(sanitized_messages):
        msg = sanitized_messages[i]
        
        # Check if this is a tool message that might be out of sequence
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            tool_id = msg.get("tool_call_id")
            
            # If this isn't the first message, check if the previous message is a matching assistant message
            if i > 0:
                prev_msg = sanitized_messages[i-1]
                
                # Check if the previous message is an assistant message with matching tool_call_id
                is_valid_sequence = (
                    prev_msg.get("role") == "assistant" and 
                    prev_msg.get("tool_calls") and 
                    any(tc.get("id") == tool_id for tc in prev_msg.get("tool_calls", []))
                )
                
                if not is_valid_sequence:
                    # Find the assistant message with this tool_call_id
                    assistant_idx = None
                    for j, assistant_msg in enumerate(sanitized_messages):
                        if (assistant_msg.get("role") == "assistant" and 
                            assistant_msg.get("tool_calls") and
                            any(tc.get("id") == tool_id for tc in assistant_msg.get("tool_calls", []))):
                            assistant_idx = j
                            break
                    
                    # If we found a matching assistant message, move this tool message right after it
                    if assistant_idx is not None:
                        # Remember to save the tool message
                        tool_msg = sanitized_messages.pop(i)
                        
                        # Insert right after the assistant message
                        sanitized_messages.insert(assistant_idx + 1, tool_msg)
                        
                        # Adjust i to account for the move
                        if assistant_idx < i:
                            # We moved the message backward, so i should point to the next message
                            # which is now at position i (since we removed a message before it)
                            continue
                        else:
                            # We moved the message forward, so i should now point to the message
                            # that is now at position i
                            continue
                    else:
                        # No matching assistant message found - create one
                        assistant_msg = {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": tool_id,
                                "type": "function",
                                "function": {
                                    "name": "unknown_function",
                                    "arguments": "{}"
                                }
                            }]
                        }
                        
                        # Insert the assistant message before the tool message
                        sanitized_messages.insert(i, assistant_msg)
                        
                        # Skip past both messages
                        i += 2
                        continue
            else:
                # This tool message is at index 0, which means there's no preceding assistant message
                # Create a dummy assistant message
                assistant_msg = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tool_id,
                        "type": "function",
                        "function": {
                            "name": "unknown_function",
                            "arguments": "{}"
                        }
                    }]
                }
                
                # Insert the assistant message before the tool message
                sanitized_messages.insert(0, assistant_msg)
                
                # Skip past both messages
                i += 2
                continue
        
        # Move to the next message
        i += 1
    
    # Final validation - ensure all tool calls have responses
    for tool_id, indices in list(tool_call_map.items()):
        if indices["tool_idx"] is None:
            # Tool call without a response - create a synthetic tool message
            assistant_idx = indices["assistant_idx"]
            assistant_msg = sanitized_messages[assistant_idx]
            
            # Find the relevant tool call
            tool_name = "unknown_function"
            for tc in assistant_msg["tool_calls"]:
                if tc.get("id") == tool_id:
                    if tc.get("function") and tc["function"].get("name"):
                        tool_name = tc["function"]["name"]
                    break
            
            # Create an automatic tool response message
            tool_msg = {
                "role": "tool",
                "tool_call_id": tool_id,
                "content": f"Auto-generated response for {tool_name}"
            }
            
            # Insert immediately after the assistant message
            if assistant_idx + 1 < len(sanitized_messages):
                # Insert at the position after assistant
                sanitized_messages.insert(assistant_idx + 1, tool_msg)
            else:
                # Just append if we're at the end
                sanitized_messages.append(tool_msg)
            
            # Update the map to note that this tool call now has a response
            tool_call_map[tool_id]["tool_idx"] = assistant_idx + 1
    
    # Ensure messages have non-null content (required by some providers)
    for msg in sanitized_messages:
        if msg.get("role") != "tool" and msg.get("content") is None and not msg.get("tool_calls"):
            msg["content"] = ""
            
        # For tool messages, ensure content is never null
        if msg.get("role") == "tool" and msg.get("content") is None:
            msg["content"] = f"Tool response for {msg.get('tool_call_id', 'unknown')}"
    
    # Special case for Claude: ensure strict alternating pattern between assistant tool_calls and tool results
    # If multiple consecutive assistant messages with tool_calls exist, interleave them with tool responses
    i = 0
    while i < len(sanitized_messages) - 1:
        current_msg = sanitized_messages[i]
        next_msg = sanitized_messages[i + 1]
        
        # When current message is assistant with tool_calls and next message is NOT a tool response
        if (current_msg.get("role") == "assistant" and 
            current_msg.get("tool_calls") and 
            (next_msg.get("role") != "tool" or not next_msg.get("tool_call_id"))):
            
            # Get the first tool call ID
            tool_id = current_msg["tool_calls"][0].get("id", "unknown")
            tool_name = "unknown_function"
            if current_msg["tool_calls"][0].get("function"):
                tool_name = current_msg["tool_calls"][0]["function"].get("name", "unknown_function")
            
            # Create a tool result message
            tool_msg = {
                "role": "tool",
                "tool_call_id": tool_id,
                "content": f"Auto-generated response for {tool_name}"
            }
            
            # Insert the tool message after the current assistant message
            sanitized_messages.insert(i + 1, tool_msg)
            
            # Skip over the newly inserted message
            i += 2
        else:
            i += 1
    return sanitized_messages

def cli_print_tool_call(tool_name="", args="", output="", prefix="  "):
    """Print a tool call with pretty formatting"""
    if not tool_name:
        return

    print(f"{prefix}{color('Tool Call:', fg='cyan')}")
    print(f"{prefix}{color('Name:', fg='cyan')} {tool_name}")
    if args:
        print(f"{prefix}{color('Args:', fg='cyan')} {args}")
    if output:
        print(f"{prefix}{color('Output:', fg='cyan')} {output}")

def get_model_input_tokens(model):
    """
    Get the number of input tokens for
    max context window capacity for a given model.
    """
    model_tokens = {
        "gpt": 128000,
        "o1": 200000,
        "claude": 200000,
        "qwen2.5": 32000,  # https://ollama.com/library/qwen2.5, 128K input, 8K output  # noqa: E501  # pylint: disable=C0301
        "llama3.1": 32000,  # https://ollama.com/library/llama3.1, 128K input  # noqa: E501  # pylint: disable=C0301
        "deepseek": 128000  # https://api-docs.deepseek.com/quick_start/pricing  # noqa: E501  # pylint: disable=C0301
    }
    for model_type, tokens in model_tokens.items():
        if model_type in model:
            return tokens
    return model_tokens["gpt"]

def get_model_name(model):
    """
    Extract a string model name from various model inputs.
    Centralizes model name standardization to avoid inconsistencies (e.g. avoid passing model object instead of string name).
    Args:
        model: String model name or model object
        
    Returns:
        str: Standardized model name string
    """
    if isinstance(model, str):
        return model
    # If not a string, use environment variable
    return os.environ.get('CAI_MODEL', 'qwen2.5:72b')

# Helper function to format time in a human-readable way
def format_time(seconds):
    if seconds is None:
        return "N/A"
    
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        seconds_remainder = seconds % 60
        return f"{minutes}m {seconds_remainder:.1f}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"

def get_model_pricing(model_name):
    """
    Get pricing information for a model, using the CostTracker's implementation.
    This is a global helper that delegates to the CostTracker instance.
    
    Args:
        model_name: String name of the model
        
    Returns:
        tuple: (input_cost_per_token, output_cost_per_token)
    """
    # Standardize model name
    model_name = get_model_name(model_name)
    
    # Use the CostTracker's implementation to maintain consistency and use its cache
    return COST_TRACKER.get_model_pricing(model_name)

def calculate_model_cost(model, input_tokens, output_tokens):
    """
    Calculate the cost for a given model based on token usage.
    
    Args:
        model: The model name or object
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens used
        
    Returns:
        float: The calculated cost in dollars
    """
    # Use the CostTracker to handle duplicates
    return COST_TRACKER.calculate_cost(
        model, 
        input_tokens, 
        output_tokens,
        label="COST CALCULATION",
        force_calculation=False  # Let it use the cache for duplicates
    )

def _create_token_display(
    interaction_input_tokens,
    interaction_output_tokens,
    interaction_reasoning_tokens,
    total_input_tokens,
    total_output_tokens,
    total_reasoning_tokens,
    model,
    interaction_cost=None,
    total_cost=None
) -> Text:
    # Standardize model name
    model_name = get_model_name(model)
    
    # Process interaction cost
    current_cost = COST_TRACKER.process_interaction_cost(
        model_name, 
        interaction_input_tokens, 
        interaction_output_tokens,
        interaction_reasoning_tokens,
        interaction_cost
    )
    
    # Process total cost 
    total_cost_value = COST_TRACKER.process_total_cost(
        model_name,
        total_input_tokens,
        total_output_tokens,
        total_reasoning_tokens,
        total_cost
    )
    
    # Create display text
    tokens_text = Text(justify="left")
    tokens_text.append(" ", style="bold")
    
    # Current interaction tokens
    tokens_text.append("Current: ", style="bold")
    tokens_text.append(f"I:{interaction_input_tokens} ", style="green")
    tokens_text.append(f"O:{interaction_output_tokens} ", style="red")
    tokens_text.append(f"R:{interaction_reasoning_tokens} ", style="yellow")
    tokens_text.append(f"(${current_cost:.4f}) ", style="bold")
    
    # Separator
    tokens_text.append("| ", style="dim")
    
    # Total tokens for this agent run
    tokens_text.append("Total: ", style="bold")
    tokens_text.append(f"I:{total_input_tokens} ", style="green")
    tokens_text.append(f"O:{total_output_tokens} ", style="red")
    tokens_text.append(f"R:{total_reasoning_tokens} ", style="yellow")
    tokens_text.append(f"(${total_cost_value:.4f}) ", style="bold")
    
    # Separator
    tokens_text.append("| ", style="dim")
    
    # Session total across all agents
    tokens_text.append("Session: ", style="bold magenta")
    tokens_text.append(f"${COST_TRACKER.session_total_cost:.4f}", style="bold magenta")
    
    # Context usage
    tokens_text.append(" | ", style="dim")
    context_pct = interaction_input_tokens / get_model_input_tokens(model_name) * 100
    tokens_text.append("Context: ", style="bold")
    tokens_text.append(f"{context_pct:.1f}% ", style="bold")
    
    # Context indicator
    if context_pct < 50:
        indicator = "🟩"
        color_local = "green"
    elif context_pct < 80:
        indicator = "🟨"
        color_local = "yellow"
    else:
        indicator = "🟥"
        color_local = "red"
    
    tokens_text.append(f"{indicator}", style=color_local)

    return tokens_text

def parse_message_content(message):
    """
    Parse a message object to extract its textual content.
    Only processes messages that don't have tool calls.
    Detects markdown code blocks and applies syntax highlighting in non-streaming mode.
    Also formats other markdown elements like headers, lists, and text formatting.
    
    Args:
        message: Can be a string or a Message object with content attribute
        
    Returns:
        str or rich.console.Group: The extracted content as a string or as a rich Group with Syntax highlighting
    """
    from rich.console import Group
    from rich.syntax import Syntax
    from rich.text import Text
    from rich.markdown import Markdown
    import re
    
    # Extract the raw content
    raw_content = ""
    
    # If message is already a string, use it
    if isinstance(message, str):
        raw_content = message
    # If message is a Message object with content attribute
    elif hasattr(message, 'content') and message.content is not None:
        raw_content = message.content
    # If message is a dict with content key
    elif isinstance(message, dict) and 'content' in message:
        raw_content = message['content']
    # If we can't extract content, convert to string
    else:
        raw_content = str(message)

    # Check if streaming is enabled
    streaming_enabled = os.getenv('CAI_STREAM', 'false').lower() == 'true'
    
    # Only apply markdown formatting in non-streaming mode
    if not streaming_enabled and raw_content:
        # Check if content contains markdown code blocks with improved regex
        code_block_pattern = r'```(\w*)\s*([\s\S]*?)\s*```'
        matches = re.findall(code_block_pattern, raw_content, re.DOTALL)
        
        if matches:
            # Prepare to process markdown with code blocks highlighted
            elements = []
            last_end = 0
            
            # Find all code blocks with improved regex pattern
            for match in re.finditer(r'```(\w*)\s*([\s\S]*?)\s*```', raw_content, re.DOTALL):
                # Get text before the code block
                start = match.start()
                if start > last_end:
                    text_before = raw_content[last_end:start]
                    
                    # Process markdown in the text before the code block
                    if text_before.strip():
                        md = Markdown(text_before)
                        elements.append(md)
                
                # Process the code block
                lang = match.group(1) or "text"
                code = match.group(2)
                
                # Use the language mapping helper to get proper syntax highlighting
                syntax_lang = get_language_from_code_block(lang)
                
                # Create syntax highlighted code
                syntax = Syntax(
                    code,
                    syntax_lang,
                    theme="monokai",
                    line_numbers=True,
                    word_wrap=True,
                    background_color="#272822"
                )
                elements.append(syntax)
                
                last_end = match.end()
            
            # Add any remaining text after the last code block
            if last_end < len(raw_content):
                text_after = raw_content[last_end:]
                
                # Process markdown in the text after the code block
                if text_after.strip():
                    md = Markdown(text_after)
                    elements.append(md)
            
            return Group(*elements)
        else:
            # If no code blocks, but still contains markdown, use Rich's markdown renderer
            # Check for markdown elements (headers, lists, formatting)
            has_markdown = any([
                # Headers
                re.search(r'^#{1,6}\s+\w+', raw_content, re.MULTILINE),
                # Lists
                re.search(r'^\s*[-*+]\s+\w+', raw_content, re.MULTILINE),
                re.search(r'^\s*\d+\.\s+\w+', raw_content, re.MULTILINE),
                # Bold/Italic
                '**' in raw_content,
                '*' in raw_content and not '**' in raw_content,
                '__' in raw_content,
                '_' in raw_content and not '__' in raw_content,
                # Links
                re.search(r'\[.+?\]\(.+?\)', raw_content)
            ])
            
            if has_markdown:
                return Group(Markdown(raw_content))
    
    # For streaming mode or no markdown, return the raw content
    return raw_content

def parse_message_tool_call(message, tool_output=None):
    """
    Parse a message object to extract its content and tool calls.
    Displays tool calls in the format: tool_name({"command":"","args":"","ctf":{},"async_mode":false,"session_id":""}) 
    and shows the tool output in a separated panel.
    
    Args:
        message: A Message object or dict with content and tool_calls attributes
        tool_output: String containing the output from the tool execution
        
    Returns:
        tuple: (content, tool_panels) where content is the message text and
               tool_panels is a list of panels representing tool calls and outputs
    """
    content = ""
    tool_panels = []
    
    # Extract the content text (LLM's inference)
    if isinstance(message, str):
        content = message
    elif hasattr(message, 'content') and message.content is not None:
        content = message.content
    elif isinstance(message, dict) and 'content' in message:
        content = message['content']
    
    # Extract tool calls
    tool_calls = None
    if hasattr(message, 'tool_calls') and message.tool_calls:
        tool_calls = message.tool_calls
    elif isinstance(message, dict) and 'tool_calls' in message and message['tool_calls']:
        tool_calls = message['tool_calls']
    
    # Process tool calls if they exist
    if tool_calls:
        from rich.panel import Panel
        from rich.text import Text
        from rich.box import ROUNDED
        from rich.console import Group
        
        for tool_call in tool_calls:
            # Extract tool name and arguments
            tool_name = None
            args_dict = {}
            call_id = None
            
            # Handle different formats of tool_call objects
            if hasattr(tool_call, 'function'):
                if hasattr(tool_call.function, 'name'):
                    tool_name = tool_call.function.name
                if hasattr(tool_call.function, 'arguments'):
                    try:
                        import json
                        args_dict = json.loads(tool_call.function.arguments)
                    except:
                        args_dict = {"raw_arguments": tool_call.function.arguments}
            elif isinstance(tool_call, dict):
                if 'function' in tool_call:
                    if 'name' in tool_call['function']:
                        tool_name = tool_call['function']['name']
                    if 'arguments' in tool_call['function']:
                        try:
                            import json
                            args_dict = json.loads(tool_call['function']['arguments'])
                        except:
                            args_dict = {"raw_arguments": tool_call['function']['arguments']}
            
            # Create a panel for this tool call if name is not None
            # NOTE: Tool execution panel will be handled in cli_print_tool_output
            # Pass on tool info to generate panels for display in cli_print_agent_messages
            if tool_name and tool_output:
                # Create content for the panel - just showing the output, not the tool call
                panel_content = []
                
                # Add tool output to the panel
                output_text = Text()
                output_text.append("Output:", style="bold #C0C0C0")  # Silver/gray
                output_text.append(f"\n{tool_output}", style="#C0C0C0")  # Silver/gray
                
                panel_content.append(output_text)
                
                # Create a panel with just the output
                tool_panel = Panel(
                    Group(*panel_content),
                    border_style="blue",
                    box=ROUNDED,
                    padding=(1, 2),
                    title="[bold]Tool Output[/bold]",  # Changed title to indicate this is just output
                    title_align="left",
                    expand=True
                )
                
                tool_panels.append(tool_panel)
                
                # Store the call_id with tool name to help cli_print_tool_output avoid duplicates
                if not hasattr(parse_message_tool_call, '_processed_calls'):
                    parse_message_tool_call._processed_calls = set()
                
                call_key = call_id if call_id else f"{tool_name}:{args_dict}"
                parse_message_tool_call._processed_calls.add(call_key)
    
    return content, tool_panels

# Add this function to detect tool output panels
def is_tool_output_message(message):
    """Check if a message appears to be a tool output panel display message."""
    if isinstance(message, str):
        msg_lower = message.lower()
        return ("call id:" in msg_lower and "output:" in msg_lower) or msg_lower.startswith("tool output")
    return False

def cli_print_agent_messages(agent_name, message, counter, model, debug,  # pylint: disable=too-many-arguments,too-many-locals,unused-argument # noqa: E501
                             interaction_input_tokens=None,
                             interaction_output_tokens=None,
                             interaction_reasoning_tokens=None,
                             total_input_tokens=None,
                             total_output_tokens=None,
                             total_reasoning_tokens=None,
                             interaction_cost=None,
                             total_cost=None,
                             tool_output=None,  # New parameter for tool output
                             suppress_empty=False):  # New parameter to suppress empty panels
    """Print agent messages/thoughts with enhanced visual formatting."""
    # Debug prints to trace the function calls
    if debug:
        if isinstance(message, str):
            print(f"DEBUG cli_print_agent_messages: Received string message: {message[:50]}...")
        if tool_output:
            print(f"DEBUG cli_print_agent_messages: Received tool_output: {tool_output[:50]}...")
    
    # Use the model from environment variable if available
    model_override = os.getenv('CAI_MODEL')
    if model_override:
        model = model_override

    timestamp = datetime.now().strftime("%H:%M:%S")

    # Create header
    text = Text()
    
    # Check if the message has tool calls
    has_tool_calls = False
    if hasattr(message, 'tool_calls') and message.tool_calls:
        has_tool_calls = True
    elif isinstance(message, dict) and 'tool_calls' in message and message['tool_calls']:
        has_tool_calls = True
    
    # Parse the message based on whether it has tool calls
    if has_tool_calls:
        parsed_message, tool_panels = parse_message_tool_call(message, tool_output)
    else:
        parsed_message = parse_message_content(message)
        tool_panels = []
        
    # Skip empty panels - THIS IS THE KEY CHANGE
    # If suppress_empty is True and there's no parsed message and no tool panels, 
    # don't create an empty panel to avoid cluttering during streaming
    if suppress_empty and not parsed_message and not tool_panels:
        return
        
    # Check if parsed_message is empty or "null"
    is_empty_message = (parsed_message == "null" or parsed_message == "" or 
                       (isinstance(parsed_message, str) and not parsed_message.strip()))
        
    # Also skip if the only message is "null" or empty
    if is_empty_message:
        if suppress_empty and not tool_panels:
            return

    # Check if we have Group content from markdown parsing
    is_rich_content = False
    from rich.console import Group
    if isinstance(parsed_message, Group):
        is_rich_content = True

    # Special handling for Reasoner Agent
    if agent_name == "Reasoner Agent":
        text.append(f"[{counter}] ", style="bold red")
        text.append(f"Agent: {agent_name} ", style="bold yellow")
        if parsed_message and not is_rich_content:
            text.append(f">> {parsed_message} ", style="green")
        text.append(f"[{timestamp}", style="dim")
        if model:
            text.append(f" ({os.getenv('CAI_SUPPORT_MODEL')})",
                        style="bold blue")
        text.append("]", style="dim")
    elif is_empty_message: 
        # When parsed_message is empty, only include timestamp and model info
        text.append(f"Agent: {agent_name} ", style="bold green")
        text.append(f"[{timestamp}", style="dim")
        if model:
            text.append(f" ({model})", style="bold magenta")
        text.append("]", style="dim")
    else:
        text.append(f"[{counter}] ", style="bold cyan")
        text.append(f"Agent: {agent_name} ", style="bold green")
        if parsed_message and not is_rich_content:
            text.append(f">> {parsed_message} ", style="yellow")
        text.append(f"[{timestamp}", style="dim")
        if model:
            text.append(f" ({model})", style="bold magenta")
        text.append("]", style="dim")

    # Add token information with enhanced formatting
    tokens_text = None
    if (interaction_input_tokens is not None and  # pylint: disable=R0916
            interaction_output_tokens is not None and
            interaction_reasoning_tokens is not None and
            total_input_tokens is not None and
            total_output_tokens is not None and
            total_reasoning_tokens is not None):

        tokens_text = _create_token_display(
            interaction_input_tokens,
            interaction_output_tokens,
            interaction_reasoning_tokens,
            total_input_tokens,
            total_output_tokens,
            total_reasoning_tokens,
            model,
            interaction_cost,
            total_cost
        )
        # Only append token information if there is a parsed message
        if parsed_message and not is_rich_content:
            text.append(tokens_text)

    # Create the panel content based on whether we have rich content or not
    from rich.panel import Panel
    from rich.console import Group
    
    if is_rich_content:
        # For rich content, create a Group with the header, content, and tokens
        panel_content = []
        panel_content.append(text)
        
        # Add spacing between header and content for better readability
        panel_content.append(Text("\n"))
        
        # Add the Group with highlighted content
        panel_content.append(parsed_message)
        
        # Add token information at the bottom with proper spacing
        if tokens_text:
            panel_content.append(Text("\n"))
            panel_content.append(tokens_text)
        
        panel = Panel(
            Group(*panel_content),
            border_style="red" if agent_name == "Reasoner Agent" else "blue",
            box=ROUNDED,
            padding=(1, 1),  # Increased padding for better appearance
            title="",
            title_align="left"
        )
    else:
        # For regular text content, use the original panel format
        panel = Panel(
            text,
            border_style="red" if agent_name == "Reasoner Agent" else "blue",
            box=ROUNDED,
            padding=(0, 1),
            title="",
            title_align="left"
        )
    #console.print("\n")
    console.print(panel)
    
    # If there are tool panels, print them after the main message panel
    # But only in non-streaming mode to avoid duplicates
    if tool_panels:
        for tool_panel in tool_panels:
            console.print(tool_panel)

def create_agent_streaming_context(agent_name, counter, model):
    """
    Create a streaming context object that maintains state for streaming agent output.
    
    Args:
        agent_name: The name of the agent to display
        counter: The interaction counter (turn number)
        model: The model name
        
    Returns:
        A dictionary with the streaming context
    """
    # Add a static variable to track active streaming contexts and prevent duplicates
    if not hasattr(create_agent_streaming_context, "_active_streaming"):
        create_agent_streaming_context._active_streaming = {}
    
    # If there's already an active streaming context with the same counter, return it
    context_key = f"{agent_name}_{counter}"
    if context_key in create_agent_streaming_context._active_streaming:
        return create_agent_streaming_context._active_streaming[context_key]
    
    try:
        from rich.live import Live
        import shutil
        
        # Use the model from env if available
        model_override = os.getenv('CAI_MODEL')
        if model_override:
            model = model_override
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Terminal size for better display
        terminal_width, _ = shutil.get_terminal_size((100, 24))
        panel_width = min(terminal_width - 4, 120)  # Keep some margin
        
        # Create base header for the panel
        header = Text()
        header.append(f"[{counter}] ", style="bold cyan")
        header.append(f"Agent: {agent_name} ", style="bold green")
        header.append(f">> ", style="yellow")
        
        # Create the content area for streaming text
        content = Text("")
        
        # Add timestamp and model info
        footer = Text()
        footer.append(f"\n[{timestamp}", style="dim")
        if model:
            footer.append(f" ({model})", style="bold magenta")
        footer.append("]", style="dim")
        
        # Create the panel (initial state)
        panel = Panel(
            Text.assemble(header, content, footer),
            border_style="blue",
            box=ROUNDED,
            padding=(0, 1),  
            title="Stream",
            title_align="left",
            width=panel_width,
            expand=True 
        )
        
        # Create Live display object but don't start it until we have content
        live = Live(panel, refresh_per_second=10, console=console, auto_refresh=True, vertical_overflow="visible")
        
        context = {
            "live": live,
            "panel": panel,
            "header": header,
            "content": content,
            "footer": footer,
            "timestamp": timestamp,
            "model": model,
            "agent_name": agent_name,
            "panel_width": panel_width,
            "is_started": False,  # Track if we've started the display
            "error": None,  # Track any errors
        }
        
        # Store the context for potential reuse
        create_agent_streaming_context._active_streaming[context_key] = context
        
        return context
    except Exception as e:
        # If rich display fails, return None and log the error
        import sys
        print(f"Error creating streaming context: {e}", file=sys.stderr)
        return None

def update_agent_streaming_content(context, text_delta, token_stats=None):
    """
    Update the streaming content with new text.
    
    Args:
        context: The streaming context created by create_agent_streaming_context
        text_delta: The new text to add
        token_stats: Optional token statistics to show with each update
    """
    if not context:
        return False
        
    try:
        # Only parse and add text if we have actual content to add
        # Skip when text_delta is empty and we're just updating token stats
        if text_delta:
            # Parse the text_delta to get just the content if needed
            parsed_delta = parse_message_content(text_delta)
            
            # Skip empty updates to avoid showing an empty panel
            if not parsed_delta or parsed_delta.strip() == "":
                # Update token stats if provided
                if token_stats:
                    # Just update the footer, not the content
                    pass
            else:
                # Add the parsed text to the content
                context["content"].append(parsed_delta)
        # If no text_delta but we have token_stats, just update stats
        elif not token_stats:
            # No text and no stats - nothing to update
            return True
        
        # Update the footer with token stats if provided
        if token_stats:
            # Create token stats display
            from rich.text import Text
            footer_stats = Text()
            
            # Add timestamp and model info
            footer_stats.append(f"\n[{context['timestamp']}", style="dim")
            if context['model']:
                footer_stats.append(f" ({context['model']})", style="bold magenta")
            footer_stats.append("]", style="dim")
            
            # Add token stats
            input_tokens = token_stats.get('input_tokens', 0)
            output_tokens = token_stats.get('output_tokens', 0)
            interaction_cost = token_stats.get('cost', 0.0)
            
            # Get session total cost - either from token_stats or directly from COST_TRACKER
            session_total_cost = token_stats.get('total_cost', 0.0)
            if session_total_cost == 0.0 and hasattr(COST_TRACKER, 'session_total_cost'):
                session_total_cost = COST_TRACKER.session_total_cost
            
            if input_tokens > 0:
                footer_stats.append(" | ", style="dim")
                footer_stats.append(f"I:{input_tokens} O:{output_tokens}", style="green")
                
                # Show both interaction cost and total session cost
                if interaction_cost > 0:
                    footer_stats.append(f" (${interaction_cost:.4f})", style="bold cyan")
                
                # Add the total cost information on the same line
                footer_stats.append(" | Session: ", style="dim")
                footer_stats.append(f"${session_total_cost:.4f}", style="bold magenta")
                
                # Add context usage indicator
                model_name = context.get("model", os.environ.get('CAI_MODEL', 'qwen2.5:14b'))
                context_pct = input_tokens / get_model_input_tokens(model_name) * 100
                if context_pct < 50:
                    indicator = "🟩"
                    color = "green"
                elif context_pct < 80:
                    indicator = "🟨"
                    color = "yellow"
                else:
                    indicator = "🟥"
                    color = "red"
                footer_stats.append(f" {indicator} {context_pct:.1f}%", style=f"bold {color}")
            
            # Update the footer
            context["footer"] = footer_stats
        
        # Update the live display with the latest content
        updated_panel = Panel(
            Text.assemble(context["header"], context["content"], context["footer"]),
            border_style="blue",
            box=ROUNDED,
            padding=(0, 1), 
            title="Stream",
            title_align="left",
            width=context.get("panel_width", 100),
            expand=True
        )
        
        # Check if we need to start the display
        if not context.get("is_started", False):
            try:
                context["live"].start()
                context["is_started"] = True
            except Exception as e:
                context["error"] = str(e)
                return False
        
        # Force an update with the new panel
        context["live"].update(updated_panel)
        context["panel"] = updated_panel
        context["live"].refresh()
        return True
    except Exception as e:
        # If there's an error, set it in the context
        context["error"] = str(e)
        return False

def finish_agent_streaming(context, final_stats=None):
    """
    Finish the streaming session and display final stats if available.
    
    Args:
        context: The streaming context to finish
        final_stats: Optional dictionary with token statistics and costs
    """
    if not context:
        return False
    
    # Clean up tracking of this context
    if hasattr(create_agent_streaming_context, "_active_streaming"):
        for key, value in list(create_agent_streaming_context._active_streaming.items()):
            if value is context:
                del create_agent_streaming_context._active_streaming[key]
                break
        
    try:
        # Check if there's actual content to display - don't show empty panels
        if not context["content"] or context["content"].plain == "":
            # If the display was never started, nothing to do
            if not context.get("is_started", False):
                return True
            # Otherwise, stop the display without showing final panel
            try:
                context["live"].stop()
            except Exception:
                pass
            return True
        
        # If we have token stats, add them
        tokens_text = None
        if final_stats:
            interaction_input_tokens = final_stats.get("interaction_input_tokens")
            interaction_output_tokens = final_stats.get("interaction_output_tokens")
            interaction_reasoning_tokens = final_stats.get("interaction_reasoning_tokens")
            total_input_tokens = final_stats.get("total_input_tokens")
            total_output_tokens = final_stats.get("total_output_tokens")
            total_reasoning_tokens = final_stats.get("total_reasoning_tokens")
            
            # Ensure costs are properly extracted and preserved as floats
            interaction_cost = float(final_stats.get("interaction_cost", 0.0))
            total_cost = float(final_stats.get("total_cost", 0.0))
            
            model_name = context.get("model", "")
            # If model is not a string, use env
            if not isinstance(model_name, str):
                model_name = os.environ.get('CAI_MODEL', 'gpt-4o-mini')
            
            if (interaction_input_tokens is not None and
                    interaction_output_tokens is not None and
                    interaction_reasoning_tokens is not None and
                    total_input_tokens is not None and
                    total_output_tokens is not None and
                    total_reasoning_tokens is not None):
                
                # Only calculate costs if they weren't provided or are zero
                if interaction_cost is None or interaction_cost == 0.0:
                    interaction_cost = calculate_model_cost(model_name, interaction_input_tokens, interaction_output_tokens)
                if total_cost is None or total_cost == 0.0:
                    total_cost = calculate_model_cost(model_name, total_input_tokens, total_output_tokens)
                
                tokens_text = _create_token_display(
                    interaction_input_tokens,
                    interaction_output_tokens,
                    interaction_reasoning_tokens,
                    total_input_tokens,
                    total_output_tokens,
                    total_reasoning_tokens,
                    model_name,  # string model name!
                    interaction_cost,
                    total_cost
                )
                
                # Crear una línea de tokens compacta para el streaming
                compact_tokens = Text()
                compact_tokens.append(" | ", style="dim")
                compact_tokens.append(f"I:{interaction_input_tokens} O:{interaction_output_tokens} ", style="green")
                compact_tokens.append(f"(${interaction_cost:.4f}) ", style="bold cyan")
                
                # Include the total session cost
                session_total_cost = COST_TRACKER.session_total_cost if hasattr(COST_TRACKER, 'session_total_cost') else total_cost
                compact_tokens.append(" | Session: ", style="dim")
                compact_tokens.append(f"${session_total_cost:.4f}", style="bold magenta")
                
                # Añadir un indicador de uso de contexto
                context_pct = interaction_input_tokens / get_model_input_tokens(model_name) * 100
                if context_pct < 50:
                    indicator = "🟩"
                elif context_pct < 80:
                    indicator = "🟨"
                else:
                    indicator = "🟥"
                compact_tokens.append(f"{indicator} {context_pct:.1f}%", style="bold")
        
        # Add the compact token info to the footer
        if 'footer' in context and final_stats:
            # Clear the existing footer
            context['footer'] = Text()
            # Add timestamp and model
            context['footer'].append(f"\n[{context['timestamp']}", style="dim")
            if context['model']:
                context['footer'].append(f" ({context['model']})", style="bold magenta")
            context['footer'].append("]", style="dim")
            
            # Add the compact token info if available
            if final_stats and 'compact_tokens' in locals():
                context['footer'].append(compact_tokens)
        
        final_panel = Panel(
            Text.assemble(
                context["header"], 
                context["content"], 
                tokens_text if tokens_text else Text(""), 
                context["footer"]
            ),
            border_style="blue",
            box=ROUNDED,
            padding=(0, 1), 
            title="Stream",
            title_align="left",
            width=context.get("panel_width", 100),
            expand=True
        )
        
        # Update one last time
        context["live"].update(final_panel)
        
        # Ensure updates are displayed before stopping
        time.sleep(0.1)
        
        # Stop the live display
        try:
            context["live"].stop()
        except Exception as e:
            context["error"] = str(e)
            
        return True
    except Exception as e:
        # If there's an error, print it if the context hasn't already tracked one
        if not context.get("error"):
            context["error"] = str(e)
            
        # Try to stop the live display even if there was an error
        try:
            if context.get("is_started", False) and context.get("live"):
                context["live"].stop()
        except Exception:
            pass
            
        return False


def cli_print_tool_output(tool_name="", args="", output="", call_id=None, execution_info=None, token_info=None, streaming=False):
    """
    Print a tool call output to the command line.
    Similar to cli_print_tool_call but for the output of the tool.
    
    Args:
        tool_name: Name of the tool
        args: Arguments passed to the tool
        output: The output of the tool
        call_id: Optional call ID for streaming updates
        execution_info: Optional execution information
        token_info: Optional token information with keys:
            - interaction_input_tokens, interaction_output_tokens, interaction_reasoning_tokens
            - total_input_tokens, total_output_tokens, total_reasoning_tokens
            - model: model name string
            - interaction_cost, total_cost: optional cost values
        streaming: Flag indicating if this is part of a streaming output
    """
    import time
    # If it's an empty output, don't print anything except for streaming sessions
    if not output and not call_id and not streaming:
        return
    
    # Skip early for execute_code tool in non-streaming mode
    if tool_name == "execute_code" and not streaming:
        return
    
    # Set up global tracker for streaming sessions
    if not hasattr(cli_print_tool_output, '_streaming_sessions'):
        cli_print_tool_output._streaming_sessions = {}
    
    # Track seen call IDs to prevent duplicate panels for non-streaming outputs
    if not hasattr(cli_print_tool_output, '_seen_calls'):
        cli_print_tool_output._seen_calls = {}
        
    # Track all displayed commands to prevent duplicates with cleanup
    if not hasattr(cli_print_tool_output, '_displayed_commands'):
        cli_print_tool_output._displayed_commands = set()
        cli_print_tool_output._last_cleanup = time.time()
    
    # Periodic cleanup to prevent memory growth
    current_time = time.time()
    if current_time - cli_print_tool_output._last_cleanup > 300:  # Cleanup every 5 minutes
        # Clear the displayed commands set periodically
        cli_print_tool_output._displayed_commands.clear()
        cli_print_tool_output._last_cleanup = current_time
    
    # --- Consistent Command Key Generation ---
    effective_command_args_str = ""
    if isinstance(args, dict):
        # If args is a dictionary, extract the 'args' field.
        effective_command_args_str = args.get("args", "")
    elif isinstance(args, str):
        # If args is a string, it might be a JSON representation or a plain string.
        try:
            parsed_json_args = json.loads(args)
            if isinstance(parsed_json_args, dict):
                # Parsed as JSON dict, get the 'args' field.
                effective_command_args_str = parsed_json_args.get("args", "")
            else:
                # Parsed as JSON, but not a dict (e.g., a JSON string literal).
                effective_command_args_str = parsed_json_args if isinstance(parsed_json_args, str) else args
        except json.JSONDecodeError:
            # Not a JSON string, treat 'args' as a plain string.
            effective_command_args_str = args
    
    command_key = f"{tool_name}:{effective_command_args_str}"
    
    # If args contain a call_counter, append it to make the key unique
    # This allows commands with counters to always display
    if isinstance(args, dict) and "call_counter" in args:
        call_counter = args["call_counter"]
        command_key += f":counter_{call_counter}"
    
    # --- End of Command Key Generation ---
        
    # Check for duplicate display conditions
    if streaming:
        # For streaming updates, track and update the single streaming session
        if call_id:
            # If this is a new streaming session, record it
            if call_id not in cli_print_tool_output._streaming_sessions:
                cli_print_tool_output._streaming_sessions[call_id] = {
                    'tool_name': tool_name,
                    'args': args, # Store original args for display formatting
                    'buffer': output if output else "",
                    'start_time': time.time(),
                    'last_update': time.time(),
                    'command_key': command_key, # Store the generated key
                    'is_complete': False
                }
                # Add the command key to displayed commands
                if command_key not in cli_print_tool_output._displayed_commands:
                    cli_print_tool_output._displayed_commands.add(command_key)
            else:
                # Update the existing session
                session = cli_print_tool_output._streaming_sessions[call_id]
                # Always replace buffer with latest output for consistency
                session['buffer'] = output
                session['last_update'] = time.time()
                if execution_info and execution_info.get('is_final', False):
                    session['is_complete'] = True
                    
            # For streaming outputs, we'll use Rich Live panel if available
            try:
                from rich.console import Console
                from rich.live import Live
                from rich.panel import Panel
                from rich.text import Text
                from rich.box import ROUNDED
                
                # Access the global live panel dictionary
                global _LIVE_STREAMING_PANELS
                
                # Create the header, content, and panel
                # Pass the original 'args' (dict or string) to _create_tool_panel_content for formatting
                current_args_for_display = cli_print_tool_output._streaming_sessions[call_id]['args']
                header, content = _create_tool_panel_content(
                    tool_name, 
                    current_args_for_display, 
                    cli_print_tool_output._streaming_sessions[call_id]['buffer'],
                    execution_info,
                    token_info
                )
                
                # Determine panel style based on status
                status = "running"
                if execution_info:
                    status = execution_info.get('status', 'running')
                
                border_style = "yellow"  # Default for running
                if status == "completed":
                    border_style = "green"
                elif status in ["error", "timeout"]:
                    border_style = "red"
                    
                # Create panel title based on status
                if status == "running":
                    title = "[bold yellow]Running[/bold yellow]"
                elif status == "completed":
                    title = "[bold green]Completed[/bold green]"
                elif status == "error":
                    title = "[bold red]Error[/bold red]"
                elif status == "timeout":
                    title = "[bold red]Timeout[/bold red]"
                else:
                    title = "[bold blue]Tool Execution[/bold blue]"
                
                # Create the panel
                panel = Panel(
                    content,
                    title=title,
                    border_style=border_style,
                    padding=(0, 1),
                    box=ROUNDED,
                    title_align="left"
                )
                
                # If we already have a live panel for this call_id, update it
                if call_id in _LIVE_STREAMING_PANELS:
                    live = _LIVE_STREAMING_PANELS[call_id]
                    live.update(panel)
                    
                    # If this is the final update, stop the live panel after a short delay
                    if execution_info and execution_info.get('is_final', False):
                        # Give a moment for the final panel to be seen
                        time.sleep(0.2)
                        live.stop()
                        # Remove from the active panel dictionary
                        del _LIVE_STREAMING_PANELS[call_id]
                else:
                    # Create a new live panel
                    console = Console(theme=theme)
                    live = Live(panel, console=console, refresh_per_second=4, auto_refresh=True)
                    # Start and store the live panel
                    live.start()
                    _LIVE_STREAMING_PANELS[call_id] = live
                
                # Return early for streaming updates
                return
                
            except ImportError:
                # Fall back to simple updates without Rich
                pass
    else:
        # For non-streaming outputs, check if we've already seen this command
        if command_key in cli_print_tool_output._displayed_commands:
            # Command has already been displayed (likely through streaming), skip duplicate display
            return
            
        # Add to displayed commands since we're going to show it
        # This handles the case where a command is non-streaming from the start
        cli_print_tool_output._displayed_commands.add(command_key)
            
    # For non-streaming updates with call_id, check if already seen
    # This _seen_calls logic is an additional layer for non-streaming calls that might have call_ids
    # but might be distinct from the primary _displayed_commands check based on command_key.
    if call_id and not streaming:
        # Create a more specific key for _seen_calls if needed, possibly including output fingerprint
        seen_call_key = f"{call_id}:{command_key}:{output[:20]}" 
        
        if seen_call_key in cli_print_tool_output._seen_calls:
            return
            
        cli_print_tool_output._seen_calls[seen_call_key] = True
        
    # Standard tool output display for non-streaming or when rich is not available
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        from rich.box import ROUNDED
        from rich.console import Group
        
        # Create a console for output
        console = Console(theme=theme)
        
        # Clean args for display (remove internal counters and flags)
        display_args = args
        if isinstance(args, dict):
            # Remove internal tracking fields that shouldn't be shown to the user
            display_args = {k: v for k, v in args.items() 
                          if k not in ["call_counter", "input_to_session"]}
        
        # Get the panel content - with syntax highlighting
        header, content = _create_tool_panel_content(tool_name, display_args, output, execution_info, token_info)
        
        # Format args for the title display
        args_str = _format_tool_args(display_args, tool_name=tool_name)
        
        # Determine border style based on status
        border_style = "blue"  # Default for non-streaming
        
        if execution_info:
            status = execution_info.get('status', 'completed')
            if status == "completed":
                border_style = "green"
            elif status == "error":
                border_style = "red"
            elif status == "timeout":
                border_style = "red"
        
        # Check if this is a handoff (transfer to another agent)
        is_handoff = tool_name.startswith("transfer_to_")
        
        # Create the title based on whether it's a handoff or regular tool
        if is_handoff:
            # Extract agent name for the handoff title
            agent_name = None
            if tool_name.startswith("transfer_to_"):
                # Remove 'transfer_to_' prefix and convert to a nicer format
                agent_name_raw = tool_name[len("transfer_to_"):]
                # Convert underscores to spaces and capitalize words
                agent_name = " ".join(word.capitalize() for word in agent_name_raw.split("_"))
                
                # Special case for acronyms like DNS or SMTP that might be in the agent name
                # Convert words that are all uppercase to remain uppercase
                parts = agent_name.split()
                for i, part in enumerate(parts):
                    if part.upper() == part and len(part) > 1:  # It's an acronym
                        parts[i] = part.upper()
                agent_name = " ".join(parts)
            
            # For handoffs, include the agent name in the title
            if execution_info:
                status = execution_info.get('status', 'completed')
                if status == "completed":
                    title = f"[bold green]Handoff: {agent_name} [Completed][/bold green]"
                elif status == "error":
                    title = f"[bold red]Handoff: {agent_name} [Error][/bold red]"
                elif status == "timeout":
                    title = f"[bold red]Handoff: {agent_name} [Timeout][/bold red]"
                else:
                    title = f"[bold blue]Handoff: {agent_name}[/bold blue]"
            else:
                title = f"[bold blue]Handoff: {agent_name}[/bold blue]"
        else:
            # For regular tools, use the original format
            if execution_info:
                status = execution_info.get('status', 'completed')
                if status == "completed":
                    title = f"[bold green]{tool_name}({args_str}) [Completed][/bold green]"
                elif status == "error":
                    title = f"[bold red]{tool_name}({args_str}) [Error][/bold red]"
                elif status == "timeout":
                    title = f"[bold red]{tool_name}({args_str}) [Timeout][/bold red]"
                else:
                    title = f"[bold blue]{tool_name}({args_str})[/bold blue]"
            else:
                title = f"[bold blue]{tool_name}({args_str})[/bold blue]"
        
        # Create the panel
        panel = Panel(
            content,
            title=title,
            border_style=border_style,
            padding=(0, 1),
            box=ROUNDED,
            title_align="left"
        )
        
        # Display the panel
        console.print(panel)
        
    except ImportError:
        # Fall back to simple output format without rich
        _print_simple_tool_output(tool_name, args, output, execution_info, token_info)


# Helper function to format tool arguments
def _format_tool_args(args, tool_name=None):
    """Format tool arguments as a clean string."""
    # If the tool is execute_code, we don't want to show any args in the main header,
    # as they are detailed in subsequent panels (either code or args string).
    if tool_name == "execute_code":
        return "" 

    # If args is already a string, it might be pre-formatted or a simple arg string
    if isinstance(args, str):
        # If it looks like a JSON dict string, try to parse and format nicely
        if args.strip().startswith('{') and args.strip().endswith('}'):
            try:
                parsed_dict = json.loads(args)
                # Recursively call with the parsed dict for consistent formatting
                return _format_tool_args(parsed_dict, tool_name=tool_name) 
            except json.JSONDecodeError:
                # Not valid JSON, or not a dict; return as is
                return args
        else:
            # Simple string arg, return as is
            return args
    
    # Format arguments from a dictionary
    if isinstance(args, dict):
        # Only include non-empty values and exclude special flags
        arg_parts = []
        for key, value in args.items():
            # Skip empty values
            if value == "" or value == {} or value is None:
                continue
            # Skip special flags
            if key in ["async_mode", "streaming"] and not value:
                continue

            value_str = str(value)

            # Format the value
            if isinstance(value, str):
                # Truncate long string values
                if len(value_str) > 70 and key not in ["code", "args"]:
                     value_str = value_str[:67] + "..."
                arg_parts.append(f"{key}={value_str}")
            else:
                arg_parts.append(f"{key}={value_str}")
        return ", ".join(arg_parts)
    else:
        return str(args)

def print_message_history(messages, title="Message History"):
    """
    Pretty-print a sequence of messages with enhanced debug information.
    
    Args:
        messages (List[dict]): List of message dictionaries to display
        title (str, optional): Title to display above the message history
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    
    console = Console()
    
    # Create a table for displaying messages
    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Role", style="cyan", width=10)
    table.add_column("Content", width=1000)
    table.add_column("Metadata", width=1000)
    
    # Process each message
    for i, msg in enumerate(messages):
        # Get role with color based on type
        role = msg.get("role", "unknown")
        role_style = {
            "user": "green",
            "assistant": "blue",
            "system": "yellow",
            "tool": "magenta"
        }.get(role, "white")
        
        # Get content preview
        content = msg.get("content")
        content_preview = ""
        if content is None:
            content_preview = "[dim]None[/dim]"
        elif isinstance(content, str):
            # Truncate and escape long content
            content_preview = (content[:37] + "...") if len(content) > 40 else content
            content_preview = content_preview.replace("\n", "\\n")
        elif isinstance(content, list):
            content_preview = f"[list with {len(content)} items]"
        else:
            content_preview = f"[{type(content).__name__}]"
        
        # Gather metadata
        metadata = []
        if msg.get("tool_calls"):
            tc_count = len(msg["tool_calls"])
            tc_info = []
            for tc in msg["tool_calls"]:
                tc_id = tc.get("id", "unknown")
                tc_name = tc.get("function", {}).get("name", "unknown") if "function" in tc else "unknown"
                tc_info.append(f"{tc_name}({tc_id})")
            metadata.append(f"tool_calls[{tc_count}]: {', '.join(tc_info)}")
            
        if msg.get("tool_call_id"):
            metadata.append(f"tool_call_id: {msg['tool_call_id']}")
            
        metadata_str = ", ".join(metadata)
        
        # Add row to table
        table.add_row(
            str(i),
            f"[{role_style}]{role}[/{role_style}]",
            content_preview,
            metadata_str
        )
    
    # Create the panel with the table
    panel = Panel(
        table,
        title=f"[bold]{title}[/bold]",
        expand=False
    )
    
    # Display the panel
    console.print(panel)
    
    return len(messages)  # Return message count for convenience

def get_language_from_code_block(lang_identifier):
    """
    Maps a language identifier from a markdown code block to a proper syntax 
    highlighting language name. Handles common aliases and defaults.
    
    Args:
        lang_identifier (str): Language identifier from markdown code block
        
    Returns:
        str: Proper language name for syntax highlighting
    """
    # Convert to lowercase and strip whitespace
    lang = lang_identifier.lower().strip() if lang_identifier else ""
    
    # Map common language aliases to their proper names
    lang_map = {
        # Empty strings or unknown
        "": "text",
        # Python variants
        "py": "python",
        "python3": "python",
        # JavaScript variants
        "js": "javascript",
        "jsx": "jsx",
        "ts": "typescript",
        "tsx": "tsx",
        "typescript": "typescript",
        # Shell variants
        "sh": "bash",
        "shell": "bash",
        "console": "bash",
        "terminal": "bash",
        # Web languages
        "html": "html",
        "css": "css",
        "json": "json",
        "xml": "xml",
        "yml": "yaml",
        "yaml": "yaml",
        # C family
        "c": "c",
        "cpp": "cpp",
        "c++": "cpp",
        "csharp": "csharp",
        "cs": "csharp",
        "java": "java",
        # Other common languages
        "go": "go",
        "golang": "go",
        "ruby": "ruby",
        "rb": "ruby",
        "rust": "rust",
        "php": "php",
        "sql": "sql",
        "diff": "diff",
        "markdown": "markdown",
        "md": "markdown",
        # Default fallback
        "text": "text",
        "plaintext": "text",
        "txt": "text",
    }
    
    # Return mapped language or default to the original if not in map
    return lang_map.get(lang, lang or "text")

def _create_tool_panel_content(tool_name, args, output, execution_info=None, token_info=None):
    """Create the header and content for a tool output panel."""
    from rich.text import Text
    from rich.syntax import Syntax # Import Syntax for highlighting
    from rich.panel import Panel
    from rich.console import Group
    from rich.box import ROUNDED
    
    # Check if this is a handoff (transfer to another agent)
    is_handoff = tool_name.startswith("transfer_to_")
    
    # Format arguments for display, passing tool_name for specific formatting
    args_str = _format_tool_args(args, tool_name=tool_name)
    
    # Get timing information
    timing_info, tool_time = _get_timing_info(execution_info)
    
    # Create header
    header = Text()
    if is_handoff:
        # Extract agent name from transfer function name
        agent_name = None
        if tool_name.startswith("transfer_to_"):
            # Remove 'transfer_to_' prefix and convert to a nicer format
            agent_name_raw = tool_name[len("transfer_to_"):]
            # Convert underscores to spaces and capitalize words
            agent_name = " ".join(word.capitalize() for word in agent_name_raw.split("_"))
            
            # Special case for acronyms like DNS or SMTP that might be in the agent name
            # Convert words that are all uppercase to remain uppercase
            parts = agent_name.split()
            for i, part in enumerate(parts):
                if part.upper() == part and len(part) > 1:  # It's an acronym
                    parts[i] = part.upper()
            agent_name = " ".join(parts)
        
        # For handoffs, show "transfer_to_X → Agent Name"
        header.append(tool_name, style="#00BCD4")
        if agent_name:
            header.append(" → ", style="bold yellow")
            header.append(agent_name, style="bold green")
        
        # Add arguments if present
        if args_str:
            header.append("(", style="yellow")
            header.append(args_str, style="yellow")
            header.append(")", style="yellow")
    else:
        # For regular tools, use the original format
        header.append(tool_name, style="#00BCD4")
        header.append("(", style="yellow")
        header.append(args_str, style="yellow")
        header.append(")", style="yellow")
    
    # Add timing information
    if timing_info:
        header.append(f" [{' | '.join(timing_info)}]", style="cyan")
    
    # Add environment info if available
    if execution_info and execution_info.get('environment'):
        env = execution_info.get('environment')
        host = execution_info.get('host', '')
        if host:
            header.append(f" [{env}:{host}]", style="magenta")
        else:
            header.append(f" [{env}]", style="magenta")
    
    # Add status information if available
    if execution_info:
        status = execution_info.get('status', None)
        if status == "completed":
            header.append(" [Completed]", style="green")
        elif status == "running":
            header.append(" [Running]", style="yellow")
        elif status == "error":
            header.append(" [Error]", style="red")
        elif status == "timeout":
            header.append(" [Timeout]", style="red")
    
    # Create token information if available
    token_content = _create_token_info_display(token_info)
    
    # Determine if we need specialized content formatting
    group_content = [header]

    if tool_name == "execute_code" and isinstance(args, dict):
        command = args.get("command")
        code_from_code_key = args.get("code")
        language_from_lang_key = args.get("language", "python")
        args_str_payload = args.get("args")

        panel1_content_str = None
        panel1_language_name = "text"
        panel1_title = "Executed Command Details"
        panel1_border_style = "cyan" # Default for "executed code"

        if command == "execute" and code_from_code_key:
            pass
        elif args_str_payload: # Covers 'cat << EOF', 'python3 script.py'
            panel1_content_str = args_str_payload
            inferred_lang_for_args = "text" # Default

            if command and command.lower() == "cat" and \
               ("<<" in args_str_payload or ">" in args_str_payload):
                # For cat with heredoc/redirection, infer from target file
                match = re.search(r'(?:>|>>)\s*([\w\./-]+\.\w+)',
                                  args_str_payload)
                if match:
                    filename = match.group(1)
                    ext = filename.split('.')[-1] if '.' in filename else ""
                    inferred_lang_for_args = get_language_from_code_block(ext)
                else:
                    inferred_lang_for_args = get_language_from_code_block("bash")
            elif re.match(r'^[\w\./-]+\.\w+$', args_str_payload.strip()):
                # If args_str_payload is a filename like "script.py"
                filename = args_str_payload.strip()
                ext = filename.split('.')[-1] if '.' in filename else ""
                inferred_lang_for_args = get_language_from_code_block(ext)
            else:
                # General arguments string, could be JSON, XML, or just text/bash
                try:
                    json.loads(args_str_payload)
                    inferred_lang_for_args = "json"
                except json.JSONDecodeError:
                    if args_str_payload.strip().startswith("<") and \
                       args_str_payload.strip().endswith(">"):
                        inferred_lang_for_args = "xml"
                    elif command: # Default to bash if it's for a known command
                        inferred_lang_for_args = get_language_from_code_block("bash")
            
            panel1_language_name = inferred_lang_for_args
            panel1_title = f"Code ({panel1_language_name})"
            panel1_border_style = "yellow"

        if panel1_content_str is not None:
            syntax_obj_panel1 = Syntax(
                panel1_content_str,
                panel1_language_name,
                theme="monokai",
                line_numbers=True,
                background_color="#272822",
                indent_guides=True,
                word_wrap=True
            )
            actual_panel1 = Panel(
                syntax_obj_panel1,
                title=panel1_title,
                border_style=panel1_border_style,
                title_align="left",
                box=ROUNDED,
                padding=(0, 1)
            )
            group_content.extend([Text("\n"), actual_panel1])

        if output:
            output_lang_name = "text"
            try:
                json.loads(output)
                output_lang_name = "json"
            except json.JSONDecodeError:
                if output.strip().startswith("<") and \
                   output.strip().endswith(">") and \
                   "<?xml" in output.lower():
                    output_lang_name = "xml"
            
            output_syntax = Syntax(
                output,
                get_language_from_code_block(output_lang_name),
                theme="monokai",
                background_color="#272822",
                word_wrap=True
            )
            
            output_panel_title = "Output"
            if command and panel1_content_str: # If input panel was shown
                output_panel_title = f"Output of '{command}'"

            output_panel = Panel(
                output_syntax,
                title=output_panel_title,
                border_style="green",
                title_align="left",
                box=ROUNDED,
                padding=(0, 1)
            )
            group_content.extend([Text("\n"), output_panel])

    # Special handling for generic_linux_command or any command containing 'command'
    elif "command" in tool_name.lower() or "shell" in tool_name.lower():
        try:
            # Highlight the output as bash
            output_syntax = Syntax(output, "bash", theme="monokai", 
                                  background_color="#272822", word_wrap=True)
            
            # Create a panel for the formatted output
            output_panel = Panel(
                output_syntax,
                title="Command Output",
                border_style="green",
                title_align="left",
                box=ROUNDED,
                padding=(0, 1)
            )
            
            # Assemble content with highlighted output
            group_content.extend([Text("\n"), output_panel])
            
        except Exception:
            # Fallback if syntax highlighting fails, just add raw output
            group_content.extend([Text("\n"), Text(output)])
    
    # Fallback for other tools to display their output if not handled above
    elif output and output.strip(): # Check if output is not None and not just whitespace
        output_lang_name = "text"
        try:
            # Attempt to parse as JSON to infer language
            json.loads(output)
            output_lang_name = "json"
        except json.JSONDecodeError:
            # Basic check for XML-like content if not JSON
            if output.strip().startswith("<") and output.strip().endswith(">"):
                output_lang_name = "xml"
            # Add more detections for other types (e.g., YAML) if needed
        
        # Use get_language_from_code_block for consistent language mapping
        syntax_lang = get_language_from_code_block(output_lang_name)
        
        output_syntax = Syntax(
            output,
            syntax_lang,
            theme="monokai",
            background_color="#272822", # Consistent theme
            word_wrap=True,
            line_numbers=True, # Usually helpful for structured output
            indent_guides=True
        )
        
        output_display_panel = Panel(
            output_syntax,
            title="Tool Output", # Generic title
            border_style="green", # Consistent
            title_align="left",
            box=ROUNDED,
            padding=(0, 1)
        )
        group_content.extend([Text("\n"), output_display_panel])

    # Add token info if available
    if token_content:
        group_content.extend([Text("\n"), token_content])
    
    return header, Group(*group_content)

# Helper function to get timing information
def _get_timing_info(execution_info=None):
    """Get timing information for display."""
    import time
    
    # Get session timing information
    try:
        from cai.cli import START_TIME
        total_time = time.time() - START_TIME if START_TIME else None
    except ImportError:
        total_time = None
    
    # Extract execution timing info
    tool_time = None
    if execution_info:
        tool_time = execution_info.get('tool_time')
    
    # Format timing info for display
    timing_info = []
    if total_time:
        timing_info.append(f"Total: {format_time(total_time)}")
    if tool_time:
        timing_info.append(f"Tool: {format_time(tool_time)}")
    
    return timing_info, tool_time

# Helper function to create token info display
def _create_token_info_display(token_info=None):
    """Create token information display text."""
    if not token_info:
        return None
    
    from rich.text import Text
    
    model = token_info.get('model', '')
    interaction_input_tokens = token_info.get('interaction_input_tokens', 0)
    interaction_output_tokens = token_info.get('interaction_output_tokens', 0)
    interaction_reasoning_tokens = token_info.get('interaction_reasoning_tokens', 0)
    total_input_tokens = token_info.get('total_input_tokens', 0)
    total_output_tokens = token_info.get('total_output_tokens', 0)
    total_reasoning_tokens = token_info.get('total_reasoning_tokens', 0)
    
    # Only continue if we have actual token information
    if not (interaction_input_tokens > 0 or total_input_tokens > 0):
        return None
    
    # Create token display
    return _create_token_display(
        interaction_input_tokens,
        interaction_output_tokens,
        interaction_reasoning_tokens,
        total_input_tokens,
        total_output_tokens,
        total_reasoning_tokens,
        model,
        token_info.get('interaction_cost'),
        token_info.get('total_cost')
    )

# Helper function for simple tool output without Rich
def _print_simple_tool_output(tool_name, args, output, execution_info=None, token_info=None):
    """Print tool output without Rich formatting."""
    # Format arguments
    args_str = _format_tool_args(args)
    
    # Get tool execution time if available
    tool_time_str = ""
    execution_status = ""
    if execution_info:
        time_taken = execution_info.get('time_taken', 0) or execution_info.get('tool_time', 0)
        status = execution_info.get('status', 'completed')
        
        # Add execution info to the tool call display
        if time_taken:
            tool_time_str = f"Tool: {format_time(time_taken)}"
            execution_status = f" [{status} in {time_taken:.2f}s]"
        else:
            execution_status = f" [{status}]"
    
    # Create timing display string
    timing_info, _ = _get_timing_info(execution_info)
    timing_display = f" [{' | '.join(timing_info)}]" if timing_info else ""
    
    # Show tool name, args, execution status and timing display
    tool_call = f"{tool_name}({args_str})"
    print(color(f"Tool Output: {tool_call}{timing_display}{execution_status}", fg="blue"))
    
    # If we have token info, display it
    if token_info:
        model = token_info.get('model', '')
        interaction_input_tokens = token_info.get('interaction_input_tokens', 0)
        interaction_output_tokens = token_info.get('interaction_output_tokens', 0)
        interaction_reasoning_tokens = token_info.get('interaction_reasoning_tokens', 0)
        total_input_tokens = token_info.get('total_input_tokens', 0)
        total_output_tokens = token_info.get('total_output_tokens', 0)
        total_reasoning_tokens = token_info.get('total_reasoning_tokens', 0)
        
        # If we have complete token information, display it
        if (interaction_input_tokens > 0 or total_input_tokens > 0):
            # Manually create formatted output similar to _create_token_display
            print(color(f"  Current: I:{interaction_input_tokens} O:{interaction_output_tokens} R:{interaction_reasoning_tokens}", fg="cyan"))
            
            # Calculate or use provided costs
            current_cost = COST_TRACKER.process_interaction_cost(
                model, 
                interaction_input_tokens, 
                interaction_output_tokens,
                interaction_reasoning_tokens,
                token_info.get('interaction_cost')
            )
            total_cost_value = COST_TRACKER.process_total_cost(
                model,
                total_input_tokens,
                total_output_tokens,
                total_reasoning_tokens,
                token_info.get('total_cost')
            )
            print(color(f"  Cost: Current ${current_cost:.4f} | Total ${total_cost_value:.4f} | Session ${COST_TRACKER.session_total_cost:.4f}", fg="cyan"))
            
            # Show context usage
            context_pct = interaction_input_tokens / get_model_input_tokens(model) * 100
            indicator = "🟩" if context_pct < 50 else "🟨" if context_pct < 80 else "🟥"
            print(color(f"  Context: {context_pct:.1f}% {indicator}", fg="cyan"))
    
    # Print the actual output
    print(output)
    print()

# Add a new function to start a streaming tool execution
def start_tool_streaming(tool_name, args, call_id=None):
    """
    Start a streaming tool execution session.
    This allows for progressive updates during tool execution.
    
    Args:
        tool_name: Name of the tool being executed
        args: Arguments to the tool (dictionary or string)
        call_id: Optional call ID for this execution. If not provided, one will be generated.
        
    Returns:
        call_id: The call ID for this streaming session (can be used for updates)
    """
    import time
    import uuid
    
    # Generate a command key to check for duplicates - match format used in cli_print_tool_output
    if isinstance(args, dict):
        cmd = args.get("command", "")
        cmd_args = args.get("args", "")
        command_key = f"{tool_name}:{cmd_args}"
    else:
        command_key = f"{tool_name}:{args}"
    
    # Check if we've already seen this exact command recently
    if not hasattr(start_tool_streaming, '_recent_commands'):
        start_tool_streaming._recent_commands = {}
        
    # If we have an existing active streaming session for this command, reuse its call_id
    # This prevents duplicate panels when the same command runs multiple times
    for existing_call_id, info in list(start_tool_streaming._recent_commands.items()):
        # Only consider recent commands (last 10 seconds)
        timestamp = info.get('timestamp', 0)
        if time.time() - timestamp < 10.0:
            existing_command_key = info.get('command_key', '')
            # Get the existing session info if available
            if (hasattr(cli_print_tool_output, '_streaming_sessions') and 
                existing_call_id in cli_print_tool_output._streaming_sessions):
                session = cli_print_tool_output._streaming_sessions[existing_call_id]
                # If this is the same command and not complete, reuse the call_id
                if existing_command_key == command_key and not session.get('is_complete', False):
                    return existing_call_id
    
    # Generate a call_id if not provided
    if not call_id:
        cmd_part = ""
        if isinstance(args, dict) and "command" in args:
            cmd_part = f"{args['command']}_"
        call_id = f"cmd_{cmd_part}{str(uuid.uuid4())[:8]}"
    
    # Track this call_id with command key for better duplicate detection
    start_tool_streaming._recent_commands[call_id] = {
        'timestamp': time.time(),
        'command_key': command_key
    }
    
    # Cleanup old entries to prevent memory growth
    current_time = time.time()
    start_tool_streaming._recent_commands = {
        k: v for k, v in start_tool_streaming._recent_commands.items() 
        if current_time - v.get('timestamp', 0) < 30  # Keep entries from last 30 seconds
    }
    
    # Show initial message with "Starting..." output
    cli_print_tool_output(
        tool_name=tool_name,
        args=args,
        output="Starting tool execution...",
        call_id=call_id,
        execution_info={"status": "running", "start_time": time.time()},
        streaming=True
    )
    
    return call_id

# Add a function to update a streaming tool execution
def update_tool_streaming(tool_name, args, output, call_id):
    """
    Update a streaming tool execution with new output.
    
    Args:
        tool_name: Name of the tool being executed
        args: Arguments to the tool (dictionary or string)
        output: New output to display
        call_id: The call ID for this streaming session
        
    Returns:
        None
    """
    # Update the streaming output
    cli_print_tool_output(
        tool_name=tool_name,
        args=args,
        output=output,
        call_id=call_id,
        execution_info={"status": "running", "replace_buffer": True},
        streaming=True
    )

# Add a function to complete a streaming tool execution
def finish_tool_streaming(tool_name, args, output, call_id, execution_info=None, token_info=None):
    """
    Complete a streaming tool execution.
    
    Args:
        tool_name: Name of the tool being executed
        args: Arguments to the tool (dictionary or string)
        output: Final output to display
        call_id: The call ID for this streaming session
        execution_info: Optional execution information
        token_info: Optional token information
        
    Returns:
        None
    """
    import time
    
    # Prepare execution info with completion status
    if execution_info is None:
        execution_info = {}
    
    # Add completion markers
    execution_info["status"] = execution_info.get("status", "completed")
    execution_info["is_final"] = True
    execution_info["replace_buffer"] = True
    
    # Calculate execution time if start_time is in the streaming session
    if hasattr(cli_print_tool_output, '_streaming_sessions') and call_id in cli_print_tool_output._streaming_sessions:
        session = cli_print_tool_output._streaming_sessions[call_id]
        if 'start_time' in session and 'tool_time' not in execution_info:
            execution_info["tool_time"] = time.time() - session['start_time']
    
    # Add compact token info for display
    if token_info:
        # Create compact token representation
        input_tokens = token_info.get('interaction_input_tokens', 0)
        output_tokens = token_info.get('interaction_output_tokens', 0)
        interaction_cost = token_info.get('interaction_cost', 0)
        
        # Calculate cost if not provided
        if not interaction_cost and input_tokens > 0:
            model_name = token_info.get('model', os.environ.get('CAI_MODEL', 'qwen2.5:14b'))
            interaction_cost = calculate_model_cost(model_name, input_tokens, output_tokens)
        
        # Add compact token info to output
        if input_tokens > 0:
            compact_tokens = f"\n[Tokens: I:{input_tokens} O:{output_tokens} | Cost: ${interaction_cost:.4f}]"
            if output:
                if not output.endswith("\n"):
                    output += "\n"
                output += compact_tokens
            else:
                output = compact_tokens
    
    # Show the final output
    cli_print_tool_output(
        tool_name=tool_name,
        args=args,
        output=output,
        call_id=call_id,
        execution_info=execution_info,
        token_info=token_info,
        streaming=True
    )
    
    # Mark the streaming session as complete
    if hasattr(cli_print_tool_output, '_streaming_sessions') and call_id in cli_print_tool_output._streaming_sessions:
        cli_print_tool_output._streaming_sessions[call_id]['is_complete'] = True

def check_flag(output, ctf, challenge=None):
    """
    Check if the CTF flag is present in the output.

    Args:
        output (str): The output to check for the flag.
        ctf: The CTF environment object.
        challenge (str, optional): The specific challenge to check.
            Defaults to None.

    Returns:
        tuple: A tuple containing a boolean indicating if the flag was
            found and the flag itself if found, otherwise None.
    """
    # Get the challenge from the environment variable or default to the first
    # challenge
    challenge_key = os.getenv("CTF_CHALLENGE")
    challenges = list(ctf.get_challenges().keys())
    challenge = (
        challenge_key
        if challenge_key in challenges
        else (challenges[0] if len(challenges) > 0 else None))
    if ctf:
        if ctf.check_flag(
            output, challenge
        ):  # check if the flag is in the output
            flag = ctf.flags[challenge]
            print(
                color(
                    f"Flag found: {flag}",
                    fg="green") +
                " in output " +
                color(
                    f"{output}",
                    fg="blue"))
            return True, flag
    else:
        print(color("CTF environment not found or provided", fg="yellow"))
    return False, None

def setup_ctf():
    """Setup CTF environment if CTF_NAME is provided"""
    ctf_name = os.getenv('CTF_NAME', None)
    if not ctf_name:
        print(color("CTF name not provided, necessary to run CTF", fg="white", bg="red"))
        sys.exit(1)

    print(color("Setting up CTF: ", fg="black", bg="yellow") +
          color(ctf_name, fg="black", bg="yellow"))

    ctf = ptt.ctf(  # pylint: disable=I1101  # noqa
        ctf_name,
        subnet=os.getenv('CTF_SUBNET', "192.168.2.0/24"),
        container_name="ctf_target",
        ip_address=os.getenv('CTF_IP', "192.168.2.100"),
    )
    ctf.start_ctf()

    # Get the challenge from the environment variable or default to the
        # first challenge
    challenge_key = os.getenv('CTF_CHALLENGE')  # TODO:
    challenges = list(ctf.get_challenges().keys())
    challenge = challenge_key if challenge_key in challenges else (
    challenges[0] if len(challenges) > 0 else None)

    # Use the user master template
    messages =  Template(
        filename="src/cai/prompts/core/user_master_template.md").render(
        ctf=ctf,
        challenge=challenge,
        ip=ctf.get_ip() if ctf else None,
    )


    print(        color(
                "Testing CTF: ",
                fg="black",
                bg="yellow") +
            color(
                ctf.name,
                fg="black",
                bg="yellow"))
    if not challenge_key or challenge_key not in challenges:
            print(
                color(
                    "No challenge provided or challenge not found. Attempting to use the first challenge.",
                    fg="white",
                    bg="blue"))
    if challenge:
            print(
                color(
                    "Testing challenge: ",
                    fg="white",
                    bg="blue") +
                color(
                    "'" +
                    challenge +
                    "' (" +
                    repr(
                        ctf.flags[challenge]) +
                    ")",
                    fg="white",
                    bg="blue"))

    return ctf, messages

def create_claude_thinking_context(agent_name, counter, model):
    """
    Create a streaming context for Claude thinking/reasoning display.
    This creates a dedicated panel that shows Claude's internal reasoning process.
    
    Args:
        agent_name: The name of the agent
        counter: The interaction counter
        model: The model name
        
    Returns:
        A dictionary with the streaming context for thinking display
    """
    import uuid
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text
    from rich.box import ROUNDED
    from rich.console import Group
    import shutil
    
    # Generate unique thinking context ID
    thinking_id = f"thinking_{agent_name}_{counter}_{str(uuid.uuid4())[:8]}"
    
    # Check if we already have an active thinking panel
    if thinking_id in _CLAUDE_THINKING_PANELS:
        return _CLAUDE_THINKING_PANELS[thinking_id]
    
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Terminal size for better display
        terminal_width, _ = shutil.get_terminal_size((100, 24))
        panel_width = min(terminal_width - 4, 120)
        
        # Create the thinking panel header
        header = Text()
        header.append("🧠 ", style="bold yellow")
        header.append(f"Claude Reasoning [{counter}]", style="bold yellow")
        header.append(f" | {agent_name}", style="bold cyan")
        header.append(f" | {timestamp}", style="dim")
        
        # Initial thinking content
        thinking_content = Text("Thinking...", style="italic dim")
        
        # Create the panel for thinking
        panel = Panel(
            Group(header, Text("\n"), thinking_content),
            title="[bold yellow]🧠 Thinking Process[/bold yellow]",
            border_style="yellow",
            box=ROUNDED,
            padding=(1, 2),
            width=panel_width,
            expand=True
        )
        
        # Create Live display object
        live = Live(panel, refresh_per_second=8, console=console, auto_refresh=True)
        
        context = {
            "thinking_id": thinking_id,
            "live": live,
            "panel": panel,
            "header": header,
            "thinking_content": thinking_content,
            "timestamp": timestamp,
            "model": model,
            "agent_name": agent_name,
            "panel_width": panel_width,
            "is_started": False,
            "accumulated_thinking": "",
        }
        
        # Store in global tracker
        _CLAUDE_THINKING_PANELS[thinking_id] = context
        
        return context
        
    except Exception as e:
        print(f"Error creating Claude thinking context: {e}")
        return None

def update_claude_thinking_content(context, thinking_delta):
    """
    Update the Claude thinking content with new reasoning text.
    
    Args:
        context: The thinking context created by create_claude_thinking_context
        thinking_delta: The new thinking text to add
    """
    if not context:
        return False
        
    try:
        # Accumulate the thinking text
        context["accumulated_thinking"] += thinking_delta
        
        # Create syntax highlighted thinking content
        from rich.syntax import Syntax
        from rich.text import Text
        from rich.console import Group
        
        # Try to format as markdown-like reasoning
        thinking_text = context["accumulated_thinking"]
        
        # Create formatted thinking display
        if len(thinking_text) > 500:
            # For long thinking, use syntax highlighting
            thinking_display = Syntax(
                thinking_text,
                "markdown",
                theme="monokai",
                background_color="#2E2E2E",
                word_wrap=True,
                line_numbers=False
            )
        else:
            # For short thinking, use regular text with styling
            thinking_display = Text(thinking_text, style="white")
        
        # Update the panel content
        updated_panel = Panel(
            Group(
                context["header"], 
                Text("\n"), 
                thinking_display
            ),
            title="[bold yellow]🧠 Thinking Process[/bold yellow]",
            border_style="yellow",
            box=ROUNDED,
            padding=(1, 2),
            width=context.get("panel_width", 100),
            expand=True
        )
        
        # Start the display if not already started
        if not context.get("is_started", False):
            try:
                context["live"].start()
                context["is_started"] = True
            except Exception as e:
                print(f"Error starting Claude thinking display: {e}")
                return False
        
        # Update the live display
        context["live"].update(updated_panel)
        context["panel"] = updated_panel
        context["live"].refresh()
        
        return True
        
    except Exception as e:
        print(f"Error updating Claude thinking content: {e}")
        return False

def finish_claude_thinking_display(context):
    """
    Finish the Claude thinking display session.
    
    Args:
        context: The thinking context to finish
    """
    if not context:
        return False
        
    # Clean up from global tracker
    thinking_id = context.get("thinking_id")
    if thinking_id and thinking_id in _CLAUDE_THINKING_PANELS:
        del _CLAUDE_THINKING_PANELS[thinking_id]
    
    try:
        # Import required classes
        from rich.text import Text
        from rich.syntax import Syntax
        from rich.console import Group
        
        # Add final formatting to show completion
        final_header = Text()
        final_header.append("🧠 ", style="bold green")
        final_header.append(f"Claude Reasoning Complete", style="bold green")
        final_header.append(f" | {context['agent_name']}", style="bold cyan")
        final_header.append(f" | {context['timestamp']}", style="dim")
        
        thinking_text = context["accumulated_thinking"]
        
        if thinking_text.strip():
            # Create final formatted display
            final_thinking_display = Syntax(
                thinking_text,
                "markdown",
                theme="monokai",
                background_color="#2E2E2E",
                word_wrap=True,
                line_numbers=False
            )
        else:
            final_thinking_display = Text("No reasoning captured", style="dim italic")
        
        # Create final panel
        final_panel = Panel(
            Group(
                final_header,
                Text("\n"),
                final_thinking_display
            ),
            title="[bold green]🧠 Thinking Complete[/bold green]",
            border_style="green",
            box=ROUNDED,
            padding=(1, 2),
            width=context.get("panel_width", 100),
            expand=True
        )
        
        # Update one last time
        if context.get("is_started", False):
            context["live"].update(final_panel)
            
            # Give a moment for the final panel to be seen
            import time
            time.sleep(0.3)
            
            # Stop the live display
            context["live"].stop()
        
        return True
        
    except Exception as e:
        print(f"Error finishing Claude thinking display: {e}")
        return False

def detect_claude_thinking_in_stream(model_name):
    """
    Detect if a model should show thinking/reasoning display.
    Only applies to Claude models with reasoning capability.
    
    Args:
        model_name: The model name to check
        
    Returns:
        bool: True if thinking display should be shown
    """
    if not model_name:
        return False
        
    model_str = str(model_name).lower()
    
    # Check for Claude models with reasoning capability
    # According to LiteLLM docs, Claude 3.7, Claude 4 and models with "thinking" support reasoning
    has_reasoning = (
        "claude" in model_str and (
            "3.7" in model_str or 
            "4" in model_str or
            "thinking" in model_str
        )
    )
    
    return has_reasoning

def start_claude_thinking_if_applicable(model_name, agent_name, counter):
    """
    Start Claude thinking display if the model supports it.
    
    Args:
        model_name: The model name
        agent_name: The agent name
        counter: The interaction counter
        
    Returns:
        The thinking context if created, None otherwise
    """
    if detect_claude_thinking_in_stream(model_name):
        return create_claude_thinking_context(agent_name, counter, model_name)
    return None
