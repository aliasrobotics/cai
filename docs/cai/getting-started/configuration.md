# Configuration

## Environment Variables

CAI leverages the `.env` file to load configuration at launch. To facilitate the setup, the repo provides an exemplary [`.env.example`](.env.example) file provides a template for configuring CAI's setup and your LLM API keys to work with desired LLM models.

⚠️  Important:

CAI does NOT provide API keys for any model by default. Don't ask us to provide keys, use your own or host your own models.

⚠️  Note:

The OPENAI_API_KEY must not be left blank. It should contain either "sk-123" (as a placeholder) or your actual API key. See https://github.com/aliasrobotics/cai/issues/27.

### List of Environment Variables

For a complete reference organized by use case, see [Environment Variables Reference](../../environment_variables.md).

| Variable | Description | Default |
|----------|-------------|---------|
| CTF_NAME | Name of the CTF challenge to run (e.g. "picoctf_static_flag") | - |
| CTF_CHALLENGE | Specific challenge name within the CTF to test | - |
| CTF_SUBNET | Network subnet for the CTF container | 192.168.3.0/24 |
| CTF_IP | IP address for the CTF container | 192.168.3.100 |
| CTF_INSIDE | Whether to conquer the CTF from within container | true |
| CAI_MODEL | Model to use for agents | alias1 |
| CAI_DEBUG | Set debug output level (0: Only tool outputs, 1: Verbose debug output, 2: CLI debug output) | 1 |
| CAI_BRIEF | Enable/disable brief output mode | false |
| CAI_MAX_TURNS | Maximum number of turns for agent interactions | inf |
| CAI_MAX_INTERACTIONS | Maximum number of interactions (tool calls, agent actions, etc.) allowed in a session. If exceeded, only CLI commands are allowed until increased. If force_until_flag=true, the session will exit | inf |
| CAI_PRICE_LIMIT | Price limit for the conversation in dollars. If exceeded, only CLI commands are allowed until increased. If force_until_flag=true, the session will exit | 1 |
| CAI_TRACING | Enable/disable OpenTelemetry tracing. When enabled, traces execution flow and agent interactions for debugging and analysis | true |
| CAI_AGENT_TYPE | Specify the agents to use (e.g., boot2root, one_tool, redteam_agent). Use "/agent" command in CLI to list all available agents | redteam_agent |
| CAI_STATE | Enable/disable stateful mode. When enabled, the agent will use a state agent to keep track of the state of the network and the flags found | false |
| CAI_MEMORY | Enable/disable memory mode (episodic: use episodic memory, semantic: use semantic memory, all: use both episodic and semantic memory) | false |
| CAI_MEMORY_ONLINE | Enable/disable online memory mode | false |
| CAI_MEMORY_OFFLINE | Enable/disable offline memory | false |
| CAI_ENV_CONTEXT | Add environment context, dirs and current env available | true |
| CAI_MEMORY_ONLINE_INTERVAL | Number of turns between online memory updates | 5 |
| CAI_SUPPORT_MODEL | Model to use for the support agent | o3-mini |
| CAI_SUPPORT_INTERVAL | Number of turns between support agent executions | 5 |
| CAI_STREAM | Enable/disable streaming output in rich panel | false |
| CAI_TELEMETRY | Enable/disable telemetry | true |
| CAI_PARALLEL | Number of parallel agent instances to run. When set to values greater than 1, executes multiple instances of the same agent in parallel and displays all results | 1 |
| CAI_GUARDRAILS | Enable/disable security guardrails for agents. When set to "true", applies security guardrails to prevent potentially dangerous outputs and inputs | false |
| CAI_GCTR_NITERATIONS | Number of tool interactions before triggering GCTR (Generative Cut-The-Rope) analysis in bug_bounter_gctr agent. Only applies when using gctr-enabled agents | 5 |
| CAI_ACTIVE_CONTAINER | Docker container ID where commands should be executed. When set, shell commands and tools execute inside the specified container instead of the host. Automatically set when CTF challenges start (if CTF_INSIDE=true) or when switching containers via /virtualization command | - |

## Custom OpenAI Base URL Support

CAI supports configuring a custom OpenAI API base URL via the `OPENAI_BASE_URL` environment variable. This allows users to redirect API calls to a custom endpoint, such as a proxy or self-hosted OpenAI-compatible service.

Example `.env` entry configuration:
```
OLLAMA_API_BASE="https://custom-openai-proxy.com/v1"
```

Or directly from the command line:
```bash
OLLAMA_API_BASE="https://custom-openai-proxy.com/v1" cai
```

## OpenRouter Integration

The Cybersecurity AI (CAI) platform offers seamless integration with OpenRouter, a unified interface for Large Language Models (LLMs). This integration is crucial for users who wish to leverage advanced AI capabilities in their cybersecurity tasks. OpenRouter acts as a bridge, allowing CAI to communicate with various LLMs, thereby enhancing the flexibility and power of the AI agents used within CAI.

To enable OpenRouter support in CAI, you need to configure your environment by adding specific entries to your `.env` file. This setup ensures that CAI can interact with the OpenRouter API, facilitating the use of sophisticated models like Meta-LLaMA. Here's how you can configure it:

```bash
CAI_AGENT_TYPE=redteam_agent
CAI_MODEL=openrouter/meta-llama/llama-4-maverick
OPENROUTER_API_KEY=<sk-your-key>  # note, add yours
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
``` 