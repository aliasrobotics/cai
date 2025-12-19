# Ollama Configuration

## Ollama Local (Self-hosted)

#### [Ollama Integration](https://ollama.com/)
For local models using Ollama, add the following to your .env:

```bash
CAI_MODEL=qwen2.5:72b
OLLAMA_API_BASE=http://localhost:8000/v1 # note, maybe you have a different endpoint
```

Make sure that the Ollama server is running and accessible at the specified base URL. You can swap the model with any other supported by your local Ollama instance.

## Ollama Cloud

For cloud models using Ollama Cloud (no GPU required), add the following to your .env:

```bash
# API Key from ollama.com
OLLAMA_API_KEY=your_api_key_here
OLLAMA_API_BASE=https://ollama.com

# Cloud model (note the ollama_cloud/ prefix)
CAI_MODEL=ollama_cloud/gpt-oss:120b
```

**Requirements:**
1. Create an account at [ollama.com](https://ollama.com)
2. Generate an API key from your profile
3. Use models with `ollama_cloud/` prefix (e.g., `ollama_cloud/gpt-oss:120b`)

**Key differences:**
- Prefix: `ollama_cloud/` (cloud) vs `ollama/` (local)
- API Key: Required for cloud, not needed for local
- Endpoint: `https://ollama.com/v1` (cloud) vs `http://localhost:8000/v1` (local)

See [Ollama Cloud documentation](ollama_cloud.md) for detailed setup instructions.
