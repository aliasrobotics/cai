# Codex CLI

!!! danger "Third-Party Scaffolding — Privacy & Security Warning"
    Third-party scaffoldings may be serving your data outside your environment.
    For **privacy** and **cybersecurity refusal optimization**, use **CAI** to obtain the best performance.

[Codex CLI](https://github.com/openai/codex) is OpenAI's open-source terminal-based AI coding agent. Because it uses the **OpenAI API format** natively, it can connect directly to the Alias API without any proxy.

!!! warning "Support Disclaimer"
    Alias Robotics **does not provide support** for developments or integrations related to Codex CLI. This page documents API compatibility only. Alias simply allows usage of the Alias API through your preferred scaffolding.

---

## Setup

### 1. Get your Alias API Key

An `ALIAS_API_KEY` (format: `sk-...`) can be obtained from either of the following:

- **[CAI PRO](https://aliasrobotics.com/cybersecurityai.php)** — full cybersecurity AI platform with access to `alias1` and other models.
- **[Alias LLMs](https://aliasrobotics.com/aliasLLMs.php)** — acquire `alias2-mini` and other Alias language models directly.

### 2. Install Codex CLI

```bash
npm install -g @openai/codex
```

### 3. Configure environment variables

```bash
export OPENAI_API_KEY="sk-your-alias-api-key-here"
export OPENAI_BASE_URL="https://api.aliasrobotics.com:666/"
```

To persist these, add them to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.):

```bash
echo 'export OPENAI_API_KEY="sk-your-alias-api-key-here"' >> ~/.zshrc
echo 'export OPENAI_BASE_URL="https://api.aliasrobotics.com:666/"' >> ~/.zshrc
source ~/.zshrc
```

### 4. Run Codex with an Alias model

```bash
codex --model alias1
```

Or set the model inline per session:

```bash
OPENAI_API_KEY="sk-your-alias-api-key-here" \
OPENAI_BASE_URL="https://api.aliasrobotics.com:666/" \
codex --model alias1
```

---

## Notes

- The Alias API is fully OpenAI-compatible — no additional configuration is required beyond pointing the base URL and API key.
- Use `alias1` for best cybersecurity performance, or `alias0` for a faster, lighter alternative.
- Token usage and billing appear in your Alias account dashboard.

---

## Related

- [CAI PRO Quickstart](../cai_pro_quickstart.md)
- [Available Models](../cai_list_of_models.md)
- [Environment Variables](../environment_variables.md)
