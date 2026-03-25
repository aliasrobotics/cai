# OpenCode

!!! danger "Third-Party Scaffolding — Privacy & Security Warning"
    Third-party scaffoldings may be serving your data outside your environment.
    For **privacy** and **cybersecurity refusal optimization**, use **CAI** to obtain the best performance.

[OpenCode](https://opencode.ai) is an open-source, terminal-based AI coding assistant. It supports OpenAI-compatible providers, which means the Alias API can be plugged in directly without any proxy.

!!! warning "Support Disclaimer"
    Alias Robotics **does not provide support** for developments or integrations related to OpenCode. This page documents API compatibility only. Alias simply allows usage of the Alias API through your preferred scaffolding.

---

## Setup

### 1. Get your Alias API Key

An `ALIAS_API_KEY` (format: `sk-...`) can be obtained from either of the following:

- **[CAI PRO](https://aliasrobotics.com/cybersecurityai.php)** — full cybersecurity AI platform with access to `alias1` and other models.
- **[Alias LLMs](https://aliasrobotics.com/aliasLLMs.php)** — acquire `alias2-mini` and other Alias language models directly.

### 2. Install OpenCode

```bash
npm install -g opencode-ai
```

Or via Homebrew (macOS):

```bash
brew install sst/tap/opencode
```

### 3. Configure the Alias provider

OpenCode uses a `~/.config/opencode/config.json` file. Add a custom OpenAI-compatible provider pointing to the Alias API:

```json
{
  "provider": {
    "alias": {
      "api": "https://api.aliasrobotics.com:666/",
      "name": "Alias Robotics",
      "env": ["ALIAS_API_KEY"]
    }
  },
  "model": "alias/alias1"
}
```

Then export your key:

```bash
export ALIAS_API_KEY="sk-your-alias-api-key-here"
```

### 4. Run OpenCode

```bash
opencode
```

OpenCode will pick up the configured provider and route requests to the Alias API.

---

## Alternative: environment variable approach

If you prefer not to edit the config file, OpenCode also respects standard OpenAI environment variables:

```bash
export OPENAI_API_KEY="sk-your-alias-api-key-here"
export OPENAI_BASE_URL="https://api.aliasrobotics.com:666/"
opencode --model alias1
```

---

## Notes

- Use `alias1` for best cybersecurity performance, or `alias0` for a faster, lighter alternative.
- Token usage and billing appear in your Alias account dashboard.

---

## Related

- [CAI PRO Quickstart](../cai_pro_quickstart.md)
- [Available Models](../cai_list_of_models.md)
- [Environment Variables](../environment_variables.md)
