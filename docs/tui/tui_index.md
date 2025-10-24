# CAI Terminal User Interface (TUI)

The CAI TUI provides a modern, terminal-based interface for interacting with CAI agents, enabling powerful multi-agent workflows, parallel execution, and advanced security testing capabilities.

![CAI TUI Interface](../media/cai-tui-main.png)

## Overview

The TUI is built on [Textual](https://textual.textualize.io/), offering:

- **🖥️ Multi-Terminal Support**: Work with up to 4 agents simultaneously in split-screen layouts
- **👥 Preconfigured Teams**: One-click deployment of specialized agent teams for security assessments
- **⚡ Parallel Execution**: Execute multiple agents in parallel with independent conversations
- **📊 Real-Time Stats**: Monitor costs, tokens, and agent performance
- **🎯 Smart Agent Selection**: Built-in agent recommendation system
- **🔧 MCP Integration**: Connect to external tools via Model Context Protocol
- **💾 Session Management**: Save and restore conversations across sessions

## When to Use the TUI vs CLI

| Feature | TUI | CLI |
|---------|-----|-----|
| **Visual feedback** | ✅ Rich UI with colors and layouts | ⚠️ Basic text output |
| **Multi-agent workflows** | ✅ Visual split-screen | ❌ Sequential only |
| **Agent teams** | ✅ One-click preconfigured teams | ❌ Manual setup |
| **Real-time monitoring** | ✅ Stats sidebar | ⚠️ Limited |
| **Session management** | ✅ Visual queue and history | ⚠️ Command-based |
| **Scripting/Automation** | ❌ Interactive only | ✅ Full scripting support |
| **Resource usage** | ⚠️ Higher (UI overhead) | ✅ Minimal |

**Use TUI for**: Interactive security testing, bug bounty hunting, team-based analysis, exploratory testing

**Use CLI for**: Automation, scripting, CI/CD integration, headless environments

## Quick Start

Launch the TUI:

```bash
cai --tui
```

Basic workflow:

1. Configure your `ALIAS_API_KEY` in **Sidebar → Keys**
2. Select a model (recommended: `alias1`) from the terminal header dropdown
3. Choose an agent or use `selection_agent` for recommendations
4. Type your prompt and press **Enter**

See the [Getting Started Guide](getting-started.md) for detailed instructions.

## System Requirements

- **Python**: 3.9 or higher
- **Terminal**: Modern terminal with 256+ color support
- **Minimum window size**: 120x40 characters (recommended)
- **API Key**: Valid `ALIAS_API_KEY` (get one from [Alias Robotics](https://aliasrobotics.com))

### Supported Terminals

- ✅ iTerm2 (macOS)
- ✅ Terminal.app (macOS)
- ✅ GNOME Terminal (Linux)
- ✅ Konsole (Linux)
- ✅ Windows Terminal (Windows)
- ✅ Alacritty (all platforms)
- ⚠️ tmux/screen (limited color support)

## Key Features

### 🖥️ Multiple Terminals

Work with multiple agents simultaneously in responsive layouts:

- **1 terminal**: Full-screen mode
- **2 terminals**: Horizontal split
- **3 terminals**: 2+1 grid layout
- **4+ terminals**: 2x2 grid with scroll

Each terminal maintains its own:
- Independent agent and model selection
- Isolated conversation history
- Separate execution context

Learn more: [Terminals Management](terminals-management.md)

### 👥 Preconfigured Teams

Access specialized agent teams from the sidebar:

- **Team: 2 Red + 2 Bug**: Offensive testing + bug hunting
- **Team: 2 Red + 2 Blue**: Dual-perspective security analysis
- **Team: Red + Blue + Retester + Bug**: Comprehensive assessment workflow

Learn more: [Teams and Parallel Execution](teams-and-parallel-execution.md)

### 🎯 Smart Agent Selection

Use the `selection_agent` to get intelligent agent recommendations based on your task:

```
/agent selection_agent
```

Or simply select it from the agent dropdown.

Learn more: [Commands Reference](commands-reference.md)

### 📊 Sidebar Features

The collapsible sidebar (`Ctrl+S`) provides:

- **Teams**: One-click team deployment
- **Queue**: Visual prompt queue management
- **Stats**: Real-time session statistics and costs
- **Keys**: Manage API keys for multiple providers

Learn more: [Sidebar Features](sidebar-features.md)

## Documentation Structure

### For New Users
1. [Getting Started](getting-started.md) - First steps and basic usage
2. [User Interface](user-interface.md) - Understanding the layout
3. [Keyboard Shortcuts](keyboard-shortcuts.md) - Essential shortcuts

### For Regular Users
4. [Commands Reference](commands-reference.md) - Complete command list
5. [Terminals Management](terminals-management.md) - Working with multiple terminals
6. [Sidebar Features](sidebar-features.md) - Sidebar tabs and capabilities

### For Advanced Users
7. [Teams and Parallel Execution](teams-and-parallel-execution.md) - Multi-agent workflows
8. [Configuration](configuration.md) - Environment variables and settings
9. [Advanced Features](advanced-features.md) - MCP, Meta Agent, and more

### Support Resources
10. [Troubleshooting](troubleshooting.md) - Common issues and solutions
11. [FAQ](faq.md) - Frequently asked questions

## Quick Reference

### Essential Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+S` | Toggle sidebar |
| `Ctrl+L` | Clear all terminals |
| `Ctrl+Q` | Exit CAI |
| `Ctrl+N` / `Ctrl+B` | Navigate terminals |
| `Ctrl+C` | Cancel current agent |
| `ESC` | Cancel all agents |

See all shortcuts: [Keyboard Shortcuts Reference](keyboard-shortcuts.md)

### Most Used Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/agent list` | List all agents |
| `/agent <name>` | Switch agent |
| `/model <name>` | Change model |
| `/queue` | Show prompt queue |
| `/cost` | Show costs and tokens |
| `/save <file>` | Save conversation |
| `/load <file>` | Load conversation |

See all commands: [Commands Reference](commands-reference.md)

## Architecture

```
CAI TUI
├── Core Components
│   ├── SessionManager - Coordinates all terminals
│   ├── TerminalRunner - Manages agent execution per terminal
│   └── AgentExecutor - Handles parallel execution
├── UI Components
│   ├── UniversalTerminal - Individual terminal widget
│   ├── StableTerminalGrid - Layout manager
│   ├── Sidebar - Navigation and features
│   └── InfoStatusBar - Real-time status display
└── Display System
    ├── DisplayManager - Output routing
    ├── StreamingDisplay - Real-time streaming
    └── AgentDisplay - Agent message formatting
```

For technical details, see the [Architecture Overview](../cai_architecture.md).

## Community and Support

- **Documentation**: [https://docs.aliasrobotics.com](https://docs.aliasrobotics.com)
- **GitHub Issues**: [https://github.com/aliasrobotics/cai/issues](https://github.com/aliasrobotics/cai/issues)
- **Discord**: [Join our community](https://discord.gg/aliasrobotics)
- **Twitter**: [@aliasrobotics](https://twitter.com/aliasrobotics)

## What's Next?

- 📖 [Getting Started Guide](getting-started.md) - Learn the basics
- ⌨️ [Keyboard Shortcuts](keyboard-shortcuts.md) - Boost your productivity
- 🎯 [Commands Reference](commands-reference.md) - Master the commands
- 👥 [Teams and Parallel Execution](teams-and-parallel-execution.md) - Advanced workflows

---

*Last updated: October 2025 | CAI TUI v0.6+*

