# CAI Continue Mode

## Overview

The `--continue` flag enables CAI agents to operate autonomously by automatically generating intelligent continuation prompts when they would normally stop and wait for user input. This feature uses AI-powered analysis to provide contextual advice based on the conversation history, allowing agents to work on complex tasks without manual intervention.

## Quick Start

```bash
# Tell jokes continuously
cai --continue --prompt "tell me a joke about security"

# Analyze code autonomously  
cai --continue --prompt "find all SQL injection vulnerabilities in this codebase"

# Run security audit
cai --continue --prompt "perform a comprehensive security audit"
```

## Example: Security Jokes with Continue Mode

Here's what happens when you run `cai --continue --prompt "tell me a joke about security"`:

```bash
$ cai --continue --prompt "tell me a joke about security"

🤖 Processing initial prompt: tell me a joke about security

Agent: Why did the hacker break up with their password? 
       Because it wasn't strong enough! 💔🔐

🤖 Auto-continuing with: Tell another cybersecurity joke or pun.

Agent: Why don't cybersecurity experts tell secrets at parties?
       Because they're afraid of social engineering! 🎉🕵️

🤖 Auto-continuing with: Tell another cybersecurity joke or pun.

Agent: What's a hacker's favorite season?
       Phishing season! 🎣💻

[Continues until interrupted with Ctrl+C]
```

## How It Works

### 1. Intelligent Context Analysis

When an agent completes a turn, the continuation system analyzes:
- **Original request**: The initial task or prompt from the user
- **Conversation history**: Recent messages and responses
- **Tool usage**: Which tools were used and their outputs
- **Error states**: Any errors encountered and their types
- **Task progress**: Current state of task completion

### 2. AI-Powered Continuation Generation

The system uses the configured AI model (default: alias1) to generate contextual continuation prompts:

```python
# The system creates a detailed context summary
context_summary = """
ORIGINAL TASK: Tell me a joke about security
CONVERSATION FLOW:
User: Tell me a joke about security
Agent: Why did the hacker break up with their password? Because it wasn't strong enough!

CURRENT STATUS:
- Last action: Told a cybersecurity joke
- Tools used: None
- Errors: No

Generate a specific continuation prompt...
"""
```

### 3. Smart Fallback System

When the AI model is unavailable, the system provides intelligent fallbacks based on context:

| Scenario | Fallback Continuation |
|----------|----------------------|
| Security joke told | "Tell another cybersecurity joke or pun." |
| File not found | "Search for the correct file path or create the missing resource." |
| Search completed | "Examine the search results in detail and investigate the most relevant findings." |
| Security analysis | "Analyze the code for security vulnerabilities like injection flaws or authentication issues." |
| Permission denied | "Check permissions and try accessing the resource with appropriate credentials." |

## Common Use Cases

### 1. Automated Security Audits
```bash
cai --continue --prompt "perform a security audit of the authentication system"
```
The agent will:
- Search for authentication-related files
- Analyze code for vulnerabilities
- Check for common security issues
- Generate a comprehensive report

### 2. Continuous Bug Hunting
```bash
cai --continue --prompt "find and document all XSS vulnerabilities"
```
The agent will:
- Search for user input handling code
- Identify potential XSS vectors
- Document findings
- Suggest fixes

### 3. Extended Code Analysis
```bash
cai --continue --prompt "analyze this codebase for OWASP Top 10 vulnerabilities"
```
The agent will:
- Systematically check for each vulnerability type
- Provide detailed findings
- Continue until all categories are covered

### 4. Entertainment Mode
```bash
cai --continue --prompt "tell me cybersecurity jokes and fun facts"
```
The agent will:
- Tell jokes about security topics
- Share interesting security facts
- Continue entertaining until stopped

## Configuration

### Environment Variables

```bash
# Use a different model for continuation generation
export CAI_MODEL=gpt-4
cai --continue --prompt "analyze this code"

# Set a fallback model if primary fails
export CAI_CONTINUATION_FALLBACK_MODEL=gpt-3.5-turbo
cai --continue --prompt "test application security"

# Configure API keys for custom models
export ALIAS_API_KEY=your-api-key
cai --continue --prompt "perform penetration testing"
```

### Combining with Other CAI Features

```bash
# Use specific agent with continue mode
CAI_AGENT_TYPE=bug_bounter_agent cai --continue --prompt "test example.com"

# Set workspace for file operations
CAI_WORKSPACE=project1 cai --continue --prompt "audit all Python files"

# Enable streaming for real-time output
CAI_STREAM=true cai --continue --prompt "monitor security events"
```

## Advanced Features

### Continuation Decision Logic

The system decides whether to continue based on:
1. **Completion indicators**: Stops if agent says "completed", "finished", "done"
2. **Active work detection**: Continues if tools are being used
3. **Error recovery**: Attempts to resolve errors automatically
4. **Task progress**: Evaluates if the original goal is achieved

### Context-Aware Prompts

