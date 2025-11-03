# CAI TUI Keyboard Shortcuts

> **⚡ CAI-Pro Exclusive Feature**  
> The Terminal User Interface (TUI) is available exclusively in **CAI-Pro**. To access this feature and unlock advanced multi-agent workflows, visit [Alias Robotics](https://aliasrobotics.com/cybersecurityai.php) for more information.

---

Master the CAI TUI with these keyboard shortcuts for maximum productivity. All shortcuts work across different terminal operating systems.


## Navigation Shortcuts

### Sidebar

| Shortcut | Action | Details |
|----------|--------|---------|
| `Ctrl+S` | Toggle sidebar | Opens/closes the sidebar panel |

**Usage**:
- Quick access to Teams, Queue, Stats, and Keys
- Sidebar state persists during session
- Width: 32 characters when open

**Alternative**: Click the `☰` button in the top-left corner

---

### Terminal Navigation

| Shortcut | Action | Details |
|----------|--------|---------|
| `Ctrl+N` | Next terminal | Cycles forward through terminals (1→2→3→4→1) |
| `Ctrl+B` | Previous terminal | Cycles backward through terminals (1→4→3→2→1) |

**Usage**:
- Focus moves to the next/previous terminal
- Visual indicator shows active terminal
- Works even when sidebar is open

**Alternative**: Click directly on any terminal to focus it

---

## Terminal Management

### Opening Terminals

| Shortcut | Action | Details |
|----------|--------|---------|
| Click `Add +` button | Add terminal | Creates new terminal with default settings |


**Default Settings**:
- Agent: `redteam_agent`
- Model: `alias1`
- Container: `local`

---

### Closing Terminals

| Shortcut | Action | Details |
|----------|--------|---------|
| `Ctrl+E` | Close current terminal | Closes the focused terminal |

**Alternative**: Click directly on specific close terminal button.

**Notes**:
- Terminal 1 cannot be closed (main terminal)
- Closing removes conversation history (save with `/save` first)
- Remaining terminals re-layout automatically

---

### Clearing Terminals

| Shortcut | Action | Details |
|----------|--------|---------|
| `Ctrl+L` | Clear all terminals | Removes output from all terminal screens |
| `/clear` | Clear current terminal | Command to clear focused terminal only |

**Notes**:
- Only clears visual output, not conversation history
- Use `/flush` to clear conversation history

## Execution Control

### Canceling Agents

| Shortcut | Action | Details |
|----------|--------|---------|
| `Ctrl+C` | Cancel current agent | Stops the agent in the focused terminal |
| `ESC` | Cancel all agents | Stops all running agents across all terminals |

**When to Use**:
- Agent is taking too long
- Wrong prompt was sent
- Need to interrupt for corrections
- Agent is stuck in a loop

**Effect**:
- Agent stops immediately
- Partial output remains visible
- Can send new prompt right away

---

## Utility Shortcuts

### Command Palette

| Shortcut | Action | Details |
|----------|--------|---------|
| `Ctrl+P` | Open command palette | Textual's command palette for searching actions |

**Features**:
- Search available commands
- Quick access to any action
- Fuzzy search support

---

### Clearing Input

| Shortcut | Action | Details |
|----------|--------|---------|
| `Ctrl+U` | Clear input | Removes all text from the input field |

**Usage**:
- Quick way to start fresh
- Clear accidental text
- Standard Unix/Linux behavior

---

### Exit Application

| Shortcut | Action | Details |
|----------|--------|---------|
| `Ctrl+Q` | Exit CAI TUI | Closes the application completely |

**Alternative**: Click the `×` button in top-right corner

**On Exit**:
- Session summary displayed (costs, tokens, duration)
- Unsaved conversations are lost (use `/save` first)
- API keys and configuration persist

## Input Editing

### Command Autocompletion

| Shortcut | Action | Details |
|----------|--------|---------|
| `Tab` | Autocomplete | Completes the current command or shows suggestions |

**Examples**:
- Type `/ag` + `Tab` → `/agent`
- Type `/mod` + `Tab` → `/model`

**Behavior**:
- Single match: Completes automatically
- Multiple matches: Shows list of suggestions
- No match: No action

---

### Command History

| Shortcut | Action | Details |
|----------|--------|---------|
| `↑` (Up Arrow) | Previous command | Navigate backward through command history |
| `↓` (Down Arrow) | Next command | Navigate forward through command history |

**Features**:
- History persists across sessions
- Stored in `~/.cai/history`
- Includes both commands and prompts
- Maximum history size: 1000 entries

**Usage Flow**:
1. Press `↑` to recall previous command
2. Continue pressing `↑` to go further back
3. Press `↓` to move forward in history
4. Edit recalled command if needed
5. Press `Enter` to execute

---

### Send Prompt

| Shortcut | Action | Details |
|----------|--------|---------|
| `Enter` | Send prompt/command | Executes the current input |

**Behavior**:
- Commands (starting with `/`): Execute immediately
- Prompts: Send to current agent
- If agent is busy: Automatically queued

## Terminal Content Copying

### Copy Visible Content

| Shortcut | Action | Details |
|----------|--------|---------|
| `Ctrl+Shift+X` | Copy visible | Copies currently visible terminal content to clipboard |

**Use Cases**:
- Share specific output with team
- Save important findings
- Document tool results

---

## Platform-Specific Notes

### macOS

All shortcuts work as documented. Some terminals (e.g., Terminal.app) may require:
- Enabling "Use Option as Meta key" in preferences
- Allowing keyboard shortcuts in Security & Privacy settings

### Linux

All shortcuts work as documented. If using tmux/screen:
- `Ctrl+B` conflicts with tmux prefix → Consider remapping tmux
- `Ctrl+S` may freeze terminal → Disable XON/XOFF with `stty -ixon`

### Windows

All shortcuts work in Windows Terminal and modern terminals. In older terminals:
- Some `Ctrl+Shift+` combinations may not work


## Custom Shortcuts

CAI TUI currently does not support custom keyboard shortcuts. This feature may be added in future versions.

**Workaround**: Use command aliases or shell scripts for custom workflows.

## Tips for Efficiency

### Power User Workflow

1. **Keep sidebar closed** (`Ctrl+S`) for max screen space
2. **Use `Ctrl+N`/`Ctrl+B`** to switch terminals instead of mouse
3. **Master `Tab` completion** for faster command input
4. **Use `↑`** to repeat similar prompts with modifications

### Recommended Shortcuts to Memorize First

Priority 1 (Essential):
- `Ctrl+S` - Toggle sidebar
- `Ctrl+Q` - Exit
- `Ctrl+C` - Cancel agent
- `Enter` - Send prompt
- `Tab` - Autocomplete

Priority 2 (Common):
- `Ctrl+N` / `Ctrl+B` - Navigate terminals
- `Ctrl+L` - Clear screen
- `↑` / `↓` - Command history
- `ESC` - Cancel all

Priority 3 (Advanced):
- `Ctrl+E` - Close terminal
- `Ctrl+P` - Command palette

## Troubleshooting Shortcuts

### Shortcut Not Working?

**Check 1: Terminal Compatibility**
- Some shortcuts may be intercepted by your terminal emulator
- Check terminal preferences for keyboard settings
- Try a different terminal (e.g., Alacritty, iTerm2)

**Check 2: tmux/screen Conflicts**
- tmux uses `Ctrl+B` as prefix (conflicts with "Previous Terminal")
- screen uses `Ctrl+A` as prefix (no conflicts with CAI TUI)
- Consider remapping tmux prefix: `set -g prefix C-a`

**Check 3: OS-Level Shortcuts**
- Some OS keyboard shortcuts override terminal shortcuts
- Example: macOS `Ctrl+Shift+Space` opens Spotlight
- Disable conflicting OS shortcuts or use command alternatives

### Accidental Exit (`Ctrl+Q`)

If you frequently press `Ctrl+Q` by accident:

**Workaround**: Use the close session button instead


## See Also

- 🎯 [Commands Reference](commands_reference.md) - All available commands
- 🖥️ [User Interface](user_interface.md) - Visual guide to the interface
- 📖 [Getting Started](getting_started.md) - Basic usage tutorial

---

*Last updated: October 2025 | CAI TUI v0.6+*

