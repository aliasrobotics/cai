# CAI REPL Commands

This document provides documentation for all commands available in the CAI (Context-Aware Interface) REPL system.

## Base Command System (`base.py`)

---

## Core Commands

### **Agent Management (`agent.py`)**
### **AgentCommand**
- **Command**: `/agent`
- **Purpose**: Managing and switching between different AI agents
- **Features**:
  - List available agents
  - Switch between agents
  - Display agent information
  - Visualize agent interaction graphs

### **Configuration Management (`config.py`)**
### **ConfigCommand**
- **Command**: `/config`
- **Purpose**: Display and configure environment variables
- **Features**:
  - Show current environment variable settings
  - Configure CTF (Capture The Flag) variables
  - Manage configuration through environment variables

### **Context Usage Monitoring (`context.py`)** 🚀 **CAI PRO Exclusive**
### **ContextCommand**
> **⚡ CAI PRO Exclusive Feature**
> The `/context` command is available exclusively in **[CAI PRO](https://aliasrobotics.com/cybersecurityai.php)**. To access this feature and unlock advanced monitoring capabilities, visit [Alias Robotics](https://aliasrobotics.com/cybersecurityai.php) for more information.

- **Command**: `/context` or `/ctx`
- **Purpose**: View context usage and token statistics for the current conversation
- **Features**:
  - Display total context usage (used/max tokens) with percentage
  - Visual grid representation of context usage with CAI logo
  - Detailed breakdown by category:
    - System prompt tokens
    - Tool definitions tokens
    - Memory/RAG tokens
    - User prompts tokens
    - Assistant responses tokens
    - Tool calls tokens
    - Tool results tokens
  - Free space visualization
  - Context usage tracking across conversation history
  - Real-time token consumption monitoring
- **Usage Example**:
  ```bash
  # Show context usage for current agent
  /context

  # Alternative short form
  /ctx
  ```
- **Output Includes**:
  - Visual grid showing filled vs free context space
  - Percentage breakdown per category
  - Token counts formatted with 'k' suffix for thousands
  - Color-coded categories for easy identification
  - Summary of total input tokens from last iteration

### **Cost Tracking (`cost.py`)**
### **CostCommand**
- **Command**: `/cost`
- **Purpose**: View usage costs and statistics
- **Features**:
  - Display current session costs
  - Show cost breakdowns by model
  - Track usage over time
  - Cost statistics and reporting

### **Exit (`exit.py`)**
### **ExitCommand**
- **Command**: `/exit`
- **Purpose**: Terminate the CAI REPL session
- **Features**:
  - Clean shutdown of the REPL
  - Save current session data
  - Cleanup background processes

### **Help System (`help.py`)**
### **HelpCommand**
- **Command**: `/help` or `/?`
- **Purpose**: Display help information and command documentation
- **Features**:
  - List available commands
  - Show command usage
  - Display command aliases
  - Provide help for specific commands

### **History Management (`history.py`)**
### **HistoryCommand**
- **Command**: `/history`
- **Purpose**: Display conversation history with agent filtering
- **Features**:
  - Show conversation history
  - Filter by specific agents
  - Display message tree structure
  - Export history functionality

---

## Data Management Commands

### **Compact Conversation (`compact.py`)**
### **CompactCommand**
- **Command**: `/compact`
- **Purpose**: Compact current conversation and manage model/prompt settings
- **Features**:
  - Reduce conversation context size
  - Change model during compaction
  - Modify prompt settings
  - Maintain conversation flow while reducing tokens

### **Environment Display (`env.py`)**
### **EnvCommand**
- **Command**: `/env`
- **Purpose**: Display current environment variables
- **Features**:
  - Show all environment variables
  - Filter by variable patterns
  - Display CAI-specific environment settings

### **Load Data (`load.py`)**
### **LoadCommand**
- **Command**: `/load`
- **Purpose**: Load JSONL data into the current session context
- **Features**:
  - Load conversation history from files
  - Import external data
  - Integrate with parallel configurations
  - Support for various data formats

### **Memory Management (`memory.py`)**
### **MemoryCommand**
- **Command**: `/memory`
- **Purpose**: Manage persistent memory storage in `.cai/memory`
- **Features**:
  - Store conversation context persistently
  - Apply memory to current context
  - Manage memory entries
  - Persistent storage across sessions

### **Flush History (`flush.py`)**
### **FlushCommand**
- **Command**: `/flush`
- **Purpose**: Clear conversation history
- **Features**:
  - Clear current conversation
  - Reset agent contexts
  - Clean up memory
  - Start fresh conversation

---

## Model Management Commands

### **Model Configuration (`model.py`)**
### **ModelCommand**
- **Command**: `/model`
- **Purpose**: View and change the current LLM model
- **Features**:
  - Switch between different models
  - Display model information
  - Configure model parameters
  - Support for LiteLLM and Ollama

### **ModelShowCommand**
- **Command**: `/model-show`
- **Purpose**: Show all available models from LiteLLM repository
- **Features**:
  - List all available models
  - Display model categories
  - Show model capabilities
  - Filter by provider

---

## Advanced Features

### **Graph Visualization (`graph.py`)**
### **GraphCommand**
- **Command**: `/graph`
- **Purpose**: Visualize agent interaction graphs
- **Features**:
  - Display directed graph of conversations
  - Show user and agent interactions
  - Highlight tool calls
  - Visualize conversation flow

### **Parallel Execution (`parallel.py`)**
### **ParallelCommand**
- **Command**: `/parallel`
- **Purpose**: Manage parallel agent configurations
- **Features**:
  - Configure multiple agents
  - Set different models per agent
  - Execute agents in parallel
  - Manage parallel configurations

### **Run Parallel (`run.py`)**
### **RunCommand**
- **Command**: `/run`
- **Purpose**: Execute queued prompts in parallel mode
- **Features**:
  - Queue prompts for different agents
  - Execute all queued prompts
  - Manage parallel execution
  - Collect results from multiple agents

### **Merge Histories (`merge.py`)**
### **MergeCommand**
- **Command**: `/merge`
- **Purpose**: Merge agent message histories (alias for `/parallel merge`)
- **Features**:
  - Combine histories from multiple agents
  - Integrate parallel conversation results
  - Shortcut for parallel merge functionality

---

## Integration Commands

### **MCP Integration (`mcp.py`)**
### **MCPCommand**
- **Command**: `/mcp`
- **Purpose**: Manage MCP (Model Context Protocol) servers and their tools
- **Features**:
  - Load SSE MCP servers
  - Load STDIO MCP servers
  - List active MCP connections
  - Add MCP tools to agents
  - Manage MCP server lifecycle

### **Platform Features (`platform.py`)**
### **PlatformCommand**
- **Command**: `/platform`
- **Purpose**: Interact with platform-specific features
- **Features**:
  - Access platform extensions
  - Platform-specific integrations
  - Check platform availability

---

## System Management Commands

### **Process Management (`kill.py`)**
### **KillCommand**
- **Command**: `/kill`
- **Purpose**: Terminate active processes or sessions
- **Features**:
  - Kill background processes
  - Terminate stuck sessions
  - Process cleanup

### **Shell Access (`shell.py`)**
### **ShellCommand**
- **Command**: `/shell`
- **Purpose**: Execute shell commands from within the REPL
- **Features**:
  - Run system commands
  - Access workspace directory
  - Container workspace support
  - Signal handling for processes

### **Virtualization (`virtualization.py`)**
### **VirtualizationCommand**
- **Command**: `/virtualization` or `/virt`
- **Purpose**: Manage Docker-based virtualization environments
- **Features**:
  - Set up Docker containers
  - Manage container lifecycle
  - Workspace virtualization
  - Environment isolation

### **Workspace Management (`workspace.py`)**
### **WorkspaceCommand**
- **Command**: `/workspace` or `/ws`
- **Purpose**: Manage workspace within Docker containers or locally
- **Features**:
  - Navigate workspace directories
  - Mount external directories
  - Container workspace management
  - File system operations

### **Quickstart (`quickstart.py`)**
### **QuickstartCommand**
- **Command**: `/quickstart`
- **Purpose**: Display setup information for new users
- **Features**:
  - Essential setup guidance
  - Configuration instructions
  - Getting started tutorial
  - Auto-runs on first launch

---

## Utility Commands

### **Command Completion (`completer.py`)**
### **FuzzyCommandCompleter**
- **Purpose**: Intelligent command completion with fuzzy matching
- **Features**:
  - Command auto-completion
  - Fuzzy matching for typos
  - Subcommand suggestions
  - Argument completion
  - Command shadowing detection

---

## Usage Examples

### Basic Workflow
```bash
# Start CAI REPL
cai

# View available agents
/agent list

# Switch to a specific agent
/agent switch <agent_name>

# View conversation history
/history

# Change model
/model gpt-4

# Clear conversation
/flush

# Exit
/exit
```

### Advanced Features
```bash
# Set up parallel execution
/parallel create agent1 --model gpt-4
/parallel create agent2 --model claude-3

# Queue prompts
/run queue agent1 "Analyze this code"
/run queue agent2 "Review the analysis"

# Execute in parallel
/run execute

# Merge results
/merge
```

### Integration Examples
```bash
# Load MCP server
/mcp load http://localhost:9876/sse burp

# Add MCP tools to agent
/mcp add-to-agent <agent_name> burp

# Set up virtualized environment
/virtualization create ubuntu:latest
/workspace /path/to/project
```

---

## Command Registration

All commands are automatically registered when their respective modules are imported through the `__init__.py` file. The command system uses a registry pattern to track all available commands and their aliases.

---

## File Structure

```
src/cai/repl/commands/
├── __init__.py          # Module exports and imports
├── base.py              # Base command class
├── agent.py             # Agent management
├── compact.py           # Conversation compaction
├── completer.py         # Command completion
├── config.py            # Configuration management
├── cost.py              # Cost tracking
├── env.py               # Environment variables
├── exit.py              # REPL exit
├── flush.py             # History clearing
├── graph.py             # Graph visualization
├── help.py              # Help system
├── history.py           # History management
├── kill.py              # Process management
├── load.py              # Data loading
├── mcp.py               # MCP integration
├── memory.py            # Memory management
├── merge.py             # History merging
├── model.py             # Model management
├── parallel.py          # Parallel execution
├── platform.py          # Platform features
├── quickstart.py        # User onboarding
├── run.py               # Parallel execution trigger
├── shell.py             # Shell access
├── virtualization.py    # Container management
└── workspace.py         # Workspace management
```

---

## Extending the Command System

To add new commands:

1. Create a new Python file in `src/cai/repl/commands/`
2. Import the base `Command` class from `base.py`
3. Extend the `Command` class with your implementation
4. Use the `register_command` decorator or function
5. Add the import to `__init__.py`

Example:
```python
from cai.repl.commands.base import Command, register_command

class MyCommand(Command):
    def __init__(self):
        super().__init__(
            name="/mycommand",
            description="My custom command",
            aliases=["/my", "/mc"]
        )
    
    def execute(self, args):
        # Command implementation
        pass

register_command(MyCommand())
```

