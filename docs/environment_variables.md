# Environment Variables Reference

This comprehensive guide documents all environment variables available in CAI, including their purposes, default values, and usage examples.

---

## 📋 Complete Reference Table

| Variable | Description | Default |
|----------|-------------|---------|
| CTF_NAME | Name of the CTF challenge to run (e.g. "picoctf_static_flag") | - |
| CTF_CHALLENGE | Specific challenge name within the CTF to test | - |
| CTF_SUBNET | Network subnet for the CTF container | 192.168.3.0/24 |
| CTF_IP | IP address for the CTF container | 192.168.3.100 |
| CTF_INSIDE | Whether to conquer the CTF from within container | true |
| CAI_MODEL | Model to use for agents | alias1 |
| CAI_DEBUG | Set debug output level (0: Only tool outputs, 1: Verbose debug output, 2: CLI debug output) | 1 |
| CAI_BRIEF | Enable/disable brief output mode | false |
| CAI_MAX_TURNS | Maximum number of turns for agent interactions | inf |
| CAI_MAX_INTERACTIONS | Maximum number of interactions (tool calls, agent actions, etc.) allowed in a session. If exceeded, only CLI commands are allowed until increased. If force_until_flag=true, the session will exit | inf |
| CAI_PRICE_LIMIT | Price limit for the conversation in dollars. If exceeded, only CLI commands are allowed until increased. If force_until_flag=true, the session will exit | 1 |
| CAI_TRACING | Enable/disable OpenTelemetry tracing. When enabled, traces execution flow and agent interactions for debugging and analysis | true |
| CAI_AGENT_TYPE | Specify the agents to use (e.g., boot2root, one_tool, redteam_agent). Use "/agent" command in CLI to list all available agents | redteam_agent |
| CAI_STATE | Enable/disable stateful mode. When enabled, the agent will use a state agent to keep track of the state of the network and the flags found | false |
| CAI_MEMORY | Enable/disable memory mode (episodic: use episodic memory, semantic: use semantic memory, all: use both episodic and semantic memory) | false |
| CAI_MEMORY_ONLINE | Enable/disable online memory mode | false |
| CAI_MEMORY_OFFLINE | Enable/disable offline memory | false |
| CAI_ENV_CONTEXT | Add environment context, dirs and current env available | true |
| CAI_MEMORY_ONLINE_INTERVAL | Number of turns between online memory updates | 5 |
| CAI_SUPPORT_MODEL | Model to use for the support agent | o3-mini |
| CAI_SUPPORT_INTERVAL | Number of turns between support agent executions | 5 |
| CAI_STREAM | Enable/disable streaming output in rich panel | false |
| CAI_TELEMETRY | Enable/disable telemetry | true |
| CAI_PARALLEL | Number of parallel agent instances to run. When set to values greater than 1, executes multiple instances of the same agent in parallel and displays all results | 1 |
| CAI_GUARDRAILS | Enable/disable security guardrails for agents. When set to "true", applies security guardrails to prevent potentially dangerous outputs and inputs | false |
| CAI_GCTR_NITERATIONS | Number of tool interactions before triggering GCTR (Generative Cut-The-Rope) analysis in bug_bounter_gctr agent. Only applies when using gctr-enabled agents | 5 |
| CAI_ACTIVE_CONTAINER | Docker container ID where commands should be executed. When set, shell commands and tools execute inside the specified container instead of the host. Automatically set when CTF challenges start (if CTF_INSIDE=true) or when switching containers via /virtualization command | - |

---

## 🎯 Quick Reference by Use Case

### 🚀 Getting Started (Essential)

For first-time users, these are the essential variables to configure:

```bash
# Required: Model selection
CAI_MODEL="alias1"                    # or gpt-4o, claude-sonnet-4.5, ollama/qwen2.5:72b

# Recommended: Agent type
CAI_AGENT_TYPE="redteam_agent"        # See available agents with /agent command

# Optional but useful: Cost control
CAI_PRICE_LIMIT="1"                   # Maximum spend in dollars
```

**Related Documentation:**
- [Installation Guide](cai/getting-started/installation.md)
- [Configuration Guide](cai/getting-started/configuration.md)

