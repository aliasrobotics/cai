# OpenRouter Configuration

#### [OpenRouter Integration](https://openrouter.ai/)

To enable OpenRouter support in CAI, you need to configure your environment by adding specific entries to your `.env` file. This setup ensures that CAI can interact with the OpenRouter API, facilitating the use of sophisticated models like Meta-LLaMA. Here’s how you can configure it:

```bash
CAI_MODEL=openrouter/meta-llama/llama-4-maverick
OPENROUTER_API_KEY=<sk-your-key>  # note, add yours
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
```
