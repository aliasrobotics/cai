# OpenAI-Compatible Providers

CAI can talk to OpenAI-compatible endpoints through LiteLLM. This includes self-hosted proxies and hosted APIs that expose OpenAI-style chat completions, such as OCI Generative AI endpoints fronted by LiteLLM.

## Configuration

Use `OPENAI_BASE_URL` for the endpoint and make the model explicit with the `openai/` prefix:

```bash
export OPENAI_API_KEY="<your-api-key-or-placeholder>"
export OPENAI_BASE_URL="https://example.com/litellm/v1"
export CAI_MODEL="openai/gpt-4.1"
export CAI_STREAM="false"

cai
```

Why the prefix matters:

- `OPENAI_BASE_URL` applies to OpenAI-compatible routing.
- The `openai/` prefix tells LiteLLM to route the model through the OpenAI provider path.
- Without the prefix, CAI may treat the model as another provider or as a default Alias model, so the custom base URL can appear to be ignored.

## Local OpenAI-compatible server example

For a local server that exposes `/v1/chat/completions`:

```bash
export OPENAI_API_KEY="dummy-key"
export OPENAI_BASE_URL="http://127.0.0.1:8000/v1"
export CAI_MODEL="openai/<model-name>"
export CAI_PRICE_LIMIT="0"

cai
```

## Ollama note

For normal local Ollama usage, prefer the dedicated Ollama provider configuration:

```bash
export OLLAMA_API_BASE="http://localhost:11434/v1"
export CAI_MODEL="ollama/qwen2.5:7b"
```

If you intentionally want to treat Ollama as a generic OpenAI-compatible endpoint, use:

```bash
export OPENAI_API_KEY="dummy-key"
export OPENAI_BASE_URL="http://127.0.0.1:11434/v1"
export CAI_MODEL="openai/qwen2.5:7b"
```

## Troubleshooting

- `OPENAI_BASE_URL` appears ignored: check that `CAI_MODEL` starts with `openai/`.
- `404 page not found`: confirm the base URL includes `/v1` and that the endpoint supports OpenAI chat completions.
- Authentication errors: confirm the API key required by your proxy/provider is in `OPENAI_API_KEY`.
- Streaming errors: retry with `CAI_STREAM=false` to isolate endpoint compatibility from streaming behavior.