---

### 🏴 CTF Challenges

For running Capture The Flag challenges in containerized environments:

```bash
# Challenge selection
CTF_NAME="picoctf_static_flag"        # Name of the CTF challenge
CTF_CHALLENGE="web_exploitation_1"    # Specific sub-challenge

# Network configuration
CTF_SUBNET="192.168.3.0/24"          # Container subnet
CTF_IP="192.168.3.100"               # Container IP address

# Execution mode
CTF_INSIDE="true"                     # Run agent inside container
```

**Best Practices:**
- Set `CTF_INSIDE=true` to run the agent inside the challenge container
- Use `CAI_ACTIVE_CONTAINER` to manually specify which container to execute commands in
- Combine with `CAI_STATE=true` to track discovered flags

**Related Documentation:**
- [CTF Benchmarks](benchmarking/jeopardy_ctfs.md)

---

### 🧠 Memory & State Management

For maintaining context across sessions and learning from past interactions:

```bash
# State tracking
CAI_STATE="true"                      # Enable network state tracking

# Memory modes
CAI_MEMORY="all"                      # Options: episodic, semantic, all, false
CAI_MEMORY_ONLINE="true"              # Enable online memory
CAI_MEMORY_OFFLINE="true"             # Enable offline memory

# Memory tuning
CAI_MEMORY_ONLINE_INTERVAL="5"       # Turns between memory updates
```

**Memory Modes Explained:**
- `episodic`: Remember specific past events and interactions
- `semantic`: Extract and store general knowledge
- `all`: Combine both episodic and semantic memory

**Related Documentation:**
- [Advanced Features](tui/advanced_features.md)

---

### 🛡️ Security & Safety

For enabling security guardrails and controlling agent behavior:

```bash
# Security guardrails
CAI_GUARDRAILS="true"                 # Prevent dangerous commands
CAI_PRICE_LIMIT="1"                   # Maximum cost in dollars
CAI_MAX_INTERACTIONS="inf"            # Maximum allowed interactions

# Debugging & monitoring
CAI_DEBUG="1"                         # 0: minimal, 1: verbose, 2: CLI debug
CAI_TRACING="true"                    # Enable OpenTelemetry tracing
```

**Security Layers:**
- **Guardrails**: Prompt injection detection and command validation
- **Cost Limits**: Prevent runaway API usage
- **Interaction Limits**: Control agent autonomy

**Related Documentation:**
- [Guardrails Documentation](guardrails.md)
- [TUI Advanced Features](tui/advanced_features.md)

---

### ⚡ Performance Optimization

For optimizing output, execution speed, and resource usage:

```bash
# Output control
CAI_BRIEF="true"                      # Concise output mode
CAI_STREAM="false"                    # Disable streaming for faster processing

# Context optimization
CAI_ENV_CONTEXT="true"                # Include environment in context
CAI_MAX_TURNS="50"                    # Limit conversation turns

# Telemetry
CAI_TELEMETRY="true"                  # Enable usage analytics
```

**Performance Tips:**
- Enable `CAI_BRIEF` for concise outputs in automated workflows
- Set `CAI_MAX_TURNS` to prevent infinite loops
- Use `CAI_STREAM=false` when output display is not needed

---

### 🔧 Advanced Agent Configuration

For specialized agents and complex workflows:

```bash
# Support agent (meta-reasoning)
CAI_SUPPORT_MODEL="o3-mini"          # Model for support agent
CAI_SUPPORT_INTERVAL="5"             # Turns between support executions

# Parallel execution
CAI_PARALLEL="3"                      # Run 3 agent instances simultaneously

# Specialized agents
CAI_GCTR_NITERATIONS="5"             # For bug_bounty_gctr agent
```

**Specialized Agent Variables:**
- `CAI_GCTR_NITERATIONS`: Controls Cut-The-Rope analysis frequency in GCTR agents
- `CAI_SUPPORT_MODEL`: Meta-agent for strategic planning
- `CAI_PARALLEL`: Swarm-style parallel agent execution

**Related Documentation:**
- [Agents Documentation](agents.md)
- [Teams & Parallel Execution](tui/teams_and_parallel_execution.md)

