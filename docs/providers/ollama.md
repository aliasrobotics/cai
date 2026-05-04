# Ollama Configuration

## Ollama Local (Self-hosted)

#### [Ollama Integration](https://ollama.com/)

For local Ollama models, point CAI at Ollama's OpenAI-compatible endpoint and use the `ollama/` model prefix:

```bash
# Start Ollama separately, then configure CAI
export OLLAMA_API_BASE="http://localhost:11434/v1"
export CAI_MODEL="ollama/qwen2.5:7b"
export CAI_PRICE_LIMIT="0"
export CAI_STREAM="false"

cai
```

Notes:

- Use the `ollama/` prefix in `CAI_MODEL`. Without it, LiteLLM may not route the request through the Ollama provider.
- Include `/v1` in `OLLAMA_API_BASE`. CAI appends the chat completions path through the OpenAI-compatible client.
- Ollama's default local port is `11434`. If you expose Ollama through Docker or another host, keep the same `/v1` suffix on that base URL.
- A local Ollama setup does not require `OLLAMA_API_KEY`.

Quick checks:

```bash
ollama --version
ollama list
curl http://localhost:11434/api/version
```

If CAI reports a `404 page not found` from Ollama, check both values:

```bash
echo "$CAI_MODEL"        # should look like ollama/<model-name>
echo "$OLLAMA_API_BASE"  # should look like http://localhost:11434/v1
```

## Ollama through an OpenAI-compatible endpoint

If you intentionally want to treat Ollama as a generic OpenAI-compatible endpoint instead of using LiteLLM's Ollama provider, use `OPENAI_BASE_URL` and an `openai/` model prefix:

```bash
export OPENAI_API_KEY="dummy-key"
export OPENAI_BASE_URL="http://127.0.0.1:11434/v1"
export CAI_MODEL="openai/qwen2.5:7b"
export CAI_PRICE_LIMIT="0"
export CAI_STREAM="false"

cai
```

Use this mode for endpoints that speak the OpenAI chat-completions API directly. For normal local Ollama usage, prefer the `OLLAMA_API_BASE` + `ollama/` configuration above.

## Ollama Cloud

For cloud models using Ollama Cloud (no local GPU required), add the following to your `.env`:

```bash
# API key from ollama.com
OLLAMA_API_KEY=your_api_key_here
OLLAMA_API_BASE=https://ollama.com

# Cloud model: note the ollama_cloud/ prefix
CAI_MODEL=ollama_cloud/gpt-oss:120b
```

Requirements:

1. Create an account at [ollama.com](https://ollama.com).
2. Generate an API key from your profile.
3. Use models with the `ollama_cloud/` prefix, for example `ollama_cloud/gpt-oss:120b`.

Key differences:

- Prefix: `ollama/` for local Ollama, `ollama_cloud/` for Ollama Cloud.
- API key: not required for local Ollama, required for Ollama Cloud.
- Endpoint: `http://localhost:11434/v1` for local Ollama, `https://ollama.com` for Ollama Cloud.

See [Ollama Cloud documentation](ollama_cloud.md) for detailed setup instructions.
