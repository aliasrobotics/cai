# Troubleshooting

> **⚡ CAI-Pro Exclusive Feature**  
> The Terminal User Interface (TUI) is available exclusively in **CAI-Pro**. To access this feature and unlock advanced multi-agent workflows, visit [Alias Robotics](https://aliasrobotics.com) for more information.

---

Common issues and solutions when using CAI TUI.

---

## Installation Issues

### Package Installation Fails

**Symptom**: `pip install` errors or dependency conflicts

**Solutions**:
- Update pip: `pip install --upgrade pip`
- Use Python 3.10+: `python --version`
- Try clean install: `pip install --force-reinstall cai`

---

## Launch Issues

### TUI Won't Start

**Symptom**: `cai` command not found or crashes on launch

**Solutions**:
- Verify installation: `pip show cai`
- Check Python path: `which python`
- Review error logs: `~/.cai/logs/`

### Terminal Display Issues

**Symptom**: Broken UI, missing colors, or garbled text

**Solutions**:
- Use modern terminal (recommended: Alacritty, iTerm2, Windows Terminal)
- Check terminal size: minimum 80x24
- Verify TERM variable: `echo $TERM`

---

## API Configuration

### API Key Not Working

**Symptom**: Authentication errors or "invalid API key" messages

**Solutions**:
- Verify key in `.env`: `CAI_API_KEY=your_key`
- Check key format and validity
- Restart TUI after changes

### Model Not Available

**Symptom**: Selected model returns errors

**Solutions**:
- Verify API key has access to model
- Check model name spelling
- Review available models in dropdown

---

## Agent Issues

### Agent Not Responding

**Symptom**: Prompts hang or no response from agent

**Solutions**:
- Check API rate limits
- Verify network connection
- Try different model
- Check cost limits not exceeded

### Wrong Agent Behavior

**Symptom**: Agent doesn't follow expected workflow

**Solutions**:
- Verify correct agent selected
- Use `/clear` to reset context
- Check agent description matches your needs

---

## Terminal Management

### Can't Create New Terminal

**Symptom**: New terminal button doesn't work

**Solutions**:
- Check maximum terminals reached (depends on layout)
- Try different layout: `Ctrl+L`
- Restart TUI

### Terminal Not Responding

**Symptom**: Input doesn't work in specific terminal

**Solutions**:
- Click terminal to focus
- Use `Ctrl+1/2/3/4` to switch focus
- Check if prompt is running

---

## Performance Issues

### Slow Response Times

**Symptom**: Agent takes too long to respond

**Solutions**:
- Try faster model (e.g., gpt-4o-mini)
- Reduce context with `/clear`
- Check network latency

### High Memory Usage

**Symptom**: TUI consumes excessive RAM

**Solutions**:
- Clear conversation history: `/clear`
- Reduce number of active terminals
- Restart TUI periodically

---

## Session & Data Issues

### Session Won't Load

**Symptom**: `/load` command fails

**Solutions**:
- Verify file path is correct
- Check JSON format validity
- Ensure file permissions

### Stats Not Updating

**Symptom**: Stats tab shows stale or no data

**Solutions**:
- Switch to different tab and back
- Check API responses are completing
- Restart TUI

---

## Cost & Billing

### Unexpected High Costs

**Symptom**: Token usage higher than expected

**Solutions**:
- Check Stats tab for breakdown
- Review context length
- Set cost limits in `.env`
- Use cheaper models for reconnaissance

---

## Keyboard Shortcuts

### Shortcuts Not Working

**Symptom**: Key combinations don't trigger actions

**Solutions**:
- Check terminal intercepts keys
- Verify TUI has focus
- Use alternative shortcuts (see [Keyboard Shortcuts](keyboard_shortcuts.md))

---

## Getting Help

If your issue isn't covered here:

1. **Check logs**: `~/.cai/logs/latest.log`
2. **Press F1**: Context-sensitive help in TUI
3. **Review documentation**: Other guides in `docs/tui/`
4. **Report issues**: Contact support with error logs

---

## Related Documentation

- [Getting Started](getting_started.md) - Setup and configuration
- [Configuration](configuration.md) - Environment variables and settings
- [Commands Reference](commands_reference.md) - All available commands
- [User Interface](user_interface.md) - UI components explained

---

