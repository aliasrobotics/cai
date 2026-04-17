# Quickstart

!!! tip "🚀 Upgrade to CAI PRO"
    Get access to unrestricted `alias1` model, Terminal UI with parallel agents, and professional support. Perfect for security professionals and teams.
    **[Explore CAI PRO features →](cai_pro.md)**

To start CAI after installing it, just type `cai` in the CLI:

```bash
└─# cai

          CCCCCCCCCCCCC      ++++++++   ++++++++      IIIIIIIIII
       CCC::::::::::::C  ++++++++++       ++++++++++  I::::::::I
     CC:::::::::::::::C ++++++++++         ++++++++++ I::::::::I
    C:::::CCCCCCCC::::C +++++++++    ++     +++++++++ II::::::II
   C:::::C       CCCCCC +++++++     +++++     +++++++   I::::I
  C:::::C                +++++     +++++++     +++++    I::::I
  C:::::C                ++++                   ++++    I::::I
  C:::::C                 ++                     ++     I::::I
  C:::::C                  +   +++++++++++++++   +      I::::I
  C:::::C                    +++++++++++++++++++        I::::I
  C:::::C                     +++++++++++++++++         I::::I
   C:::::C       CCCCCC        +++++++++++++++          I::::I
    C:::::CCCCCCCC::::C         +++++++++++++         II::::::II
     CC:::::::::::::::C           +++++++++           I::::::::I
       CCC::::::::::::C             +++++             I::::::::I
          CCCCCCCCCCCCC               ++              IIIIIIIIII

                      Cybersecurity AI (CAI), v0.4.0
                          Bug bounty-ready AI

CAI>
```

That should initialize CAI and provide a prompt to execute any security task you want to perform. The navigation bar at the bottom displays important system information. This information helps you understand your environment while working with CAI.

Here's a quick [demo video](https://asciinema.org/a/zm7wS5DA2o0S9pu1Tb44pnlvy) to help you get started with CAI. We'll walk through the basic steps — from launching the tool to running your first AI-powered task in the terminal. Whether you're a beginner or just curious, this guide will show you how easy it is to begin using CAI.

### Autonomous Mode with --continue

CAI can run autonomously using the `--continue` flag, which makes agents automatically continue their work without waiting for user input:

```bash
# Have CAI tell security jokes continuously
cai --continue --prompt "tell me a joke about security"

# Run autonomous security audit
cai --continue --prompt "perform security audit of authentication system"

# Hunt for vulnerabilities automatically
cai --continue --prompt "find SQL injection vulnerabilities"
```

With `--continue`, CAI will:
- Analyze the conversation context after each turn
- Generate intelligent continuation prompts
- Keep working until the task is complete or interrupted

See the [Continue Mode Guide](continue_mode.md) for detailed information.

From here on, type on `CAI` and start your security exercise. Best way to learn is by example:

### Environment Variables

??? "List of Environment Variables"

    | Variable | Description |
    |----------|-------------|
    | CTF_NAME | Name of the CTF challenge to run (e.g. "picoctf_static_flag") |
    | CTF_CHALLENGE | Specific sub challenge name within the CTF to test (e.g. CTF_NAME="kiddoctf" contains 4 subchallenges. For running one of them: "01 linux i") |
    | CTF_SUBNET | Network subnet for the CTF container |
    | CTF_IP | IP address for the CTF container |
    | CTF_INSIDE | Whether to conquer the CTF from within container |
    | CAI_MODEL | Model to use for agents |
    | ⚠️ CAI_DEBUG | Set debug output level (0: Only tool outputs, 1: Verbose debug output, 2: CLI debug output) |
    | ⚠️ CAI_BRIEF | Enable/disable brief output mode |
    | CAI_MAX_TURNS | Maximum number of turns for agent interactions |
    | ⚠️ CAI_TRACING | Enable/disable OpenTelemetry tracing |
    | CAI_AGENT_TYPE | Specify the agents to use (e.g. "boot2root") |
    | CAI_PRICE_LIMIT | Price limit for the conversation in dollars |
    | CAI_WORKSPACE | Defines the name of the workspace |
    | CAI_GUARDRAILS | Enable/disable guardrails for prompt injection protection (default: true) |


## Setting Environment Variables

There are several ways to configure environment variables for CAI:

---

#### 1. Using the `.env` file

```
# Add any env variable to your .env file
CAI_PRICE_LIMIT="0.004"
CAI_MODEL="qwen2.5:72b"
```

#### 2. Command-line parameters

Pass variables directly when launching CAI

```
CAI_PRICE_LIMIT="0.004" CAI_MODEL="qwen2.5:72b" cai
```

#### 3. Runtime configuration

After running CAI, use **`/env`** (the catalog).

```
  /env set <#|NAME> <value...>   # set a catalog variable
  /env list                      # numbered catalog + live values
  /env default                   # restore catalog defaults
```

```
  cai
  /env list
  # Pick the catalog index or variable name from the first column
  /env set 18 "0.004"
```
