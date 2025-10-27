# CAI TUI User Interface

> **⚡ CAI-Pro Exclusive Feature**  
> The Terminal User Interface (TUI) is available exclusively in **CAI-Pro**. To access this feature and unlock advanced multi-agent workflows, visit [Alias Robotics](https://aliasrobotics.com) for more information.

---

This guide provides a detailed overview of the CAI TUI interface components and their functions.

## Interface Overview

The CAI TUI interface is divided into several key areas:


---

## Top Bar

The top bar provides global controls and information:

- **[≡] Menu Button**: Opens the command palette for quick access to all TUI commands
- **Terminal CTR Help**: Shows current help context and available shortcuts
- **[±] Maximize**: Toggles fullscreen mode for the active terminal
- **[×] Close**: Exits the TUI application

### Command Palette

Press `Ctrl+P` or click the menu button to open the command palette, which provides:

- Quick command search and execution
- Fuzzy matching for command names
- Keyboard navigation (arrow keys, Enter)
- Recent commands history
- Command descriptions and shortcuts

Available commands include:
- `clear` - Clear terminal output
- `save` - Save current session
- `load` - Load previous session
- `export` - Export conversation
- `reset` - Reset agent context
- `help` - Show help information

---

## Sidebar

The sidebar contains four main tabs accessible via mouse click or keyboard shortcuts (`Alt+1` through `Alt+4`):

### 1. Teams Tab (`Alt+1`)

The Teams tab displays preconfigured agent teams for parallel testing scenarios:

**Team Buttons**:
- Compact labels show team composition (e.g., `#1: 2 red + 2 bug`)
- Click to apply team configuration to all terminals
- Hover to see detailed tooltip with full agent names and terminal assignments

**Tooltip Information**:
- Team number and composition (e.g., "#2: 1 redteam_agent + 3 bug_bounter_agent")
- Terminal-by-terminal breakdown:
  - T1: redteam_agent
  - T2: bug_bounter_agent
  - T3: bug_bounter_agent
  - T4: bug_bounter_agent

**Available Teams**:
- **Team 1**: 2 Red Team + 2 Bug Bounty agents
- **Team 2**: 1 Red Team + 3 Bug Bounty agents
- **Team 3**: 2 Red Team + 2 Blue Team agents
- **Team 4**: 2 Blue Team + 2 Bug Bounty agents

When you select a team:
- All terminals are reconfigured automatically
- Agent dropdowns update to reflect new assignments
- Terminal headers show the assigned agent
- Previous conversations are preserved

### 2. Queue Tab (`Alt+2`)

The Queue tab manages prompt queuing and broadcast execution:

**Queue Management**:
- View all queued prompts
- Delete individual prompts
- Clear entire queue
- Execute queue sequentially

**Broadcast Mode**:
- Toggle broadcast mode on/off
- Send prompts to all terminals simultaneously
- Queue prompts for batch execution
- Monitor execution progress

**Queue Display**:
```
[1] Scan target.com for XSS vulnerabilities
[2] Check for SQL injection in login form
[3] Test API endpoints for authorization bypass
```


### 3. Stats Tab (`Alt+3`)

The Stats tab provides real-time cost tracking and usage statistics:

**Cost Information**:
- Total session cost (all terminals combined)
- Per-terminal cost breakdown
- Token usage (input/output)
- Model pricing details
- Cost per interaction

**Usage Metrics**:
- Number of interactions
- Total tokens consumed
- Average cost per turn
- Time elapsed
- Active terminals

**Example Display**:

```
Total Cost: $0.47
═══════════════════════
Terminal 1: $0.15 (3 interactions)
Terminal 2: $0.12 (2 interactions)
Terminal 3: $0.10 (2 interactions)
Terminal 4: $0.10 (2 interactions)
Model: alias1 ($0.015/1K in, $0.060/1K out)
Tokens: 1,240 input, 6,850 output
```


**Cost Limits**:
- Set via `CAI_PRICE_LIMIT` environment variable
- Warning when approaching limit
- Automatic pause when limit exceeded

### 4. Keys Tab (`Alt+4`)

The Keys tab displays and manages API key status:

**Key Information**:
- API key provider (OpenAI, Anthropic, etc.)
- Key validity status
- Last validation time
- Rate limit information

**Key Management**:
- View masked API keys
- Test key validity
- Update keys without restarting
- Environment variable status

**Example Display**:


---

## Terminal Components

Each terminal window consists of several components:

### Terminal Header

The header bar above each terminal shows:

- **Terminal Number**: T1, T2, T3, or T4
- **Agent Name**: Currently selected agent (e.g., `redteam_agent`)
- **Model Selector**: Dropdown to change LLM model (e.g., `alias1`, `gpt-4o`)
- **Container Icon**: Indicates if agent is running in container mode

**Agent Dropdown**:
- Click to open agent selection menu
- Shows all available agents
- Hover for agent description
- Keyboard navigation supported

**Model Dropdown**:
- Click to open model selection menu
- Shows configured models (alias0, alias1, gpt-4o, etc.)
- Displays model aliases and actual names
- Updates immediately upon selection

### Terminal Output Area

The main terminal display area shows:

**Agent Responses**:
- Formatted text with Rich markup support
- Syntax-highlighted code blocks
- Tables and structured data
- Progress indicators for long operations

**Tool Calls**:
- Tool name and parameters
- Execution status (running, success, error)
- Tool output and results
- Collapsed/expanded view for long outputs

**System Messages**:
- Agent initialization
- Context resets
- Error messages
- Cost warnings

**Streaming Display**:
- Real-time token streaming for LLM responses
- Progressive rendering of tool outputs
- Live progress indicators
- Smooth scrolling

**Example Output**:




### Terminal States

Terminals can be in different visual states:

**Active State**:
- Highlighted border (accent color)
- Ready to receive input
- Cursor visible in input area
- Responds to keyboard shortcuts

**Inactive State**:
- Dimmed border
- Background operations continue
- Click to activate
- Scrollable content

**Busy State**:
- Spinner or progress indicator
- "Working..." message
- Cannot send new prompts
- Cancel option available (`Ctrl+C`)

**Error State**:
- Red border or error indicator
- Error message displayed
- Retry option available
- Can clear and continue

---

## Terminal Layouts

The TUI supports multiple layout configurations for parallel agent execution:

### Single Terminal Layout

Default view showing one terminal at full width:






**Use Cases**:
- Single-agent workflows
- Detailed analysis requiring full screen
- Learning and experimentation

**Activation**: Automatically displayed when only one terminal is needed

### Split (Two Terminal) Layout

Side-by-side view for two terminals:



**Use Cases**:
- Comparing two agent approaches
- Red team vs. Blue team parallel execution
- Different model comparison

**Activation**: Triggered when using 2 terminals or Team 3/4

### Triple Terminal Layout

Three terminals with one full-width top terminal:




**Use Cases**:
- Full team operations (Teams 1-4)
- Maximum parallel execution
- Comprehensive testing scenarios
- Multi-perspective analysis

**Activation**: Default for preconfigured teams (Team 1, 2, 3, 4)

### Scrollable Layout

For more than 4 terminals (experimental):



**Use Cases**:
- Large-scale testing
- Custom configurations
- Advanced workflows

**Activation**: Manual configuration via startup YAML

---

## Status Bar

The bottom status bar displays global information:

**Left Section**:
- **Agent**: Currently active agent name
- **Model**: Currently active model
- **Cost**: Session total cost

**Center Section**:
- **Tokens**: Total tokens used (input/output)
- **Time**: Session duration
- **Interactions**: Number of completed turns

**Right Section**:
- **Status**: Connection status, errors, warnings
- **Mode**: Current mode (broadcast, queue, normal)
- **Shortcuts**: Context-sensitive keyboard hints

**Example**:

## Input Area

The input area at the bottom provides prompt entry and management:

### Prompt Input

**Features**:
- Multi-line input support (grows with content)
- Syntax highlighting for code snippets
- Placeholder text with hints
- Character counter for long prompts
- Auto-scrolling for long text

**Keyboard Shortcuts**:
- `Enter`: Submit prompt (single-line mode)
- `Shift+Enter`: New line (multi-line mode)
- `Ctrl+Enter`: Submit multi-line prompt
- `Ctrl+U`: Clear input
- `Up/Down`: Navigate command history

### Autocompletion

The TUI provides intelligent autocompletion for:

**Commands**:
- `/clear` - Clear terminal
- `/save` - Save session
- `/load` - Load session
- `/help` - Show help
- `/agent` - Switch agent
- `/model` - Switch model

**Agent Names**:
- Type `@` to trigger agent name completion
- Fuzzy matching supported
- Shows agent descriptions

**File Paths**:
- Type `/path/` to trigger path completion
- Shows recent files and directories
- Supports tab completion

**Example**:


---

## Responsive Design

The TUI adapts to different terminal sizes:

### Minimum Requirements
- **Width**: 80 columns minimum (120+ recommended)
- **Height**: 24 rows minimum (40+ recommended)

### Adaptive Behaviors

**Small Terminals (80×24)**:
- Sidebar collapses to icons only
- Single terminal view prioritized
- Compact status bar
- Abbreviated labels

**Medium Terminals (120×40)**:
- Full sidebar visible
- Split/Triple layouts available
- Standard spacing
- Full labels

**Large Terminals (160×50+)**:
- Quad layout comfortable
- Additional information displayed
- More breathing room
- Enhanced tooltips

### Dynamic Adjustments

The TUI automatically:
- Wraps long lines in terminal output
- Truncates button labels to fit width
- Adjusts table column widths
- Scales terminal grid based on available space
- Hides non-essential UI elements when space is limited

---

*Last updated: October 2025 | CAI TUI v0.6+*

