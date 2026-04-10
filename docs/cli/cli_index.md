# CAI Command Line Interface (CLI)

The CAI CLI provides a powerful, terminal-based interface for interacting with cybersecurity AI agents through a traditional command-line environment, optimized for automation, scripting, and integration workflows.

```
          CCCCCCCCCCCCC      ++++++++   ++++++++      IIIIIIIIII
       CCC::::::::::::C  ++++++++++       ++++++++++  I::::::::I
     CC:::::::::::::::C ++++++++++         ++++++++++ I::::::::I
    C:::::CCCCCCCC::::C +++++++++    ++     +++++++++ II::::::II
   C:::::C       CCCCCC +++++++     +++++     +++++++   I::::I
  C:::::C                +++++     +++++++     +++++    I::::I
  C:::::C                ++++                   ++++    I::::I
  C:::::C                 ++                     ++     I::::I
  C:::::C                  +   +++++++++++++++   +      I::::I
  C:::::C                    +++++++++++++++++++        I::::I
  C:::::C                     +++++++++++++++++         I::::I
   C:::::C       CCCCCC        +++++++++++++++          I::::I
    C:::::CCCCCCCC::::C         +++++++++++++         II::::::II
     CC:::::::::::::::C           +++++++++           I::::::::I
       CCC::::::::::::C             +++++             I::::::::I
          CCCCCCCCCCCCC               ++              IIIIIIIIII

                      Cybersecurity AI (CAI), v0.6.0
                          Bug bounty-ready AI

CAI>
```

## Overview

The CLI is the foundational interface for CAI, offering:

- **⚡ Lightweight Execution**: Minimal resource overhead for maximum performance
- **🤖 Direct Agent Interaction**: Immediate access to all CAI agents
- **📝 Command System**: 30+ built-in commands for complete control
- **🔄 Automation Ready**: Perfect for scripting and CI/CD pipelines
- **🧩 Queue System**: Batch processing with command chaining
- **⚙️ Parallel Execution**: Run multiple agents simultaneously
- **💾 Session Management**: Save and restore conversations
- **🔧 Shell Integration**: Direct shell command execution

## When to Use the CLI vs TUI

| Feature | CLI | TUI |
|---------|-----|-----|
| **Scripting/Automation** | ✅ Full support | ❌ Interactive only |
| **CI/CD Integration** | ✅ Perfect fit | ❌ Not suitable |
| **Resource Usage** | ✅ Minimal | ⚠️ Higher (UI overhead) |
| **Batch Processing** | ✅ Queue system | ⚠️ Limited |
| **Visual Feedback** | ⚠️ Text-based | ✅ Rich UI |
| **Multi-agent Workflows** | ✅ Parallel mode | ✅ Visual split-screen |
| **Remote/Headless** | ✅ SSH friendly | ⚠️ Requires terminal UI |
| **Learning Curve** | ⚠️ Steeper | ✅ Intuitive |

**Use CLI for**: Automation, scripting, CI/CD, headless servers, SSH sessions, batch processing

**Use TUI for**: Interactive testing, visual multi-agent workflows, exploratory analysis, real-time monitoring

## Quick Start

Launch the CLI:

```bash
cai
```

With an initial prompt:

```bash
cai --prompt "scan 192.168.1.1 for open ports"
```

With YAML configuration:

```bash
cai --yaml agents.yaml
```

Basic workflow:

1. Launch CAI: `cai`
2. Configure API key in `.env` or environment
3. Select a model: `/model alias1`
4. Choose an agent: `/agent redteam_agent`
5. Type your prompt and press **Enter**

See the [Getting Started Guide](getting_started.md) for detailed instructions.

## Key Features

### 🎯 Command System

Over 30 built-in commands organized by category:

- **Agent Management**: `/agent`, `/parallel`, `/run`
- **Memory & History**: `/memory`, `/history`, `/compact`, `/flush`, `/load`, `/merge`
- **Environment & Config**: `/config`, `/env`, `/help var` (per-variable help), `/workspace`, `/virtualization`
- **Tools & Integration**: `/mcp`, `/platform`, `/shell`
- **Utilities**: `/model`, `/graph`, `/context`, `/cost`, `/help`

All commands support aliases for faster typing (e.g., `/a` for `/agent`, `/h` for `/help`).

Learn more: [Commands Reference](commands_reference.md)


### ⚡ Parallel Execution

Run multiple agents simultaneously:

```bash
# Configure parallel agents
/parallel add redteam_agent
/parallel add bug_bounter_agent
/parallel add blueteam_agent

# Execute on all agents
/parallel run "analyze target.com"
```

Or use YAML configuration:

```bash
cai --yaml agents.yaml --prompt "test application security"
```

Learn more: [Advanced Usage](advanced_usage.md)

### 💻 Shell Integration

Execute shell commands directly:

```bash
# Using /shell command
/shell nmap -sV 192.168.1.1

# Using $ shortcut
$ whoami

# Using /$ alias
/$ ls -la
```

### 💾 Session Management

Save and restore conversations:

```bash
# Save current session
/save pentest_session.json

# Save as Markdown report
/save findings_report.md

# Load previous session
/load pentest_session.json
```

### 🧠 Memory Management

Advanced memory features for long-term context:

```bash
# Enable episodic memory
CAI_MEMORY=episodic cai

# Save memory snapshot
/memory save "web app vulnerabilities found"

# List saved memories
/memory list

# Apply memory to current session
/memory apply mem_12345
```

## System Requirements

