# Claude Code

!!! danger "Third-Party Scaffolding — Privacy & Security Warning"
    Third-party scaffoldings may be serving your data outside your environment.
    For **privacy** and **cybersecurity refusal optimization**, use **CAI** to obtain the best performance.

Claude Code is Anthropic's official CLI for agentic coding. Because it speaks the **Anthropic API format** natively, it cannot talk directly to the Alias API (which is OpenAI-compatible). A small proxy is required to translate between the two.

!!! warning "Support Disclaimer"
    Alias Robotics **does not provide support** for developments or integrations related to Claude Code. This page documents API compatibility only. Alias simply allows usage of the Alias API through your preferred scaffolding.

---

## How It Works

```
Claude Code  →  Anthropic API format
                        ↓
              claude-code-proxy (localhost:8082)
                        ↓
              OpenAI-compatible format  →  Alias API
```

The proxy ([github.com/1rgs/claude-code-proxy](https://github.com/1rgs/claude-code-proxy)) intercepts Anthropic-format requests from Claude Code and forwards them to any OpenAI-compatible backend — in this case, the Alias API.

---

## Setup

### 1. Get your Alias API Key

An `ALIAS_API_KEY` (format: `sk-...`) can be obtained from either of the following:

- **[CAI PRO](https://aliasrobotics.com/cybersecurityai.php)** — full cybersecurity AI platform with access to `alias1` and other models.
- **[Alias LLMs](https://aliasrobotics.com/aliasLLMs.php)** — acquire `alias2-mini` and other Alias language models directly.

### 2. Clone and configure the proxy

```bash
git clone https://github.com/1rgs/claude-code-proxy.git
cd claude-code-proxy
```

Create a `.env` file:

```bash
# Point to the Alias API
OPENAI_API_KEY="sk-your-alias-api-key-here"
OPENAI_BASE_URL="https://api.aliasrobotics.com:666/"

# Map Claude model names to Alias models
BIG_MODEL="alias1"
SMALL_MODEL="alias1"

PREFERRED_PROVIDER="openai"
```

### 3. Run the proxy

Install `uv` if needed, then start the server:

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8082 --reload
```

Or with Docker:

```bash
docker run -d --env-file .env -p 8082:8082 ghcr.io/1rgs/claude-code-proxy:latest
```

### 4. Launch Claude Code via the proxy

```bash
ANTHROPIC_BASE_URL=http://localhost:8082 claude
```

To avoid setting this every time, export it in your shell profile:

```bash
echo 'export ANTHROPIC_BASE_URL=http://localhost:8082' >> ~/.zshrc
```

---

## Verification

Inside Claude Code, run a quick prompt and confirm the response is served via `alias1`. Token usage and billing will appear in your Alias account.

---

## Related

- [CAI PRO Quickstart](../cai_pro_quickstart.md)
- [Available Models](../cai_list_of_models.md)
- [Environment Variables](../environment_variables.md)
