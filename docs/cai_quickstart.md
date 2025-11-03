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

After running CAI, use `/config`

```
  /config set <number> <value> to configure a variable # see `config.py` or type `/help`

```

```
  cai
  /config # It will display a panel with all the environment variables.
        # You must pick its reference NUMBER (1st column left)
  # `18` is the corresponding number for CAI_PRICE_LIMIT
  /config set 18 "0.004"
```
