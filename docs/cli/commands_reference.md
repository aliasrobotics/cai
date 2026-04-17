# CAI CLI and REPL commands reference

This page documents flags accepted by the `cai` binary and slash commands in the **CLI** interactive REPL. For **Textual TUI** shortcuts, multi-terminal routing, and UI-only behavior, see the [TUI commands reference](../tui/commands_reference.md).

---

## On this page

1. [Binary `cai` CLI flags](#binary-cai-cli-flags)
2. [REPL syntax](#repl-syntax)
3. [Agents and models](#agents-and-models)
4. [Conversation and context](#conversation-and-context)
5. [Memory](#memory)
6. [Parallel execution and queues](#parallel-execution-and-queues)
7. [Configuration and environment](#configuration-and-environment)
8. [Integrations](#integrations)
9. [System and processes](#system-and-processes)
10. [Utilities](#utilities)
11. [Quick reference table](#quick-reference-table)
12. [Commands registered](#commands-registered)
13. [Next steps](#next-steps)

---

## Binary `cai` CLI flags

The binary parses known flags and treats **unrecognized tokens as an initial prompt** (positional prompt text), similar to `parse_known_args()` semantics.


| Flag                 | Type     | Default   | Description                                                                           |
| -------------------- | -------- | --------- | ------------------------------------------------------------------------------------- |
| `--tui`              | flag     | false     | Start CAI in Textual TUI (multi-terminal). Sets `CAI_TUI_MODE=true`.                  |
| `--yaml FILE`        | option   | —         | Load parallel agent definitions from a YAML file.                                     |
| `--prompt TEXT`      | option   | —         | Initial prompt executed immediately on startup.                                       |
| `--version`          | flag     | false     | Print `cai-framework` version and exit.                                               |
| `--update`           | flag     | false     | Check for updates and install if available. Requires `ALIAS_API_KEY`.                 |
| `--continue` / `-c`  | flag     | false     | Enable auto-continue mode (`CAI_CONTINUE_MODE=true`).                                 |
| `--resume [SESSION]` | optional | —         | Resume a prior session: `last`, `list`, a session id, or path to a `.jsonl` log.      |
| `--logpath PATH`     | option   | —         | Custom log directory (often used with `--resume`).                                    |
| `--unrestricted`     | flag     | false     | Enable abliteration steering: `CAI_UNRESTRICTED=true`.                                |
| `--yolo`             | flag     | false     | Skip confirmation for sensitive commands (`CAI_YOLO=true`). **Insecure.**             |
| `--api`              | flag     | false     | Run CAI as an HTTP API backend (FastAPI + uvicorn). See [CAI API Backend](../api.md). |
| `--api-host`         | option   | 127.0.0.1 | API bind host. Env: `CAI_API_HOST`.                                                   |
| `--api-port`         | int      | 8000      | API bind port. Env: `CAI_API_PORT`.                                                   |
| `--api-reload`       | flag     | false     | Uvicorn auto-reload. Env: `CAI_API_RELOAD`.                                           |
| `--api-workers`      | int      | 1         | Uvicorn workers. Env: `CAI_API_WORKERS`.                                              |


**API mode:** operational details, auth headers, and routes are documented in [CAI API Backend](../api.md). For a single list of all binary flags, stay on this page; the API doc focuses on HTTP behavior.

**Example (non-interactive prompt):**

```bash
cai --prompt "Summarize SSH hardening for Ubuntu 22.04"
```

---

## REPL syntax

```text
/command [subcommand] [arguments ...]
```

Aliases are listed per command. Arguments in `[]` are optional; `|` means alternatives.

In **Example** sections below, lines starting with `CAI>` are commands you type; other lines are **representative** REPL output (exact text, tables, and colors vary by build and environment).

---

## Agents and models

### `/agent` (`/a`)

Manage and switch agents.


| Subcommand | Arguments               | Description                                             |
| ---------- | ----------------------- | ------------------------------------------------------- |
| `list`     | —                       | List available agents and parallel patterns.            |
| `select`   | name / number / pattern | Switch to the given agent; transfers history.           |
| `info`     | [name / number]         | Detailed info: key, model, tools, handoffs, guardrails. |
| `current`  | —                       | Active agent configuration (in TUI: all terminals).     |
| `new`      | —                       | Create a new agent interactively.                       |


- **No arguments:** same as `/agent current`.
- **Shortcut:** `/agent red_teamer` is equivalent to `/agent select red_teamer`.

**Example:**

```text
CAI> /agent list
… table of agents, models, and ids (layout varies by build) …

CAI> /agent select red_teamer
Switched to agent: red_teamer

CAI> /agent
… same as /agent current: active agent, model, tools summary …
```

### `/model` (`/mod`)

View or change the active LLM. The LiteLLM-backed catalog is under the `**show**` subcommand (for example `**/model show**` or `**/mod show**`).


| Usage                            | Description                                                                                        |
| -------------------------------- | -------------------------------------------------------------------------------------------------- |
| `/model` (no extra args)         | Prints the current model and a numbered table of predefined models (with pricing where available). |
| `/model <name>`                  | Sets the model by name (typically via `CAI_MODEL`), e.g. `/model gpt-4o`.                          |
| `/model <n>`                     | Selects by number from the last displayed table, e.g. `/model 5`.                                  |
| `/model show`                    | Lists LiteLLM-backed models (full catalog). Use `/model` / `/model <n>` to switch after choosing.  |
| `/model show supported`          | Same catalog filtered to models with function-calling support.                                     |
| `/model show <search>`           | Filter the catalog by substring.                                                                   |
| `/model show supported <search>` | Filter to supported models matching a substring.                                                   |


**Examples:**

```text
CAI> /model
Current model: alias1
… numbered shortcuts / pricing table …

CAI> /model gpt-4o
Model set to gpt-4o

CAI> /model show ollama
… LiteLLM rows whose id/name contains "ollama" …

CAI> /mod show supported
… catalog filtered to function-calling models …
```

---

## Conversation and context

### `/flush` (`/clear`)

Clear conversation history.


| Subcommand | Arguments | Description                                          |
| ---------- | --------- | ---------------------------------------------------- |
| `all`      | —         | Clear **all** agents, plus sudo cache and allowlist. |
| `agent`    | name      | Clear history for one agent.                         |


- **CLI, no args:** interactive menu of agents that have history.
- **TUI, no args:** clears **only** the current terminal.
- **Shortcut:** `/flush Red Teamer` or `/flush P2` clears by display name or agent id.

**Example:**

```text
CAI> /flush agent red_teamer
Cleared history for red_teamer.

CAI> /flush all
Cleared all agent histories (and related caches per build).
```

### `/compact` (`/cmp`)

Summarize the conversation into memory.


| Subcommand | Arguments                 | Description                       |
| ---------- | ------------------------- | --------------------------------- |
| `model`    | name / number / `default` | Model used for compaction.        |
| `prompt`   | text / `reset`            | Custom summarization prompt.      |
| `status`   | —                         | Show current compaction settings. |


Inline flags: `--model …`, `--prompt …`. **No args:** in parallel mode compacts all; in single-agent / TUI shows a menu.

**Example:**

```text
CAI> /compact status
Compaction model: default  |  custom prompt: (none)

CAI> /compact
… summary written to memory / thread shortened (wording varies) …
```

### `/history` (`/his`)

History with optional filtering.


| Subcommand | Arguments | Description                  |
| ---------- | --------- | ---------------------------- |
| `all`      | —         | Full history for all agents. |
| `agent`    | name      | History for one agent.       |
| `search`   | term      | Search the history.          |
| `index`    | —         | Message index.               |


**No arguments:** interactive control panel.

**Example:**

```text
CAI> /history search "nmap"
… matching transcript excerpts …

CAI> /history agent red_teamer
… recent messages for that agent …
```

### `/load` (`/l`)

Load JSONL into context.


| Subcommand | Arguments | Description                        |
| ---------- | --------- | ---------------------------------- |
| `agent`    | [path]    | Load history for the active agent. |
| `all`      | [path]    | Load for all agents.               |
| `parallel` | [path]    | Load into parallel configuration.  |
| `load-all` | —         | Load all available logs.           |


**No arguments:** load from `logs/last`.

**Example:**

```text
CAI> /load session_2025-04-01.jsonl
Loaded conversation from session_2025-04-01.jsonl
```

### `/merge` (`/mrg`)

Shortcut for `/parallel merge`. Merges parallel contexts into the main thread and exits parallel mode.

**Example:**

```text
CAI> /merge
… merged parallel branches into main; returned to single-agent mode …
```

---

## Memory

### `/memory` (`/mem`)

Persistent memory under `~/.cai/memory`.


| Subcommand     | Arguments      | Description                            |
| -------------- | -------------- | -------------------------------------- |
| `list`         | —              | List saved memories.                   |
| `save`         | [name] [agent] | Save conversation as memory.           |
| `apply`        | id / name      | Apply memory to context.               |
| `show`         | id / name      | Show one memory’s content.             |
| `delete`       | id / name      | Delete a memory.                       |
| `remove`       | id / name      | Alias of `delete`.                     |
| `merge`        | id1 id2 …      | Merge multiple memories.               |
| `status`       | —              | Memory subsystem status.               |
| `compact`      | [agent]        | Compact memory for an agent.           |
| `clear`        | —              | Delete all memories.                   |
| `list-applied` | —              | Memories applied to the current agent. |


**No arguments:** control panel. A single id such as `M001` routes to `show`.

**Example:**

```text
CAI> /memory list
M001  pentest-notes-20250401   12 messages
M002  ctf-web-flags            8 messages

CAI> /memory show M001
… saved memory content …
```

---

## Parallel execution and queues

### `/parallel` (`/par`, `/p`)

Configure and run parallel agents.


| Subcommand        | Arguments               | Description                                 |
| ----------------- | ----------------------- | ------------------------------------------- |
| `add`             | agent [`--model` model] | Add an agent to the parallel set.           |
| `list`            | —                       | List configured parallel agents.            |
| `clear`           | —                       | Remove parallel agents (no merge).          |
| `remove`          | agent / index           | Remove one parallel agent.                  |
| `override-models` | model                   | Set a shared model for all parallel agents. |
| `merge`           | [`all` / agent]         | Merge contexts into the main thread.        |
| `prompt`          | agent / `all` `"text"`  | Enqueue a prompt for agent(s).              |
| `run`             | —                       | Run all enqueued prompts in parallel.       |


**No arguments:** show current parallel configuration.

**Example:**

```text
CAI> /parallel list
P1  red_teamer   alias1
P2  blueteam     gpt-4o

CAI> /parallel prompt all "Enumerate TLS on target:443"
… prompts queued …

CAI> /parallel run
… parallel fan-out; per-terminal output in TUI …
```

### `/queue` (`/que`)

Sequential prompt queue.


| Subcommand      | Arguments | Description                   |
| --------------- | --------- | ----------------------------- |
| `show` / `list` | —         | Show queued prompts.          |
| `add`           | `"text"`  | Append a prompt.              |
| `run`           | —         | Run all prompts sequentially. |
| `remove`        | index     | Remove one entry.             |
| `clear`         | —         | Empty the queue.              |
| `next`          | —         | Run only the next prompt.     |
| `load`          | path      | Load prompts from a file.     |


**Example:**

```text
CAI> /queue add "Run nmap -sV on 10.0.0.5"
Queued #1

CAI> /queue show
#1  Run nmap -sV on 10.0.0.5

CAI> /queue run
… runs prompts in order …
```

### `/continue`

Auto-continue mode.


| Subcommand | Description                   |
| ---------- | ----------------------------- |
| `on`       | Set `CAI_CONTINUE_MODE=true`. |
| `off`      | Disable auto-continue.        |
| `status`   | Show state.                   |


**No arguments:** turns the mode **on**.

**Example:**

```text
CAI> /continue status
CAI_CONTINUE_MODE=false

CAI> /continue on
Auto-continue enabled.
```

---

## Configuration and environment

### `/env` (`/e`)

Catalog and edit `CAI_*` and `CTF_*` variables; sensitive values are masked in listings.


| Subcommand | Arguments                | Description                                                                   |
| ---------- | ------------------------ | ----------------------------------------------------------------------------- |
| `list`     | —                        | Numbered catalog with descriptions and current values (default when helpful). |
| `get`      | `VAR` or index           | Print one variable's effective value.                                         |
| `set`      | `VAR` or index, `value…` | Set a variable (by name or by catalog number from `list`).                    |
| `default`  | —                        | Restore catalog defaults where applicable.                                    |


**No arguments / bare `/env`:** compact view of live `CAI_`* / `CTF_`* values (not the full numbered catalog). Piping: `/env \| grep VAR` works in supported terminals.

Alternate assignment style (some builds): `/env set VAR=value` or multiple tokens after `set`.

**Examples:**

```text
CAI> /env list
… numbered catalog: CAI_MODEL, CAI_MAX_TURNS, CTF_NAME, … with current values …

CAI> /env get CAI_MODEL
CAI_MODEL=alias1

CAI> /env set CAI_MODEL gpt-4o
Set CAI_MODEL=gpt-4o

CAI> /env set 18 5.0
Set variable #18 to 5.0   (index 18 from /env list)

CAI> /env
CAI_MODEL=gpt-4o
CAI_MAX_TURNS=100
CTF_NAME=
… other CAI_* / CTF_* keys in this session …

CAI> /env default
… restored defaults where the catalog defines them …
```

### `/settings` (`/set`)

Interactive settings and FAQ.


| Topic                           | Description               |
| ------------------------------- | ------------------------- |
| `faq` / `help` / `troubleshoot` | FAQ and troubleshooting.  |
| `validate` / `check`            | Validate API keys.        |
| `status` / `info`               | System status.            |
| `lang` / `language`             | Language selector.        |
| `ollama` / `local`              | Ollama / local model FAQ. |


**No args:** full-screen interactive UI in CLI; TUI-adapted UI in TUI.

**Example:**

```text
CAI> /settings faq
… opens FAQ / troubleshooting flow …
```

### `/temperature` (`/temp`)

Show or set `CAI_TEMPERATURE` (float `0.0`–`2.0`).

**Example:**

```text
CAI> /temp
CAI_TEMPERATURE=0.7

CAI> /temp 0.2
CAI_TEMPERATURE=0.2
```

### `/topp` (`/top_p`)

Show or set nucleus sampling `CAI_TOP_P` (float `0.0`–`1.0`).

**Example:**

```text
CAI> /topp
CAI_TOP_P=1.0

CAI> /topp 0.9
CAI_TOP_P=0.9
```

---

## Integrations

### `/mcp`

Model Context Protocol servers.


| Subcommand     | Arguments    | Description                                                                 |
| -------------- | ------------ | --------------------------------------------------------------------------- |
| `load`         | url name     | Load an MCP **SSE** server.                                                 |
| `load-stdio`   | command name | Load an MCP **stdio** server (some builds use `/mcp load stdio …` instead). |
| `list`         | —            | Active MCP connections.                                                     |
| `add-to-agent` | agent server | Attach MCP tools to an agent.                                               |


Many builds also support extra helpers (`tools`, `status`, `remove`, …); use `/mcp help` locally.

**Example:**

```text
CAI> /mcp load https://example.com/mcp/sse ctf-tools
Loaded MCP server "ctf-tools" (SSE).

CAI> /mcp list
ctf-tools   SSE   connected
```

### `/api` (`/apikey`)

Manage `ALIAS_API_KEY` in the environment / `.env`.


| Subcommand | Arguments | Description              |
| ---------- | --------- | ------------------------ |
| `show`     | —         | Display key (masked).    |
| `set`      | key       | Persist `ALIAS_API_KEY`. |


**No arguments:** `show`. Shortcut: `/api sk-…` behaves like `/api set sk-…`.

**Example:**

```text
CAI> /api
ALIAS_API_KEY=sk-…xxxx   (masked)

CAI> /api set sk-proj-…
API key saved to environment / .env (path depends on build).
```

### `/auth`

API users and device pairing.


| Subcommand | Arguments         | Description                 |
| ---------- | ----------------- | --------------------------- |
| `add-user` | username password | Add an API user.            |
| `add-ip`   | ip[:port]         | Register an IP for pairing. |


**Example:**

```text
CAI> /auth add-user analyst hunter2
User "analyst" created.

CAI> /auth add-ip 203.0.113.10
Registered pairing for 203.0.113.10
```

---

## System and processes

### `/shell` (`/s`, `$`)

Run the remainder of the line as a shell command.

Examples: `/shell ls -la`, `/s whoami`, `$ nmap -sV 10.0.0.1`

**Example:**

```text
CAI> $ whoami
alice

CAI> /shell ls -la /tmp
total 12
drwxrwxrwt … /tmp
```

### `/workspace` (`/ws`)

Workspace (host or Docker container).


| Subcommand | Arguments | Description                        |
| ---------- | --------- | ---------------------------------- |
| `set`      | path      | Set working directory / workspace. |
| `get`      | —         | Show current workspace.            |
| `ls`       | [path]    | List files.                        |
| `exec`     | command   | Run a command in the workspace.    |
| `copy`     | src dst   | Copy between host and container.   |


**No arguments:** same as `get`.

**Example:**

```text
CAI> /ws get
Workspace: /home/alice/projects/cai-target

CAI> /ws ls src
agent.py  tools.py  …
```

### `/virtualization` (`/virt`)

Docker environments.


| Subcommand | Arguments       | Description      |
| ---------- | --------------- | ---------------- |
| `pull`     | image           | Pull an image.   |
| `run`      | image [options] | Run a container. |


**No arguments:** Docker status. A single non-subcommand argument can select/activate an image as container context (see `/help virtualization` on your build).

**Example:**

```text
CAI> /virt
Docker: running   images: 12   active: cai-kali:latest

CAI> /virt pull kalilinux/kali-rolling
… pull progress …
```

---

## Utilities

### `/help` (`/h`, `/?`)

Built-in help and topic deep-dives.

Example topics: `agent`, `parallel`, `queue`, `memory`, `history`, `compact`, `flush`, `load`, `merge`, `env`, `workspace`, `virtualization`, `mcp`, `shell`, `model`, `graph`, `aliases`, `commands`, `quick`, `quickstart`, `topics`.

Examples: `/help`, `/help parallel`, `/? model`

**Example:**

```text
CAI> /help env
… environment catalog / usage for /env …
```

### `/cost` (`/costs`, `/usage`)


| Subcommand | Description                             |
| ---------- | --------------------------------------- |
| `summary`  | Session summary (default when no args). |
| `models`   | Per-model breakdown.                    |
| `daily`    | Daily costs.                            |
| `sessions` | Per-session costs.                      |
| `reset`    | Reset counters.                         |


**Example:**

```text
CAI> /cost
Session spend: $0.42   tokens in: 120k   tokens out: 18k

CAI> /cost models
alias1   $0.30
gpt-4o   $0.12
```

### `/graph` (`/g`)


| Subcommand | Arguments | Description    |
| ---------- | --------- | -------------- |
| `all`      | —         | Full graph.    |
| `timeline` | —         | Timeline view. |
| `stats`    | —         | Statistics.    |
| `export`   | [path]    | Export graph.  |


**No args:** active agent view. A free argument can select `P1`, `P2`, or an agent name.

**Example:**

```text
CAI> /graph
… ASCII or Rich-rendered interaction graph for the active agent …
```

### `/exit` (`/q`, `/quit`)

Clean exit: telemetry flush, session end, `sys.exit(0)`.

**Example:**

```text
CAI> /exit
Goodbye.
```

### `/quickstart` (`/qs`, `/quick`)

Essential setup instructions and tables (no args).

**Example:**

```text
CAI> /quickstart
… printed checklist: keys, /env list, /model show, agents, … …
```

### `/replay`

Replay a session JSONL.

- Path to `.jsonl`, or no args → `logs/last`.
- Optional trailing **numeric** argument: delay in seconds between actions.
- `stop` / `cancel`: stop in-progress replay (TUI).

Sets `CAI_DISABLE_SESSION_RECORDING=true` while replaying.

**Example:**

```text
CAI> /replay logs/last.jsonl 0.5
… replay with 0.5s delay between actions …
```

### `/resume` (`/r` when registered)

Resume a previous session. Optional:

- `--full` / `-f` — full history.
- Path to `.jsonl`, or session id.
- No args — latest session.

**Example:**

```text
CAI> /resume --full ./logs/session_20250401.jsonl
… session restored with full transcript …
```

### `/sessions` (`/sess`)

List recent sessions; optional count limit or session id / label for details.

**Example:**

```text
CAI> /sessions 5
… last five session ids, paths, and labels …
```

### `/ctr`

Cyber threat reasoning / attack graphs. Optional alias form `ctr` (without leading `/`) in some builds.


| Subcommand | Description                 |
| ---------- | --------------------------- |
| `show`     | Current CTR analysis.       |
| `graph`    | Attack graph visualization. |
| `list`     | Available analyses.         |
| `use`      | Select an analysis.         |
| `open`     | Open dedicated view.        |


**No arguments:** full CTR analysis output.

**Example:**

```text
CAI> /ctr show
… current CTR narrative / indicators …
```

### `/metadebug` (`/md`)

Meta-agent debugging (**TUI**). Requires `CAI_META_AGENT=true`.

**Example:**

```text
CAI> /md
… meta-agent trace / routing (TUI only; requires CAI_META_AGENT=true) …
```

---

## Quick reference table


| Command           | Aliases            | Description                                                       |
| ----------------- | ------------------ | ----------------------------------------------------------------- |
| `/agent`          | `/a`               | Manage and switch agents                                          |
| `/api`            | `/apikey`          | Show or set `ALIAS_API_KEY`                                       |
| `/auth`           | —                  | API users and device pairing                                      |
| `/compact`        | `/cmp`             | Compact conversation to memory                                    |
| `/continue`       | —                  | Auto-continue mode                                                |
| `/cost`           | `/costs`, `/usage` | Usage cost statistics                                             |
| `/ctr`            | `ctr`              | CTR analysis / attack graphs                                      |
| `/env`            | `/e`               | Catalog / get / set / `default` for `CAI_*` and `CTF_*` variables |
| `/exit`           | `/q`, `/quit`      | Exit the REPL                                                     |
| `/flush`          | `/clear`           | Clear conversation history                                        |
| `/graph`          | `/g`               | Interaction graph                                                 |
| `/help`           | `/h`, `/?`         | Help and documentation                                            |
| `/history`        | `/his`             | History with filters                                              |
| `/load`           | `/l`               | Load JSONL into context                                           |
| `/mcp`            | —                  | MCP servers                                                       |
| `/memory`         | `/mem`             | Persistent memory (`~/.cai/memory`)                               |
| `/merge`          | `/mrg`             | Merge parallel contexts                                           |
| `/metadebug`      | `/md`              | Meta-agent debug (TUI)                                            |
| `/model`          | `/mod`             | View or change model; `show` subcommand lists LiteLLM catalog     |
| `/parallel`       | `/par`, `/p`       | Parallel agents                                                   |
| `/queue`          | `/que`             | Sequential prompt queue                                           |
| `/quickstart`     | `/qs`, `/quick`    | Quick start guide                                                 |
| `/replay`         | —                  | Replay JSONL session                                              |
| `/resume`         | `/r`               | Resume session                                                    |
| `/sessions`       | `/sess`            | List recent sessions                                              |
| `/settings`       | `/set`             | Interactive settings / FAQ                                        |
| `/shell`          | `/s`, `$`          | Shell escape                                                      |
| `/temperature`    | `/temp`            | Sampling temperature                                              |
| `/topp`           | `/top_p`           | Top-p sampling                                                    |
| `/virtualization` | `/virt`            | Docker environments                                               |
| `/workspace`      | `/ws`              | Workspace management                                              |


---

## Commands registered

The following modules are imported in `[src/cai/repl/commands/__init__.py](../../src/cai/repl/commands/__init__.py)` in a typical OSS snapshot: `agent`, `compact`, `cost`, `env`, `exit`, `flush`, `graph`, `help`, `history`, `load`, `mcp`, `memory`, `merge`, `model`, `parallel`, `quickstart`, `shell`, `virtualization`, `workspace`. Your checkout may load extra modules; use `/help` locally for the authoritative list.

Commands such as `/resume`, `/queue`, `/continue`, `/settings`, `/api`, `/auth`, `/replay`, `/sessions`, `/ctr`, and `/metadebug` are listed above for completeness but may ship only in builds that add their modules to the REPL registry.

---

## Next steps

- [CLI getting started](getting_started.md)
- [CLI advanced usage](advanced_usage.md)
- [CLI overview](cli_index.md)
- [CAI API Backend](../api.md) — HTTP API when using `cai --api`

---

