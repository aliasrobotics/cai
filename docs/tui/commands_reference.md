# CAI TUI Commands Reference

> **⚡ CAI-Pro Exclusive Feature**  
> The Terminal User Interface (TUI) is available exclusively in **CAI-Pro**. To access this feature and unlock advanced multi-agent workflows, visit [Alias Robotics](https://aliasrobotics.com/cybersecurityai.php) for more information.

---

This comprehensive guide documents all commands available in the CAI Terminal User Interface (TUI), including command palette actions, keyboard shortcuts, and CLI-style commands.

---

## Command Categories

CAI TUI commands are organized into the following categories:

1. [Agent Management](#agent-management)
2. [Model Management](#model-management)
3. [Terminal Control](#terminal-control)
4. [History and Memory](#history-and-memory)
5. [Session Management](#session-management)
6. [Utility Commands](#utility-commands)
7. [Navigation and UI](#navigation-and-ui)

---

## Agent Management

### `/agent` or `/a`

Switch between agents or list all available agents.

**Syntax**:
```
/agent [agent_name]
/a [agent_name]
```

**Examples**:
```bash
# List all available agents
/agent

# Switch to red team agent
/agent redteam_agent

# Switch to bug bounty agent
/a bug_bounter_agent
```

**Available Agents**:
- `redteam_agent` - Offensive security testing and penetration testing
- `blueteam_agent` - Defensive security analysis and hardening
- `bug_bounter_agent` - Bug bounty hunting and vulnerability research
- `retester_agent` - Retesting and validation of vulnerabilities
- `one_tool_agent` - Basic single-tool execution (minimalist approach)
- `dfir_agent` - Digital forensics and incident response
- `reporting_agent` - Report generation and security documentation
- `reverse_engineering_agent` - Binary analysis and reverse engineering
- `network_security_analyzer_agent` - Network security assessment
- `wifi_security_agent` - WiFi security testing and wireless analysis
- `memory_analysis_agent` - Memory forensics and analysis
- `dns_smtp_agent` - DNS and SMTP protocol analysis
- `replay_attack_agent` - Replay attack testing and analysis
- `subghz_sdr_agent` - Sub-GHz and Software Defined Radio (SDR) analysis
- `thought_agent` - Reasoning, planning, and analysis
- `use_case_agent` - Use case analysis and scenario planning
- `flag_discriminator` - CTF flag identification and discrimination
- `cybersecurity_engineer` - Cybersecurity engineering and architecture
- `selection_agent` - Intelligent agent selection and routing
- `bb_triage_swarm_pattern` - Bug bounty triage swarm pattern
- `redteam_swarm_pattern` - Red team swarm coordination pattern
- `offsec_pattern` - Offensive security pattern orchestration

**Notes**:
- Agent changes are immediate and affect only the active terminal
- Each terminal can run a different agent simultaneously
- Agent context is preserved when switching between terminals

---

## Model Management

### Model Selection via Dropdown

CAI TUI uses model dropdowns in each terminal header for model management. Models are configured via environment variables and aliases.

**Available Models**:
- `alias1` - Cybersecurity focus model [Recommended]
- `gpt-4o` - OpenAI GPT-4 Optimized
- `gpt-4-turbo` - OpenAI GPT-4 Turbo
- `claude-3-5-sonnet-20241022` - Anthropic Claude 3.5 Sonnet
- `o1-mini` - OpenAI O1 Mini
- `o1-preview` - OpenAI O1 Preview

**How to Change Models**:
1. Click the model dropdown in any terminal header
2. Select desired model from the list
3. Model change takes effect immediately for that terminal

**Environment Variables**:
```bash
export CAI_MODEL=gpt-4o              # Set default model
export CAI_OPENAI_API_KEY=sk-...    # OpenAI API key
export CAI_ANTHROPIC_API_KEY=sk-... # Anthropic API key
```

**Notes**:
- Each terminal can use a different model
- Model costs are tracked separately per terminal
- Switching models mid-conversation preserves history

---

## Terminal Control

### Terminal-Specific Commands

Send commands to specific terminals using either the prefix notation or the flag notation.

#### Method 1: Prefix Notation

**Syntax**:
```
T<terminal_number>:<command>
```

**Examples**:
```bash
# Switch agent in Terminal 2
T2:/agent blueteam_agent

# Change model in Terminal 3
T3:/model alias1

# Clear Terminal 1
T1:/clear

# Execute command in Terminal 4
T4:scan target.com for vulnerabilities
```
#### Method 2: Flag Notation

**Syntax**:

```
<command> t<terminal_number>

```

**Examples**:
```bash
# Switch agent in Terminal 2
/agent blueteam_agent t2

# Change model in Terminal 3
/model alias1 t3

# Clear Terminal 1
/clear t1

# Execute any command in Terminal 4
/help t4

# Send prompt to Terminal 2
Scan target.com for XSS vulnerabilities t2
```

**Supported Flags**:
- `t1` - Target Terminal 1
- `t2` - Target Terminal 2
- `t3` - Target Terminal 3
- `t4` - Target Terminal 4
- (Additional terminals if configured: `t5`, `t6`, etc.)

**Notes**:
- Both methods achieve the same result
- Flag notation is more concise for quick commands
- Prefix notation is clearer for complex prompts
- You can target any terminal without focusing it first
- Useful for scripting and automation
- Works with all commands (slash commands and prompts)

**Keyboard Shortcut**: Click the `[+]` button in the top bar

**Notes**:
- New terminals start with `redteam_agent` by default
- Maximum recommended terminals: 4 (for optimal UX)
- Terminals beyond 4 use scrollable layout

---

## History and Memory

### `/history [number] [agent_name]` or `/h`

Display conversation history for the current or specified agent.

**Syntax**:
```
/history [number] [agent_name]
```

**Examples**:
```bash
# Show last 10 messages
/history

# Show last 20 messages
/history 20

# Show history for specific agent
/history 10 redteam_agent

# Compact syntax
/h 5
```

**Notes**:
- Default shows last 10 interactions
- History includes both user prompts and agent responses
- History is terminal-specific

### `/flush [agent_name|all]`

Clear agent message history.

**Syntax**:
```
/flush [agent_name|all]
```

**Examples**:
```bash
# Flush current agent history
/flush

# Flush specific agent
/flush redteam_agent

# Flush all agents
/flush all
```

**Notes**:
- Flushing is irreversible
- Agent context window is reset
- Useful for starting fresh conversations

### `/memory [subcommand]` or `/mem`

Advanced memory management for agents.

**Syntax**:
```
/memory <subcommand>
/mem <subcommand>
```

**Subcommands**:

#### `list`
Show all saved memories.
```bash
/memory list
```

#### `save [name]`
Save current conversation as a memory.
```bash
/memory save "Authentication bypass research"
/mem save pentest_findings
```

#### `apply <memory_id>`
Apply a saved memory to the current agent.
```bash
/memory apply mem_12345
```

#### `show <memory_id>`
Display the content of a specific memory.
```bash
/memory show mem_12345
```

#### `delete <memory_id>`
Remove a memory permanently.
```bash
/memory delete mem_12345
```

#### `merge <id1> <id2> [name]`
Combine two memories into one.
```bash
/memory merge mem_12345 mem_67890 "Combined pentesting notes"
```

#### `compact`
AI-powered memory summarization.
```bash
/memory compact
```

#### `status`
Show memory system status and statistics.
```bash
/memory status
```

**Notes**:
- Memories persist across sessions
- Useful for resuming long-term research projects
- AI-powered summarization reduces token usage

---

## Session Management

### `/save <filename>`

Save the current conversation to a file.

**Syntax**:
```
/save <filename>
```

**Supported Formats**:
- JSON (`.json`)
- Markdown (`.md`)

**Examples**:
```bash
# Save as JSON
/save pentest_session.json

# Save as Markdown
/save findings_report.md

# Save with full path
/save ~/Documents/cai_sessions/project_alpha.json
```

**Notes**:
- Saves all terminal conversations
- Includes agent names, models, and timestamps
- Cost information is preserved

### `/load <filename>` or `/l`

Load a previously saved conversation.

**Syntax**:
```
/load <filename>
/l <filename>
```

**Examples**:
```bash
# Load JSON session
/load pentest_session.json

# Load Markdown report
/load findings_report.md

# Compact syntax
/l ~/cai_sessions/old_session.json
```

**Notes**:
- Restores agent context and history
- Compatible with both JSON and Markdown formats
- Loading does not affect current cost tracking

---

## Utility Commands

### `/context [agent_name]` or `/ctx` 🚀 **CAI PRO Exclusive**

> **⚡ CAI PRO Exclusive Feature**
> The `/context` command is available exclusively in **[CAI PRO](https://aliasrobotics.com/cybersecurityai.php)**. To access this feature and unlock advanced monitoring capabilities, visit [Alias Robotics](https://aliasrobotics.com/cybersecurityai.php) for more information.

Display context window usage and token statistics for the current conversation.

**Syntax**:
```
/context [agent_name]
/ctx [agent_name]
```

**Examples**:
```bash
# Show context usage for active terminal
/context

# Show context usage for specific agent
/context redteam_agent

# Compact syntax
/ctx
```

**Output Includes**:
- Total context usage (used/max tokens) with percentage
- Visual grid representation with CAI logo
- Breakdown by category:
  - System prompt tokens
  - Tool definitions tokens
  - Memory files (RAG) tokens
  - User prompts tokens
  - Assistant responses tokens
  - Tool calls tokens
  - Tool results tokens
- Free space available
- Color-coded visualization for easy identification

**Notes**:
- Context usage helps monitor when you're approaching model limits
- Different models have different context windows (e.g., GPT-4: 128k, Claude: 200k)
- Use `/context` regularly during long conversations to avoid hitting limits
- Context usage is terminal-specific in TUI mode

### `/cost [agent_name]`

Display API usage costs and token statistics.

**Syntax**:
```
/cost [agent_name]
```

**Examples**:
```bash
# Show costs for active terminal
/cost

# Show costs for specific agent
/cost redteam_agent

# Show total session costs
/cost all
```

**Output Includes**:
- Total cost (USD)
- Input tokens used
- Output tokens used
- Cost per interaction
- Model pricing rates
- Terminal breakdown

### `/help [command]` or `/?`

Get help for commands.

**Syntax**:
```
/help [command]
/? [command]
```

**Examples**:
```bash
# General help
/help

# Help for specific command
/help agent
/help parallel
/? mcp
```

### `/env`

Display environment variables relevant to CAI.

**Syntax**:
```
/env
```

**Output Includes**:
- `CAI_MODEL` - Default model
- `CAI_AGENT_TYPE` - Default agent
- `CAI_MAX_TURNS` - Maximum interaction turns
- `CAI_TRACING` - Tracing status
- `CAI_GUARDRAILS` - Guardrails enabled
- `CAI_PRICE_LIMIT` - Cost limit
- `CAI_TUI_MODE` - TUI mode settings
- API keys (masked)

### `/shell` or `$`

Execute shell commands directly from the TUI.

**Syntax**:
```
/shell <command>
$<command>
```

**Examples**:
```bash
# List files
/shell ls -la

# Check network
$ping -c 3 target.com

# Run nmap scan
$nmap -sV 192.168.1.1
```

**Notes**:
- Commands execute in the system shell
- Output is displayed in the terminal
- Use with caution - no sandboxing

### `/kill`

Terminate the currently executing agent operation.

**Syntax**:
```
/kill
```

**Keyboard Shortcut**: `Ctrl+C`

**Notes**:
- Stops agent mid-execution
- Partial responses are discarded
- Agent context is preserved

### `/clear`

Clear the terminal output.

**Syntax**:
```
/clear
```

**Keyboard Shortcut**: `Ctrl+L`

**Notes**:
- Clears visual output only
- Conversation history is preserved
- Cost tracking continues


**Keyboard Shortcut**: `Ctrl+Q`

**Notes**:
- Unsaved sessions will be lost
- Graceful shutdown of all terminals

---

## Navigation and UI

### Command Palette

Access the command palette for quick command search and execution.

**Keyboard Shortcut**: `Ctrl+P`

**Features**:
- Fuzzy search for commands
- Command descriptions
- Keyboard navigation (arrow keys, Enter)
- Recent commands
- Theme switching

### Sidebar Toggle

Show or hide the sidebar.

**Keyboard Shortcut**: `Ctrl+S`

**Alternative**: Click the `[≡]` button in the top bar


### Clear Input

Clear the prompt input field.

**Keyboard Shortcut**: `Ctrl+U`

**Use Cases**:
- Parallel agent execution
- Comparing agent responses
- Team-based workflows

### Cancel Operations

Cancel running operations.

**Keyboard Shortcuts**:
- `Ctrl+C` - Cancel execution in focused terminal
- `Escape` - Cancel all running agents (press twice to exit)

---

## Next Steps

- [Terminals Management](terminals_management.md) - Advanced multi-terminal workflows
- [Keyboard Shortcuts](keyboard_shortcuts.md) - Complete keyboard reference
- [User Interface Guide](user_interface.md) - Visual components and layouts

For questions or issues, visit [CAI GitHub Issues](https://github.com/aliasrobotics/cai/issues).

---

*Last updated: October 2025 | CAI TUI v0.6+*

