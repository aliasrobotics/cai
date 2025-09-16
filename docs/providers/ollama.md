# Ollama Configuration

#### [Ollama Integration](https://ollama.com/)
For local models using Ollama, add the following to your .env:

```bash
CAI_MODEL=qwen2.5:72b
OLLAMA_API_BASE=http://localhost:8000/v1 # note, maybe you have a different endpoint
```

Make sure that the Ollama server is running and accessible at the specified base URL. You can swap the model with any other supported by your local Ollama instance.
