# LLM Council

The LLM Council is a multi-model consensus system that queries multiple AI models, has them evaluate each other's responses, and synthesizes a final answer through a chairman. This approach improves accuracy for complex decisions by leveraging diverse model perspectives.

## How It Works

The council operates in three stages:

```
User Query: "What's the best approach for this security task?"
│
├─ Stage 1: Council Members (parallel)
│  ├─ Agent + gpt-4o           → Text response only
│  ├─ Agent + gpt-5            → Text response only
│  └─ Agent + claude-sonnet-4-5 → Text response only
│
├─ Stage 2: Rankings (parallel)
│  ├─ Agent + gpt-4o           → Ranks anonymized responses
│  ├─ Agent + gpt-5            → Ranks anonymized responses
│  └─ Agent + claude-sonnet-4-5 → Ranks anonymized responses
│
└─ Stage 3: Chairman
   └─ Active Agent + TOOLS
      ├─ Synthesizes best answer
      └─ Can execute operations if requested
```

**Key Points:**

- **Stage 1 & 2**: Council members provide text-only responses (no tool execution)
- **Stage 3**: The chairman (your active agent) can use all available tools
- All members use the current agent's instructions and context

## Quick Start

```bash
# Configure council models
export CAI_COUNCIL="gpt-4o,gpt-5,claude-sonnet-4-20250514"

# In CAI REPL, load an agent first
CAI> /agent redteam

# Use the council command
CAI> /council What are the best practices for API security?

# Or use the short alias
CAI> /c How should I approach this vulnerability assessment?
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CAI_COUNCIL` | Comma-separated list of council member models | `gpt-4o,gpt-4o-mini` |
| `CAI_COUNCIL_AUTO` | Auto-convene setting: `false`, `true`/`1`, or interval number | `false` |
| `CAI_COUNCIL_PROMPT` | Custom prompt for auto-council reviews | See below |
| `CAI_COUNCIL_DEBUG` | Enable debug output (`1`, `true`, `yes`) | `false` |

```bash
# Example configuration
export CAI_COUNCIL="gpt-4o,gpt-5,claude-sonnet-4-20250514"
export CAI_COUNCIL_AUTO="5"
export CAI_COUNCIL_PROMPT="Review the current progress and recommend the best approach."
export CAI_COUNCIL_DEBUG="1"
```

### API Keys

Ensure you have the appropriate API keys set for your council models:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export ALIAS_API_KEY="..."
```

### Verified Model Names

Use exact model names as shown in the `/model` command:

| Provider | Models |
|----------|--------|
| OpenAI | `gpt-5`, `gpt-4o`, `gpt-4o-mini`, `o3-mini` |
| Anthropic | `claude-sonnet-4-20250514`, `claude-3-5-sonnet-20240620` |
| Alias | `alias1` |
| DeepSeek | `deepseek-v3`, `deepseek-r1` |

## Manual Usage

The `/council` command (alias `/c`) invokes the council manually:

```bash
# Load an agent
CAI> /agent redteam

# Ask the council
CAI> /council What vulnerabilities should I look for in this web application?
```

The council uses the active agent's:

- Instructions/system prompt
- Available tools (chairman only)
- Guardrails

## Auto-Council Mode

When `CAI_COUNCIL_AUTO` is enabled, the council convenes automatically at specified intervals during agent execution.

### Configuration Options

- `false` - Never auto-convene (use `/council` manually)
- `true` or `1` - Convene at every agent interaction
- `5`, `10`, etc. - Convene every N interactions

### Example: Every Interaction

```bash
export CAI_COUNCIL_AUTO="1"

CAI> run ps aux, then analyze the results, then check for vulnerabilities

🏛️ COUNCIL (auto-invoked at interaction [1])
[Stage 1, 2, 3 run...]
[1] Agent: "I'll run ps aux" → executes command

🏛️ COUNCIL (auto-invoked at interaction [2])
[Stage 1, 2, 3 run...]
[2] Agent: "Analyzing results..." → analyzes output

