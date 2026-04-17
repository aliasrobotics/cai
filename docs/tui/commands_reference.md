# CAI TUI Commands Reference

> **⚡ CAI-Pro Exclusive Feature**  
> The Terminal User Interface (TUI) is available exclusively in **CAI-Pro**. To access this feature and unlock advanced multi-agent workflows, visit [Alias Robotics](https://aliasrobotics.com/cybersecurityai.php) for more information.

---

!!! tip "Recommended: use the CLI REPL"
    The command matrix for every `cai` binary flag and REPL slash command is maintained in the **[CLI commands reference](../cli/commands_reference.md)**. **When in doubt—especially for scripting, copy-paste examples, or comparing subcommands—use the plain CLI REPL** and the CLI reference. The TUI shares the same underlying engine; this document focuses on **multi-terminal UX**, keyboard shortcuts, palette actions, and behaviors that differ from the CLI.

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

## CLI parity and TUI-only differences

The [CLI commands reference](../cli/commands_reference.md) is the **authoritative** list for REPL slash commands. The TUI reuses the same slash commands, but a few interactions differ:


| Situation                                  | CLI REPL                                           | TUI                                                                                                                |
| ------------------------------------------ | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `/flush` or `/clear` with **no** arguments | Interactive menu of agents that still have history | Clears history for the **focused terminal only**                                                                   |
| `/agent` with no arguments                 | Same as `/agent current`                           | Shows the active agent configuration across terminals where applicable                                             |
| Screen vs history                          | N/A                                                | **Ctrl+L** / visual “clear” only affects scrollback; it does **not** replace `/flush` for wiping message history |


For binary flags such as `--tui`, `--yaml`, or `--api`, see [Binary `cai` CLI flags](../cli/commands_reference.md#binary-cai-cli-flags).

---

## Agent Management

### `/agent` or `/a`

Switch between agents or list all available agents.

!!! note "CLI reference vs TUI examples"
    The CLI reference documents `/agent` with explicit subcommands (`list`, `select`, `info`, `current`, …). In the TUI you will often see the shorthand `/agent <name>`; on many builds that is equivalent to `/agent select <name>`. For exact syntax and flags, follow the **[CLI commands reference](../cli/commands_reference.md#agent-a)**.

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

### `/history [number] [agent_name]` or `/his`

Display conversation history for the current or specified agent. (Use `/his` — `/h` is reserved for `/help` on builds that follow the documented alias table.)

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
/his 5
```

**Notes**:

- Default shows last 10 interactions
- History includes both user prompts and agent responses
- History is terminal-specific

### `/flush [agent_name|all]` or `/clear`

Clear agent message history (`/clear` is an alias of `/flush` for history, not the same as clearing the screen—see below).

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
- **TUI:** with **no** arguments, `/flush` typically affects only the **focused** terminal (see [CLI parity and TUI-only differences](#cli-parity-and-tui-only-differences)). The CLI may instead show a picker—confirm with `/help flush` on your build.

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

For spend and token usage use **`/cost`** (and the per-terminal cost UI in the TUI). When threads grow too long, use **`/compact`**. See the [CLI commands reference](../cli/commands_reference.md) for the full command list.

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

### Stopping work in the TUI

Use **Ctrl+C** to cancel the **current agent turn** or tool call in the focused terminal. Partial responses may be discarded depending on the tool; message history is preserved unless you also `/flush`. To signal an external PID, use **`/shell`** or **`$`** with the usual OS tools.

### `/clear` (scrollback)

Clear **visual** terminal output (scrollback) in the TUI.

**Syntax**:

```
/clear
```

**Keyboard Shortcut**: `Ctrl+L`

**Notes**:

- Clears visual output only
- **Does not** wipe conversation history—use `/flush` / `/clear` in the history sense (see above)
- Cost tracking continues

### `/exit` or `/quit` or `/q`

Leave the TUI session cleanly (telemetry flush, session teardown).

**Keyboard Shortcut**: `Ctrl+Q` (depending on build; confirm in-app shortcuts)

**Notes**:

- Unsaved work in buffers may be lost—`/save` or export logs first if needed
- Shuts down all terminals in the layout

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

- [CLI commands reference](../cli/commands_reference.md) — recommended for exact REPL syntax
- [Terminals Management](terminals_management.md) - Advanced multi-terminal workflows
- [Keyboard Shortcuts](keyboard_shortcuts.md) - Complete keyboard reference
- [User Interface Guide](user_interface.md) - Visual components and layouts

For questions or issues, visit [CAI GitHub Issues](https://github.com/aliasrobotics/cai/issues).

---

*TUI UX and shortcuts; authoritative slash-command tables: [CLI commands reference](../cli/commands_reference.md).*