The continuation prompts adapt based on:
- **Task type**: Security analysis, testing, code review, etc.
- **Current state**: Errors, findings, progress
- **Tool usage**: Different prompts for different tools
- **Conversation flow**: Maintains coherent task progression

## Best Practices

### 1. Clear Initial Prompts
```bash
# Good - Specific and actionable
cai --continue --prompt "find SQL injection vulnerabilities in user.py"

# Less effective - Too vague
cai --continue --prompt "check security"
```

### 2. Monitor Progress
- Check output periodically to ensure correct direction
- Use Ctrl+C to stop if needed
- Review logs for detailed execution history

### 3. Set Appropriate Limits
```python
# In code integration, use max_turns
run_cai_cli(
    starting_agent=agent,
    initial_prompt="analyze security",
    continue_mode=True,
    max_turns=10  # Limit to 10 turns
)
```

### 4. Error Handling
The system automatically:
- Retries failed operations with different approaches
- Searches for alternatives when files are missing
- Adjusts strategies based on error types

## Troubleshooting

### Issue: Generic Continuation Messages
**Symptom**: Always see "Continue working on the task based on your previous findings"

**Solution**: 
- Check model configuration is correct
- Ensure API keys are valid
- Review debug logs for API errors

### Issue: Continuation Not Triggering
**Symptom**: Agent stops after completing a task

**Possible causes**:
- Agent explicitly said task is "completed" or "done"
- No recent tool usage detected
- Error in continuation module

**Solution**:
- Use more open-ended initial prompts
- Check logs for completion indicators
- Verify --continue flag is properly set

### Issue: Infinite Loops
**Symptom**: Agent keeps doing the same thing

**Solution**:
- Set max_turns limit
- Use more specific initial prompts
- Interrupt with Ctrl+C and refine the task

## Technical Implementation

### Core Components

1. **`src/cai/continuation.py`**: Main continuation logic
   - `generate_continuation_advice()`: Creates AI-powered prompts
   - `should_continue_automatically()`: Decides when to continue

2. **`src/cai/cli.py`**: Integration point
   - `--continue` flag handling
   - Continuation loop implementation

3. **Context Analysis**: 
   - Extracts conversation history
   - Identifies tool usage patterns
   - Detects error conditions

### API Integration

The continuation system uses LiteLLM for model calls:
```python
response = await litellm.acompletion(
    model=model_name,
    messages=[{"role": "user", "content": context_summary}],
    temperature=0.3,  # Low temperature for focused responses
    max_tokens=150
)
```

## Examples Gallery

### Security Audit Continuation
```
Original: "Audit the login system"
→ "Search for authentication-related files in the codebase."
→ "Analyze the login function for SQL injection vulnerabilities."
→ "Check password hashing implementation for security best practices."
→ "Review session management for potential security issues."
```

### Bug Bounty Continuation
```
Original: "Test example.com for vulnerabilities"
→ "Perform initial reconnaissance to gather information about the target."
→ "Scan for exposed endpoints and services."
→ "Test authentication endpoints for common vulnerabilities."
→ "Check for information disclosure in error messages."
```

### Code Review Continuation
```
Original: "Review api.py for security issues"
→ "Analyze input validation in API endpoints."
→ "Check for proper authentication and authorization."
→ "Review error handling for information leakage."
→ "Examine data serialization for injection vulnerabilities."
```

## Example Scripts

Explore working examples in the `examples/` directory:

### Security Jokes Example
```python
# examples/continue_mode_jokes.py
# Demonstrates continuous joke telling with --continue flag
python examples/continue_mode_jokes.py
```

### Security Audit Example
```python
# examples/continue_mode_security_audit.py
# Shows autonomous vulnerability scanning with --continue
python examples/continue_mode_security_audit.py
```

These examples demonstrate:
- How to use --continue flag programmatically
- Handling continuous output
- Graceful interruption with Ctrl+C
- Practical security use cases

## Combining with Session Resume

The `--continue` flag works seamlessly with `--resume` to continue interrupted sessions autonomously:

```bash
# Resume last session and continue working autonomously
cai --resume --continue

# Resume specific session and continue
cai --resume abc12345 --continue

# Resume from interactive selector and continue
cai --resume list --continue
```

This powerful combination:
1. **Restores your previous session** with full conversation history
2. **Automatically generates a continuation prompt** based on where you left off
3. **Continues working autonomously** without waiting for user input

For more details on session resume capabilities, see the [Session Resume](session_resume.md) documentation.

## Summary

The `--continue` flag transforms CAI into an autonomous cybersecurity assistant capable of:
- Working independently on complex tasks
- Recovering from errors intelligently
- Maintaining context across multiple operations
- Resuming and continuing interrupted sessions with `--resume --continue`
- Providing entertainment with continuous jokes

Whether you're conducting security audits, hunting for bugs, or just want some cybersecurity humor, continue mode keeps your agent working until the job is done.