🏛️ COUNCIL (auto-invoked at interaction [3])
[Stage 1, 2, 3 run...]
[3] Agent: "Checking for vulnerabilities..." → performs check
```

### Example: Every 5 Interactions

```bash
export CAI_COUNCIL_AUTO="5"

CAI> perform a comprehensive security audit

[1] Agent executes first task
[2] Agent executes second task
[3] Agent executes third task
[4] Agent executes fourth task

🏛️ COUNCIL (auto-invoked at interaction [5])
[Stage 1, 2, 3 run...]
[5] Agent executes fifth task

[6] Agent continues...
[7] Agent continues...
[8] Agent continues...
[9] Agent continues...

🏛️ COUNCIL (auto-invoked at interaction [10])
[Stage 1, 2, 3 run...]
[10] Agent executes tenth task
```

## Programmatic Usage

You can use the council directly in Python code:

```python
from cai.council import run_full_council_agents, CouncilAgentConfig
from cai.sdk.agents import Agent

# With an existing agent
stage1, stage2, stage3, metadata = await run_full_council_agents(
    base_agent=my_agent,
    user_query="Your question here",
)

# Access results
print(stage3["response"])  # Final answer
print(metadata["aggregate_rankings"])  # Model rankings
print(metadata["council_cost"])  # Total cost
print(metadata["council_input_tokens"])  # Input tokens
print(metadata["council_output_tokens"])  # Output tokens
```

### Return Values

```python
stage1_results: List[Dict]  # Individual responses from each model
stage2_results: List[Dict]  # Rankings from each model
stage3_result: Dict         # Final synthesized answer
metadata: Dict              # Rankings, cost, tokens
```

### Metadata Structure

```python
metadata = {
    "aggregate_rankings": [
        {"model": "gpt-4o", "average_rank": 1.33, "rankings_count": 3},
        {"model": "gpt-5", "average_rank": 2.0, "rankings_count": 3},
    ],
    "council_cost": 0.032,
    "council_input_tokens": 5000,
    "council_output_tokens": 2500,
}
```

## Visual Display

During execution, the council shows an animated panel with progress:

```
╭───────────────────────  Alias Council  ────────────────────────╮
│                                                                 │
│  👑 Chairman: Red Team Agent (gpt-4o)                          │
│                                                                 │
│  ⠋ Stage 1: Collecting responses from council members          │
│      ██████████░░░░░░░░░░ 2/3                                  │
│       ✓   gpt-4o                                               │
│       ✓   gpt-5                                                │
│       ⠋   alias1                                               │
│                                                                 │
│  ○ Stage 2: Waiting...                                         │
│                                                                 │
│  💰 $0.012 (1.2k in / 800 out) ⏱ 15.2s                        │
│                                                                 │
╰─────────────────────────────────────────────────────────────────╯
```

## Performance Considerations

| Metric | Single Query | Council (3 models) |
|--------|--------------|-------------------|
| API Calls | 1 | ~7 (2N + 1) |
| Cost | 1x | 3-4x |
| Latency | 1x | 2-3x |
| Accuracy | Base | Improved |

!!! tip "When to Use Council"
    Use the council when accuracy matters more than speed or cost. It's particularly valuable for:

    - Complex security decisions
    - Architecture recommendations
    - Vulnerability assessments
    - Strategic planning tasks

## Troubleshooting

### Debug Mode

Enable detailed logging to diagnose issues:

```bash
export CAI_COUNCIL_DEBUG=1
```

### Common Issues

**"All models failed to respond"**

- Verify API keys are set correctly
- Check model names with `/model` command
- Check for rate limiting

**Council hangs on Stage 1**

- Model name might be incorrect (verify with `/model`)
- API key invalid or missing
- Network connectivity issues

**"Temperature not supported"**

- Handled automatically for GPT-5/O1/O3 models (temperature set to 1)

### Test Individual Models

Before using council, verify each model works independently:

```bash
CAI> /model gpt-4o
CAI> What is 2+2?
```

### Minimal Configuration

If experiencing issues, try a minimal setup:

```bash
export CAI_COUNCIL="gpt-4o,gpt-4o-mini"
```

## Credits

Inspired by [llm-council](https://github.com/karpathy/llm-council) by Andrej Karpathy.
