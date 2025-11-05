# Get Started with CAI PRO

> **Quick Start Guide**
>
> This guide will have you running CAI PRO with unlimited alias1 tokens in minutes.
>
> **Already subscribed?** Jump to [Step 2: Install CAI](#2-install-cai)

---

## Prerequisites

- **Operating System**: Linux, macOS, or Windows (WSL2)
- **Python**: 3.9 or higher
- **Internet Connection**: Required for initial setup
- **CAI PRO Subscription**: [Subscribe here](https://aliasrobotics.com/cybersecurityai.php)

---

## Quick Start Steps

### 1. Subscribe to CAI PRO

Visit [https://aliasrobotics.com/cybersecurityai.php](https://aliasrobotics.com/cybersecurityai.php):

1. Click **"Buy CAI PRO"**
2. Complete payment (€350/month, secure European processing)
3. Receive your **`ALIAS_API_KEY`** via email (within 5 minutes)

**💡 Tip**: Check your spam folder if you don't receive the key immediately.

---

### 2. Install CAI

#### Installation Steps

1. **Create and navigate to your project directory:**

```bash
mkdir cai-pro
cd cai-pro
```

2. **Update system packages:**

```bash
sudo apt update
```

3. **Create a Python virtual environment:**

```bash
python3.12 -m venv cai_env
```

4. **Activate the virtual environment:**

```bash
source cai_env/bin/activate
```

5. **Install CAI PRO from private package repository:**

```bash
pip install --index-url https://packages.aliasrobotics.com:664/<api-key>/ cai-framework
```

**⚠️ Important**: Replace `<api-key>` with your API Key from the subscription confirmation email.

**Example:**
```bash
pip install --index-url https://packages.aliasrobotics.com:664/sk-xxxxxxxxxxxxxxxx/ cai-framework
```

**💡 Tip**: Your API Key looks like `sk-xxxxxxxxxxxxxxxx` and is provided in your CAI PRO subscription email.

For detailed installation instructions and troubleshooting, see the [CAI PRO Installation Guide](Installation_Guide_for_CAI_Pro_v0.6.md).

---

### 3. Configure Your Environment

Create or update your `.env` file in your project directory:

```bash
# CAI PRO Configuration
ALIAS_API_KEY="sk-your-caipro-key-here"
CAI_MODEL="alias1"

# Optional: Enable advanced features
CAI_TUI_MODE=true
CAI_GUARDRAILS=true
CAI_STREAM=false
```

**💡 Security Tip**: Never commit `.env` files to version control. Add `.env` to your `.gitignore`.

---

### 4. Verify Installation

Test that CAI PRO is working correctly:

```bash
# Launch CAI CLI
cai

# Inside CAI, check your model
CAI> /model

# You should see:
# Available models:
# - alias1 (active) ✅
# - alias0
# - gpt-4o (requires OPENAI_API_KEY)
# - claude-sonnet-4 (requires ANTHROPIC_API_KEY)
# ...
```

**Expected output**: `alias1` should be listed and marked as active.

---

### 5. Run Your First Security Test

Let's start with a simple security assessment:

```bash
CAI> Analyze the security posture of https://testphp.vulnweb.com

# Alias1 will:
# 1. Perform reconnaissance
# 2. Identify vulnerabilities
# 3. Suggest exploitation techniques
# 4. Provide remediation guidance
```

**✅ Success!** You're now using unlimited alias1 tokens for security testing.

---

## Launch Terminal UI (TUI)

CAI PRO includes a powerful multi-terminal interface:

```bash
# Launch TUI mode
cai --tui

# Or set it as default in .env
echo "CAI_TUI_MODE=true" >> .env
cai
```

### TUI Quick Tips

**Keyboard Shortcuts:**
- `Ctrl+S` - Toggle sidebar
- `Ctrl+N` / `Ctrl+B` - Switch between terminals
- `Ctrl+L` - Clear terminal
- `Ctrl+Q` - Exit

**Add More Terminals:**
- Click the `[+]` button in the top bar
- Or use `/add` command

**Load Preconfigured Teams:**
- Open sidebar (`Ctrl+S`)
- Click "Teams" tab
- Select a team (e.g., "#1: 2 red + 2 bug")

[Full TUI Documentation →](tui/tui_index.md)

---

## Common First Tasks

### Task 1: Web Application Security Assessment

```bash
CAI> Conduct a comprehensive security assessment of https://example.com

# Alias1 will:
# - Enumerate subdomains and technologies
# - Identify OWASP Top 10 vulnerabilities
# - Test for SQL injection, XSS, CSRF
# - Generate a detailed report
```

### Task 2: CTF Challenge Solving

```bash
CAI> Solve this CTF challenge: [paste challenge description]

# Alias1 excels at:
# - Web challenges
# - Binary exploitation
# - Cryptography
# - Reverse engineering
```

### Task 3: Exploit Development

```bash
CAI> Write a Python exploit for CVE-2024-1234

# Alias1 will:
# - Research the vulnerability
# - Develop a working exploit
# - Include error handling
# - Add comments explaining each step
```

### Task 4: Bug Bounty Reconnaissance

```bash
CAI> Perform recon on https://bugbounty-target.com for a bug bounty program

# Alias1 will:
# - Enumerate attack surface
# - Identify interesting endpoints
# - Suggest testing strategies
# - Prioritize high-value targets
```

---

## Advanced Configuration

### Enable Context Monitoring

Track your token usage in real-time:

```bash
CAI> /context

# Shows:
# - Total tokens used/available
# - Breakdown by category (system, tools, memory, messages)
# - Visual grid representation
# - Optimization suggestions
```

### Multi-Agent Parallel Execution

Run multiple agents simultaneously in TUI:

```bash
# In TUI mode, open sidebar (Ctrl+S)
# Click "Teams" tab
# Select Team #1: "2 red + 2 bug"

# Type your prompt and press Ctrl+Shift+A to broadcast to all terminals
Scan target.com for vulnerabilities
```

### Save and Load Sessions

```bash
# Save your current conversation
CAI> /save pentest_session.json

# Load it later
CAI> /load pentest_session.json
```

---

## Troubleshooting

### Issue: "alias1 not available"

**Solution 1**: Check your API key
```bash
# Verify ALIAS_API_KEY is set correctly
env | grep ALIAS
```

**Solution 2**: Ensure you're using CAI PRO version
```bash
cai --version
# Should show v0.6.0 or higher
```

**Solution 3**: Contact support
- Email: support@aliasrobotics.com
- Subject: "alias1 not available - [your email]"

---

### Issue: "Rate limit exceeded"

**This shouldn't happen with CAI PRO** (unlimited tokens). If you see this:

1. Check for typos in your `ALIAS_API_KEY`
2. Contact support immediately: support@aliasrobotics.com

---

### Issue: TUI not launching

**Solution 1**: Install required dependencies
```bash
pip install textual rich
```

**Solution 2**: Check terminal compatibility
```bash
# TUI requires a modern terminal emulator
# Recommended: Alacritty, iTerm2, Windows Terminal
```

**Solution 3**: Use CLI mode instead
```bash
# TUI is optional, CLI works everywhere
cai  # without --tui flag
```

---

## Next Steps

### 📚 Learn More

- **[TUI Full Guide](tui/tui_index.md)** - Master the Terminal UI
- **[Commands Reference](tui/commands_reference.md)** - All available commands
- **[Alias1 Deep Dive](cai_pro_alias1.md)** - Understand your flagship model
- **[Features Overview](cai_pro_features.md)** - Explore all CAI PRO capabilities

### 🎯 Practical Guides

- **[Running Agents](running_agents.md)** - Agent selection and configuration
- **[Context Management](context.md)** - Optimize token usage
- **[Guardrails & Security](guardrails.md)** - Secure testing practices
- **[Environment Variables](environment_variables.md)** - Complete configuration reference

### 🏆 Case Studies

Learn from real-world CAI applications:
- [Ecoforest Heat Pumps OT Security](https://aliasrobotics.com/case-studies-robot-cybersecurity.php)
- [MiR Robot Vulnerability Discovery](https://aliasrobotics.com/case-studies-robot-cybersecurity.php)
- [Mercado Libre API Testing](https://aliasrobotics.com/case-studies-robot-cybersecurity.php)

---

## Get Help

### Professional Support (CAI PRO Subscribers)

- **Email**: support@aliasrobotics.com (48h SLA)
- **Discord**: #pro-support channel (exclusive)
- **Quarterly Calls**: Strategy and roadmap discussions

### Community Resources

- **[Discord Community](https://discord.gg/fnUFcTaQAC)** - 1000+ security researchers
- **[GitHub Issues](https://github.com/aliasrobotics/cai/issues)** - Bug reports and feature requests
- **[Documentation](index.md)** - Complete CAI documentation

---

## Tips for Success

### 🎯 Best Practices

1. **Start with clear prompts**: Be specific about your testing scope and objectives
2. **Use context monitoring**: Check `/context` regularly to optimize token usage
3. **Leverage parallel execution**: Run multiple agents for comprehensive coverage
4. **Save your sessions**: Use `/save` to preserve important conversations
5. **Enable guardrails**: Keep `CAI_GUARDRAILS=true` for safer operations

### ⚡ Power User Tips

- **Keyboard shortcuts**: Master `Ctrl+N`, `Ctrl+B`, `Ctrl+S` for efficient TUI navigation
- **Team presets**: Use preconfigured teams instead of manual agent setup
- **Mix models**: Use alias1 for exploitation, GPT-4o for professional reporting
- **Custom agents**: Request specialized agents for your domain (contact support)

---

## Congratulations! 🎉

You're now ready to leverage CAI PRO for professional security testing. 

**Remember:**
- ✅ Unlimited alias1 tokens
- ✅ Zero refusals for authorized testing
- ✅ Professional support available
- ✅ European data privacy guaranteed

**Questions?** Contact support@aliasrobotics.com

---

<small>
*Need help? We're here: **support@aliasrobotics.com***  
*Want to upgrade to Enterprise? [Request quote →](mailto:contact@aliasrobotics.com?subject=CAI%20Enterprise%20Inquiry)*
</small>