- **Python**: 3.9 or higher
- **Terminal**: Any modern terminal (bash, zsh, fish)
- **API Key**: Valid `ALIAS_API_KEY` (get one from [Alias Robotics](https://aliasrobotics.com))
- **Operating System**: Linux, macOS, Windows (WSL recommended)

### Supported Terminals

- ✅ bash (Linux/macOS/WSL)
- ✅ zsh (macOS/Linux)
- ✅ fish (Linux/macOS)
- ✅ PowerShell (Windows)
- ✅ SSH sessions
- ✅ tmux/screen
- ✅ CI/CD environments

## Architecture

```
CAI CLI
├── Core Components
│   ├── run_cai_cli - Main interactive loop
│   ├── AgentManager - Agent lifecycle management
│   ├── CommandRegistry - Command routing and execution
│   └── SessionRecorder - Session logging and persistence
├── Command System
│   ├── AgentCommand - Agent switching and management
│   ├── ParallelCommand - Multi-agent coordination
│   ├── MCPCommand - External tool integration
│   ├── ConfigCommand - Environment management
│   └── 25+ additional commands
└── Integration Layer
    ├── PromptToolkit - Input handling and completion
    ├── FuzzyCompleter - Intelligent autocompletion
    ├── QueueManager - Batch execution
    └── ShellExecutor - Direct shell access
```

For technical details, see the [Architecture Overview](../cai_architecture.md).

## Common Use Cases

### 1. CTF Challenges

```bash
# Set up CTF environment
export CTF_NAME="hackableii"
export CTF_CHALLENGE="web_challenge"
export CAI_AGENT_TYPE="redteam_agent"

# Launch with auto-execution
cai --prompt "analyze the challenge and find the flag"
```

### 2. Bug Bounty Automation

```bash
# Configure bug bounty workflow
/agent bug_bounter_agent
/model alias1

# Execute reconnaissance
Perform full reconnaissance on bugcrowd.example.com
```

### 3. CI/CD Security Testing

```bash
#!/bin/bash
# security-check.sh

export CAI_MAX_TURNS=10
export CAI_PRICE_LIMIT=5.0
export CAI_TRACING=false

cai --prompt "scan $CI_TARGET for OWASP Top 10 vulnerabilities ; generate JSON report" > security-report.json
```

### 4. Parallel Reconnaissance

```bash
# agents.yaml
agents:
  - name: subdomain_scanner
    agent_type: redteam_agent
    model: alias1
  - name: port_scanner
    agent_type: network_security_analyzer_agent
    model: alias1
  - name: vulnerability_checker
    agent_type: bug_bounter_agent
    model: alias1

# Execute
cai --yaml agents.yaml --prompt "full reconnaissance on target.com"
```

## Quick Reference

### Essential Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/agent list` | List all agents | `/agent list` |
| `/agent <name>` | Switch agent | `/agent redteam_agent` |
| `/model <name>` | Change model | `/model alias1` |
| `/config` | View configuration | `/config` |
| `/help` | Show help | `/help agent` |
| `/save <file>` | Save session | `/save session.json` |
| `/load <file>` | Load session | `/load session.json` |
| `/cost` | Show costs | `/cost` |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Tab` | Autocomplete commands |
| `↑/↓` | Navigate command history |
| `Ctrl+C` | Interrupt execution |
| `Ctrl+L` | Clear screen |
| `Ctrl+D` | Exit CAI |
| `Ctrl+Z` | Suspend process |
| `Ctrl+X Ctrl+E` | Open editor |

See the complete [Commands Reference](commands_reference.md) for all commands.

## Configuration

CAI CLI can be configured via:

1. **Environment Variables**: `CAI_MODEL`, `CAI_AGENT_TYPE`, etc.
2. **`.env` File**: Place in your working directory
3. **`/config` Command**: Runtime configuration changes
4. **YAML Files**: Agent and workflow definitions

Example `.env`:

```env
ALIAS_API_KEY=ak_live_1234567890abcdef
CAI_MODEL=alias1
CAI_AGENT_TYPE=redteam_agent
CAI_DEBUG=1
CAI_PRICE_LIMIT=10.0
CAI_MAX_TURNS=50
```

For all configuration options, see [Configuration Guide](../getting-started/configuration.md).

## Documentation Structure

### For New Users
1. [Getting Started](getting_started.md) - First steps and basic usage
2. [Commands Reference](commands_reference.md) - Essential commands

### For Advanced Users
3. [Commands Reference](commands_reference.md) - Complete command list
4. [Advanced Usage](advanced_usage.md) - Automation, scripting, and advanced features

### Related Documentation
- [Configuration Guide](../getting-started/configuration.md) - All environment variables
- [Architecture Overview](../cai_architecture.md) - Technical architecture
- [TUI Documentation](../tui/tui_index.md) - Terminal UI alternative

## Community and Support

- **Documentation**: [https://docs.aliasrobotics.com](https://docs.aliasrobotics.com)
- **GitHub Issues**: [https://github.com/aliasrobotics/cai/issues](https://github.com/aliasrobotics/cai/issues)
- **Discord**: [Join our community](https://discord.gg/aliasrobotics)
- **Twitter**: [@aliasrobotics](https://twitter.com/aliasrobotics)

## What's Next?

- 📖 [Getting Started Guide](getting_started.md) - Learn the basics
- 📚 [Commands Reference](commands_reference.md) - Master all commands
- 🚀 [Advanced Usage](advanced_usage.md) - Unlock powerful features

---

*Last updated: November 2025 | CAI CLI v0.6+*

