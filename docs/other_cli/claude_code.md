# Claude Code

!!! danger "Third-Party Scaffolding — Privacy & Security Warning"
    Third-party scaffoldings may be serving your data outside your environment.
    For **privacy** and **cybersecurity refusal optimization**, use **CAI** to obtain the best performance.

!!! warning "Support Disclaimer"
    Alias Robotics **does not provide support** for developments or integrations related to Claude Code. This page documents API compatibility only. Alias simply allows usage of the Alias API through your preferred scaffolding.

---

## Step 1: Install Claude Code

### Prerequisites

- **Node.js 18** or newer
- For **macOS**, use [nvm](https://github.com/nvm-sh/nvm) to install Node.js — installing the package directly may cause permission issues
- For **Windows**, additionally install [Git for Windows](https://gitforwindows.org/)

```bash
# Install Claude Code
npm install -g @anthropic-ai/claude-code

# Navigate to your project
cd your-awesome-project

# Launch
claude
```

!!! note
    If macOS users encounter permission issues during installation, use `nvm` to install Node.js.

---

## Step 2: Configure the Alias API

### 1. Get your Alias API Key

An `ALIAS_API_KEY` (format: `sk-...`) can be obtained from either of the following:

- **[CAI PRO](https://aliasrobotics.com/cybersecurityai.php)** — full cybersecurity AI platform with access to `alias1` and other models.
- **[Alias LLMs](https://aliasrobotics.com/aliasLLMs.php)** — acquire `alias2-mini` and other Alias language models directly.

### 2. Configure Environment Variables

Set up environment variables using one of the following methods for macOS/Linux or Windows.

!!! note
    Some commands show no output when setting environment variables — that's normal as long as no errors appear. A new terminal window may be required for the changes to take effect.

#### macOS & Linux

Edit the Claude Code configuration file `~/.claude/settings.json`. Add or modify the `env` fields `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN`.

Replace `your_alias_api_key` with the API Key you obtained in the previous step.

```json
{
    "env": {
        "ANTHROPIC_AUTH_TOKEN": "your_alias_api_key",
        "ANTHROPIC_BASE_URL": "https://api.aliasrobotics.com:666/",
        "API_TIMEOUT_MS": "3000000"
    }
}
```

#### Windows Cmd

Run the following commands in Cmd. Replace `your_alias_api_key` with the API Key you obtained in the previous step.

```cmd
setx ANTHROPIC_AUTH_TOKEN your_alias_api_key
setx ANTHROPIC_BASE_URL https://api.aliasrobotics.com:666/
```

#### Windows PowerShell

Run the following commands in PowerShell. Replace `your_alias_api_key` with the API Key you obtained in the previous step.

```powershell
[System.Environment]::SetEnvironmentVariable('ANTHROPIC_AUTH_TOKEN', 'your_alias_api_key', 'User')
[System.Environment]::SetEnvironmentVariable('ANTHROPIC_BASE_URL', 'https://api.aliasrobotics.com:666/', 'User')
```

---

## Step 3: Start with Claude Code

Once the configuration is complete, start using Claude Code in your terminal:

```bash
cd your-project-directory
claude
```

Token usage and billing will appear in your Alias account.

---

## Related

- [CAI PRO Quickstart](../cai_pro_quickstart.md)
- [Available Models](../cai_list_of_models.md)
- [Environment Variables](../environment_variables.md)
