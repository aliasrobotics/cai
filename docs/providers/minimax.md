# MiniMax Configuration

#### [MiniMax AI](https://www.minimax.io/)

MiniMax provides large language models with an OpenAI-compatible API. CAI includes a built-in `MiniMaxProvider` for easy integration.

## Setup

1. Get an API key from [MiniMax](https://platform.minimax.chat/).
2. Set the environment variable:

```bash
export MINIMAX_API_KEY=<your-api-key>
```

## Usage

### Option 1: Using MiniMaxProvider (Recommended)

```python
from cai.sdk.agents import Agent, Runner, RunConfig
from cai.sdk.agents.models.minimax_provider import MiniMaxProvider

provider = MiniMaxProvider()

agent = Agent(
    name="assistant",
    instructions="You are a helpful assistant.",
)

result = await Runner.run(
    agent,
    "Hello!",
    run_config=RunConfig(model_provider=provider),
)
```

### Option 2: Using environment variables with LiteLLM

```bash
CAI_MODEL=openai/MiniMax-M2.7
MINIMAX_API_KEY=<your-api-key>
OPENAI_API_BASE=https://api.minimax.io/v1
```

### Option 3: Direct model on Agent

```python
from openai import AsyncOpenAI
from cai.sdk.agents import Agent, OpenAIChatCompletionsModel

client = AsyncOpenAI(
    api_key="<your-api-key>",
    base_url="https://api.minimax.io/v1",
)

agent = Agent(
    name="assistant",
    instructions="You are a helpful assistant.",
    model=OpenAIChatCompletionsModel(
        model="MiniMax-M2.7",
        openai_client=client,
    ),
)
```

## Available Models

| Model | Context Window | Description |
|-------|---------------|-------------|
| `MiniMax-M2.7` | 1M tokens | Latest and most capable model |
| `MiniMax-M2.5` | 1M tokens | Strong general-purpose model |
| `MiniMax-M2.5-highspeed` | 204K tokens | Optimized for speed |

## Notes

- MiniMax uses an OpenAI-compatible API, so it works with `OpenAIChatCompletionsModel`.
- Tracing is sent to OpenAI by default. If you don't have an OpenAI API key, disable tracing with `set_tracing_disabled(True)` or set a tracing-specific key.
- Temperature range: `[0.0, 1.0]`.
