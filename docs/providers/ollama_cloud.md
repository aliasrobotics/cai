# Ollama Cloud

Run large language models without local GPU using Ollama's cloud service.

## Quick Start

### 1. Get API Key

- Create account at [ollama.com](https://ollama.com)
- Generate API key from your profile

### 2. Configure `.env`

```bash
OLLAMA_API_KEY=your_api_key_here
OLLAMA_API_BASE=https://ollama.com
CAI_MODEL=ollama_cloud/gpt-oss:120b
```

### 3. Run

```bash
cai
```

## Available Models

View in CAI with `/model-show` under "Ollama Cloud" category:

- `ollama_cloud/gpt-oss:120b` - General purpose 120B model
- `ollama_cloud/llama3.3:70b` - Llama 3.3 70B
- `ollama_cloud/qwen2.5:72b` - Qwen 2.5 72B
- `ollama_cloud/deepseek-v3:671b` - DeepSeek V3 671B

More models at [ollama.com/library](https://ollama.com/library).

## Model Selection

```bash
# By name
CAI> /model ollama_cloud/gpt-oss:120b

# By number (after /model-show)
CAI> /model 3
```

## Local vs Cloud

| Feature | Local | Cloud |
|---------|-------|-------|
| Prefix | `ollama/` | `ollama_cloud/` |
| API Key | Not required | Required |
| Endpoint | `http://localhost:8000/v1` | `https://ollama.com/v1` |
| GPU | Required | Not required |

## Troubleshooting

**Unauthorized error**: Verify `OLLAMA_API_KEY` is set correctly

**Path not found**: Ensure `OLLAMA_API_BASE=https://ollama.com` (without `/v1`)

**Model not listed**: Check model prefix is `ollama_cloud/`, not `ollama/`

## Validation

Test connection with curl:

```bash
curl https://ollama.com/v1/chat/completions \
  -H "Authorization: Bearer $OLLAMA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-oss:120b", "messages": [{"role": "user", "content": "test"}]}'
```

## References

- [Ollama Cloud Docs](https://ollama.com/docs/cloud)
- [Model Library](https://ollama.com/library)
- [Get API Key](https://ollama.com/settings/keys)