---

### 🐳 Container & Virtualization

For executing commands inside Docker containers:

```bash
# Container targeting
CAI_ACTIVE_CONTAINER="a1b2c3d4e5f6"  # Docker container ID

# Automatic with CTF
CTF_INSIDE="true"                     # Auto-set CAI_ACTIVE_CONTAINER on CTF start
```

**Container Execution:**
- When `CAI_ACTIVE_CONTAINER` is set, all shell commands execute inside that container
- Automatically configured when starting CTF challenges with `CTF_INSIDE=true`
- Switch containers using `/virtualization` command in CLI

**Related Documentation:**
- [Commands Reference](cai/getting-started/commands.md)

---

### 🖥️ TUI-Specific Configuration

For Terminal User Interface features and workflows:

```bash
# TUI display
CAI_STREAM="true"                     # Enable streaming in TUI panels
CAI_BRIEF="false"                     # Full output for interactive sessions

# TUI workflows
CAI_PARALLEL="1"                      # Usually 1 for TUI, use Teams feature instead
CAI_GUARDRAILS="false"                # Consider enabling for team workflows
```

**TUI Recommendations:**
- Set `CAI_STREAM=true` for better interactive experience
- Use built-in Teams feature instead of `CAI_PARALLEL`
- Enable `CAI_GUARDRAILS` when coordinating multiple agents

**Related Documentation:**
- [TUI Documentation](tui/tui_index.md)
- [TUI Getting Started](tui/getting_started.md)

---

## 💡 Common Configuration Examples

### Example 1: Local Development with Ollama

```bash
CAI_MODEL="ollama/qwen2.5:72b"
CAI_AGENT_TYPE="redteam_agent"
CAI_PRICE_LIMIT="0"
CAI_DEBUG="1"
CAI_GUARDRAILS="false"
```

### Example 2: Production CTF Solving

```bash
CTF_NAME="hackthebox_challenge"
CTF_INSIDE="true"
CAI_MODEL="alias1"
CAI_STATE="true"
CAI_MEMORY="all"
CAI_GUARDRAILS="true"
CAI_PRICE_LIMIT="5"
```

### Example 3: Pentesting with Cost Control

```bash
CAI_MODEL="gpt-4o"
CAI_AGENT_TYPE="redteam_agent"
CAI_PRICE_LIMIT="2"
CAI_MAX_INTERACTIONS="100"
CAI_GUARDRAILS="true"
CAI_BRIEF="false"
```

### Example 4: Parallel Testing (Non-TUI)

```bash
CAI_MODEL="alias0-fast"
CAI_PARALLEL="5"
CAI_BRIEF="true"
CAI_MAX_TURNS="20"
CAI_STREAM="false"
```

---

## 📚 Related Documentation

- [Configuration Guide](cai/getting-started/configuration.md) - Basic setup and API keys
- [Commands Reference](cai/getting-started/commands.md) - Available CLI commands
- [TUI Documentation](tui/tui_index.md) - Terminal User Interface features
- [Agents Documentation](agents.md) - Available agent types
- [Guardrails](guardrails.md) - Security and safety features

---

## ⚠️ Important Notes

### API Keys

CAI does NOT provide API keys for any model by default. Configure your own keys in the `.env` file:

```bash
OPENAI_API_KEY="sk-..."              # Required (can use "sk-123" as placeholder)
ANTHROPIC_API_KEY="sk-ant-..."       # For Claude models
ALIAS_API_KEY="sk-..."               # For alias1 (CAI PRO)
OLLAMA_API_BASE="http://localhost:11434/v1"  # For local models
```

See the [Configuration Guide](cai/getting-started/configuration.md) for more details.

### Setting Variables

There are three ways to configure environment variables:

**1. `.env` file (Recommended)**
```bash
# Add to .env file
CAI_MODEL="alias1"
CAI_PRICE_LIMIT="1"
```

**2. Command-line**
```bash
CAI_MODEL="gpt-4o" CAI_PRICE_LIMIT="2" cai
```

**3. Runtime configuration**
Use CLI commands to modify settings during execution. See [Commands Reference](cai/getting-started/commands.md).

