# Getting Started with CAI TUI

> **⚡ CAI-Pro Exclusive Feature**  
> The Terminal User Interface (TUI) is available exclusively in **CAI-Pro**. To access this feature and unlock advanced multi-agent workflows, visit [Alias Robotics](https://aliasrobotics.com/cybersecurityai.php) for more information.

---

This guide will walk you through launching the CAI TUI for the first time and performing your first security assessment.

## Prerequisites

Before starting, ensure you have:

- ✅ CAI installed (see [Installation Guide](../Installation_Guide_for_CAI_Pro_v0.6.md))
- ✅ Python 3.9+ installed
- ✅ A valid `ALIAS_API_KEY` from [Alias Robotics](https://aliasrobotics.com)


## Step 1: Launch the TUI

Open your terminal and run:

```bash
cai --tui
```

If your `ALIAS_API_KEY` is not configured, you'll see an authentication error. Don't worry—we'll fix this in the next step.


## Step 2: Configure Your API Key

The first time you use CAI TUI, you need to configure your API key:

1. **Open the Sidebar**
   - Press `Ctrl+S` to toggle the sidebar (if not already visible)

2. **Navigate to Keys Tab**
   - Click on the **"Keys"** tab in the sidebar
   - This shows all configured API keys

3. **Add Your API Key**
   - Click the **"Add New Key"** button
   - A dialog will appear with two fields:
     - **Key Name**: Enter `ALIAS_API_KEY`
     - **Key Value**: Enter your API key (e.g., `ak_live_1234567890abcdef`)
   
4. **Save the Key**
   - Click the **"Save"** button
   - Your key is now securely stored in `~/.cai/.env`

### Alternative: Using Environment Variables

You can also set your API key via environment variable:

```bash
export ALIAS_API_KEY="your_api_key_here"
cai --tui
```

Or create a `.env` file in your project directory:

```env
ALIAS_API_KEY=your_api_key_here
```

## Step 3: Select Your Model

CAI supports multiple AI models. For optimal performance and cost balance, we recommend `alias1`:

### Option 1: Using the Dropdown (Recommended)

1. Look at the terminal header (top bar of each terminal)
2. Find the **"model"** dropdown (center-right area)
3. Click on it to see available models
4. Select **`alias1`**

### Option 2: Using a Command

Type in the input field at the bottom:

```
/model alias1
```

Press **Enter**.

### Available Models

| Model | Provider | Best For | Cost |
|-------|----------|----------|------|
| `alias1` | Alias Robotics | **Recommended** - Balanced performance | Medium |
| `gpt-5` | OpenAI | Latest reasoning and code generation | Very High |
| `gpt-4o` | OpenAI | Complex reasoning and multi-modal | High |
| `claude-4-5` | Anthropic | Advanced reasoning and long contexts | Very High |
| `claude-3-5-sonnet-20241022` | Anthropic | Fast responses with good quality | High |

> **💡 Tip**: You can change models at any time without losing your conversation history.

## Step 4: Choose Your Agent

CAI comes with specialized agents for different security tasks. Here's how to choose:

### Option 1: Use the Agent Recommendation System

The easiest way to start:

1. Click the **agent** dropdown in the terminal header
2. Select **`selection_agent`** 
3. Type your task description: `"I need to test a web application for SQL injection"`
4. The agent will recommend the best agent for your task

Alternatively, use the command:

```
/agent selection_agent
```

Then describe your task.

### Option 2: Choose Directly from the Dropdown

If you know which agent you need:

1. Click the **agent** dropdown
2. Browse available agents (scroll if needed)
3. Select your desired agent (e.g., `redteam_agent`, `bug_bounter_agent`)

### Option 3: List All Agents

To see all available agents with descriptions:

```
/agent list
```

### Common Agent Types

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| `redteam_agent` | Offensive security testing | Default for penetration testing |
| `blueteam_agent` | Defensive security analysis | Security posture assessment |
| `bug_bounter_agent` | Bug bounty hunting | Finding high-value vulnerabilities |
| `retester_agent` | Vulnerability retesting | Confirming fixes |
| `selection_agent` | Agent recommendation | **When unsure which agent to use** |

> **💡 Pro Tip**: Start with `selection_agent` if you're new to CAI—it will guide you to the right agent for your task.

## Step 5: Start Your First Conversation

Now you're ready to interact with CAI!

### Example 1: Basic Reconnaissance

In the input field at the bottom (marked with `CAI>`), type:

```
Scan 198.51.100.50 for open ports and services
```

Press **Enter**.

The agent will:
- Process your request
- Use appropriate tools (nmap, etc.)
- Display results in the terminal output area

### Example 2: Web Application Testing

Prompt example:

```
Test https://example.com for common web vulnerabilities
```

Press **Enter**.

The agent will:
- Process your request
- Use appropriate tools (nmap, etc.)
- Display results in the terminal output area

### Example 3: Network Analysis

Prompt example:

```
Analyze the network traffic from this pcap file: capture.pcap
```

### Understanding the Output

As the agent works, you'll see:

1. **Tool Execution**: Messages showing which tools are being launched
2. **Streaming Output**: Real-time results from tools
3. **Agent Reasoning**: The agent's thought process (if `CAI_DEBUG=1`)
4. **Final Response**: Summary and recommendations

### Queuing Prompts

If the agent is busy, you can send another prompt—it will be **automatically queued**:

- View the queue: Press `Ctrl+Shift+Q` or use `/queue`
- The next prompt will execute when the current one finishes

## Step 6: Working with Multiple Terminals

One of the TUI's most powerful features is multi-terminal support.

### Adding a New Terminal

Click the **"Add +"** button in the top of the screen

Each new terminal:
- Starts with `alias1` model and `redteam_agent`
- Has an independent conversation history
- Can run a different agent and model

### Navigating Between Terminals

- **Next terminal**: `Ctrl+N`
- **Previous terminal**: `Ctrl+B`
- **Click directly** on any terminal to focus it

### Example Workflow: Dual-Perspective Analysis

1. **Terminal 1**: Keep `redteam_agent` for offensive testing
2. **Terminal 2**: Add a new terminal, switch to `blueteam_agent`
3. Send the same target to both:
   - T1: Offensive analysis
   - T2: Defensive recommendations
4. Compare results side-by-side

## Step 7: Using Preconfigured Teams

For common multi-agent workflows, use **Teams**:

1. Open the sidebar (`Ctrl+S`)
2. Click the **"Teams"** tab
3. Select a team (e.g., **"#1: 2 red + 2 bug"**)

This will:
- Automatically open 4 terminals (or reuse existing ones)
- Assign agents according to the team configuration
- Ready to process your prompt in parallel

**Popular Teams**:
- **2 Red + 2 Bug**: Comprehensive penetration testing + bug hunting
- **2 Red + 2 Blue**: Offensive + defensive analysis
- **Red + Blue + Retester + Bug**: Full security assessment lifecycle

Learn more about Teams and Parallel Execution in the full TUI documentation.

## Step 8: Saving Your Work

To save your conversation for later:

```
/save my-assessment.json
```

Or in Markdown format:

```
/save my-assessment.md
```

Files are saved in your current working directory.

### Loading a Saved Session

```
/load my-assessment.json
```

This restores the conversation history for the current terminal.

## Step 9: Monitoring Costs

CAI tracks your API usage and costs in real-time.

### View Costs for Current Agent

```
/cost
```

This shows:
- Total tokens used (input + output)
- Estimated cost in USD
- Breakdown by interaction

### Check Stats in Sidebar

Open the sidebar (`Ctrl+S`) and go to **"Stats"** tab to see:
- Session duration
- Total agents used
- Total cost across all terminals

## Common First-Time Issues

### Issue: Agent is not responding

**Solution**: 
- Press `Ctrl+C` to cancel the current agent
- Check your internet connection
- Verify your API key is valid

### Issue: Terminal output is cluttered

**Solution**:
- Clear the terminal: `Ctrl+L` or `/clear`
- Reduce debug output: Set `CAI_DEBUG=0` before launching
- Use `/flush` to clear conversation history

### Issue: I can't see the full interface

**Solution**:
- Resize your terminal window to at least 120x40 characters
- Try full-screen mode: `F11` (on most terminals)
- Zoom out: `Ctrl+-` (on most terminals)

## Next Steps

Congratulations! You've completed the basics of CAI TUI. Here's what to explore next:

### Learn More Commands
- 📖 [Commands Reference](commands_reference.md) - Master all available commands
- ⌨️ [Keyboard Shortcuts](keyboard_shortcuts.md) - Speed up your workflow

### Explore Advanced Features
- 👥 [Teams and Parallel Execution](teams_and_parallel_execution.md) - Multi-agent workflows
- 🚀 [Advanced Features](advanced_features.md) - MCP, ICL, and more

### Get Help
- 🔧 [Troubleshooting](troubleshooting.md) - Solve issues
- 💬 [Community Discord](https://discord.gg/aliasrobotics) - Ask questions

