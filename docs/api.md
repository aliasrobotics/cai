# CAI API Backend

The `cai --api` mode exposes a stateful HTTP backend built with FastAPI. It uses per-session agents to keep conversation state and REST routes to run REPL commands or send prompts to the model.

## Start the server

```bash
cai --api --api-host 0.0.0.0 --api-port 8080
# If 8080 (or your chosen port) is busy, the server auto-picks
# the next free port and prints it in the console.
```

CLI flags and environment variables (API subset):

| Flag | Env | Description |
| --- | --- | --- |
| `--api` | `CAI_API_MODE` | Enable the HTTP backend. |
| `--api-host` | `CAI_API_HOST` | Bind host/interface (default 127.0.0.1). |
| `--api-port` | `CAI_API_PORT` | Bind port (default 8000). |
| `--api-reload` | `CAI_API_RELOAD` | Dev autoreload. |
| `--api-workers` | `CAI_API_WORKERS` | Worker processes (ignored with reload). |

For **all** `cai` binary flags (`--tui`, `--resume`, `--yaml`, `--version`, …), see the single source of truth: [CLI commands reference — Binary `cai` CLI flags](cli/commands_reference.md#binary-cai-cli-flags).

Interactive docs at `/api/docs` and OpenAPI spec at `/api/openapi.json`.

### Authentication

- The API uses the client’s `ALIAS_API_KEY` as the secret. Set `ALIAS_API_KEY` and send it in header `X-CAI-API-Key` (customizable via `CAI_API_KEY_HEADER`).
- If `ALIAS_API_KEY` is not set, the API is unprotected (local dev only). For compatibility, `CAI_API_KEY` is accepted as a fallback.

Verbose/auth logging
- Server logs level: set `CAI_API_LOG_LEVEL` to `debug` (or `trace`) before `cai --api`.
- Request logging (method/path/headers/body preview): `CAI_API_LOG_REQUESTS=true`.
- Authentication decisions (why 401): `CAI_API_LOG_AUTH=true`.
- Dev autoreload: `CAI_API_RELOAD=true`.

Example:
```bash
ALIAS_API_KEY="your_key" \
CAI_API_LOG_LEVEL=debug \
CAI_API_LOG_REQUESTS=true \
CAI_API_LOG_AUTH=true \
CAI_API_RELOAD=true \
cai --api --api-host 0.0.0.0 --api-port 8080
```

### Content types

- JSON for request/response payloads.
- Server-Sent Events (SSE) for streaming endpoint (`text/event-stream`).

## Endpoints

Below are the endpoints with request/response examples and headers. For authenticated calls, include:

- `X-CAI-API-Key: $ALIAS_API_KEY`

Quick index
- GET /api/v1/health
- GET /api/v1/commands
- POST /api/v1/commands/{command}
- POST /api/v1/sessions
- GET /api/v1/sessions
- GET /api/v1/sessions/{id}
- DELETE /api/v1/sessions/{id}
- POST /api/v1/sessions/{id}/reset
- POST /api/v1/sessions/{id}/messages
- POST /api/v1/sessions/{id}/messages/stream
- GET /api/v1/sessions/{id}/history
- POST /api/v1/sessions/{id}/interrupt
- POST /api/v1/sessions/{id}/reload
- GET /api/v1/agents
- GET /api/v1/models
- POST /api/v1/sessions/{id}/ux/final_message/stream_tokens
- POST /api/v1/ux/title
- POST /api/v1/ux/summarize

### GET /api/v1/health
- Description: Liveness check. No auth required.
- Response 200:

```json
{"status":"ok","version":"<semver or dev>"}
```

### GET /api/v1/commands
- Description: List all REPL commands (names, aliases, subcommands).
- Headers: `X-CAI-API-Key`
- Response 200:

```json
{
  "commands": [
    {"name":"/memory","description":"memory ops","aliases":[],"subcommands":["show"]},
    {"name":"/help","description":"display help","aliases":["/h"],"subcommands":[]}
  ]
}
```

### POST /api/v1/commands/{command}
- Description: Execute a REPL command.
- Headers: `X-CAI-API-Key`, `Content-Type: application/json`
- Body:

```json
{"args": ["show"], "auto_correct": true}
```

- Response 200:

```json
{"handled": true, "suggested_command": null, "stdout": "...", "stderr": "", "exit_code": null}
```

### POST /api/v1/sessions
- Description: Create a new stateful session with its own agent instance and memory.
- Headers: `X-CAI-API-Key`, `Content-Type: application/json`
- Body:

```json
{"agent": "redteam_agent", "model": "alias1", "stateful": true, "metadata": {}}
```

- Response 201 (SessionDetailModel): includes summary + empty history initially.

### GET /api/v1/sessions
- Description: List active sessions (summaries).
- Headers: `X-CAI-API-Key`
- Response 200:

```json
{"sessions": [{"id":"<uuid>","agent":"redteam_agent","model":"alias1","stateful":true,"history_length":0, "created_at":"...","updated_at":"...","metadata":{}}]}
```

### GET /api/v1/sessions/{id}
- Description: Get session detail (summary + full history).
- Headers: `X-CAI-API-Key`

### DELETE /api/v1/sessions/{id}
- Description: Delete a session.
- Headers: `X-CAI-API-Key`
- Response: 204 No Content

### POST /api/v1/sessions/{id}/reset
- Description: Reset the session agent and clear history.
- Headers: `X-CAI-API-Key`
- Response 200: SessionDetailModel

### POST /api/v1/sessions/{id}/messages
- Description: Non-streamed inference. Runs the agent and returns the final result.
- Headers: `X-CAI-API-Key`, `Content-Type: application/json`
- Body (InferenceRequest):

```json
{"input": "List current risks", "context": {"org": "acme"}, "max_turns": 8}
```

- Response 200 (InferenceResponse):

```json
{
  "session": {"id": "<uuid>", ...},
  "result": {
    "messages": [/* semantic items: messages, tool calls, outputs, ... */],
    "history": [/* updated message list */],
    "final_output": {/* typed final output if agent uses an output schema, else string */},
    "text_output": "<assistant final text, if any>",
    "input_guardrails": [],
    "output_guardrails": []
  }
}
```

### POST /api/v1/sessions/{id}/messages/stream (SSE)
- Description: Stream high-level reasoning steps live (no token streaming) and a final summary. Under the hood the API performs non-streaming model calls and streams steps via server-side hooks (tools, handoffs, messages).
- Headers: `X-CAI-API-Key`, `Content-Type: application/json`, `Accept: text/event-stream`
- Body (InferenceRequest): same as non-streamed.
- Stream format: Server-Sent Events with two event types:
  - `event: reasoning_step` — One event per step with JSON `data` (examples below).
  - `event: final` — Final event with `{ steps, final_message, final_output }`.

Reasoning step payloads (no token deltas):

```json
// Message generated by the assistant
{"type":"message","agent":"Red Team","text":"...full assistant message..."}

// Tool call
{"type":"tool_call","agent":"Red Team","tool":"nmap_scan","arguments":{"target":"10.0.0.5"}}

// Tool output
{"type":"tool_output","agent":"Red Team","output":"open ports: 22,80"}

// Agent switch (handoff)
{"type":"handoff","from_agent":"Coordinator","to_agent":"Exploiter"}

// Explicit agent switch signal
{"type":"agent_switched","agent":"Exploiter"}
```

Final event payload:

```json
{
  "steps": [ /* the same reasoning steps emitted during the stream */ ],
  "final_message": "...last assistant message (if any)...",
  "final_output": {/* structured output if present, else string/null */}
}
```

Example with curl (SSE):

```bash
curl -N \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -H "X-CAI-API-Key: $ALIAS_API_KEY" \
  -d '{"input": "List current risks"}' \
  http://localhost:8080/api/v1/sessions/<SESSION_ID>/messages/stream
```

### POST /api/v1/sessions/{id}/messages/stream_tokens (SSE)
- Description: Token-level streaming (plus reasoning steps). This endpoint enables provider streaming internally and emits token deltas as they arrive. Use this only if you need character/token granularity.
- Headers: `X-CAI-API-Key`, `Content-Type: application/json`, `Accept: text/event-stream`
- Body (InferenceRequest): same as non-streamed.
- Stream events:
  - `event: token` with data `{ "type": "token_delta", "text": "..." }` for each emitted text delta.
  - `event: token` with data `{ "type": "message_start" }` and `{ "type": "message_end" }` to mark boundaries.
  - `event: reasoning_step` for high-level steps (same schema as /messages/stream).
  - `event: final` with the same summary payload as /messages/stream.

Notes
- Token streaming can be quite chatty; ensure your client handles backpressure and uses streaming-friendly APIs.
- For iOS, prefer URLSession streaming (see sample below); Safari’s EventSource cannot set custom headers.

curl example (tokens):
```bash
curl -N \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -H "X-CAI-API-Key: $ALIAS_API_KEY" \
  -d '{"input": "Write a haiku about ports"}' \
  http://localhost:8080/api/v1/sessions/<SESSION_ID>/messages/stream_tokens
```

iOS (Swift) streaming example (tokens)
```swift
let sid = "<SESSION_ID>"
var req = URLRequest(url: URL(string: "http://127.0.0.1:8080/api/v1/sessions/\(sid)/messages/stream_tokens")!)
req.httpMethod = "POST"
req.addValue("text/event-stream", forHTTPHeaderField: "Accept")
req.addValue("application/json", forHTTPHeaderField: "Content-Type")
req.addValue(ProcessInfo.processInfo.environment["ALIAS_API_KEY"] ?? "", forHTTPHeaderField: "X-CAI-API-Key")
req.httpBody = try! JSONSerialization.data(withJSONObject: ["input": "Hi"], options: [])

let task = URLSession.shared.streamTask(with: req)
task.resume()
task.readData(ofMinLength: 1, maxLength: 8192, timeout: 0) { data, atEOF, error in
    if let data = data, let s = String(data: data, encoding: .utf8) {
        // parse SSE lines: event: <name> / data: <json>
        print(s)
    }
}
```

Implementation notes (for curious devs)
- API streaming never enables OpenAI chat completions token streaming. Instead:
  - We run the agent with non-streaming model calls and emit events via RunHooks (tools start/end, handoffs, agent switches).
  - We add one message step after each assistant turn (full text, no token deltas).
  - This guarantees that model streaming is always off while still providing live step updates.

## Schemas (request/response fields)

- HealthResponse
  - status: string
  - version: string

- CommandMetadata
  - name: string (e.g., "/memory")
  - description: string
  - aliases: string[] (e.g., ["/h"]) 
  - subcommands: string[] (e.g., ["show"]) 

- CommandsResponse
  - commands: CommandMetadata[]

- CommandRequest
  - args: string[] (optional)
  - auto_correct: boolean (default true)

- CommandResponse
  - handled: boolean
  - suggested_command: string | null
  - stdout: string
  - stderr: string
  - exit_code: number | null

- CreateSessionRequest
  - agent: string (optional; default from CAI_AGENT_TYPE)
  - model: string (optional; default from CAI_MODEL)
  - stateful: boolean (default true)
  - metadata: object (optional)

- SessionSummary
  - id: string (UUID)
  - agent: string
  - model: string
  - stateful: boolean
  - created_at: ISO8601 string
  - updated_at: ISO8601 string
  - history_length: number
  - metadata: object

- SessionDetail
  - All SessionSummary fields, plus:
  - history: ResponseInputItem[] (OpenAI Responses input items list – user/system/assistant/tool items)

- SessionsResponse
  - sessions: SessionSummary[]

- InferenceRequest
  - input: string | ResponseInputItem[]
  - context: object (optional)
  - max_turns: number (optional)

- RunResultPayload
  - messages: Item[] (list of semantic items generated during the run; see below)
  - history: ResponseInputItem[] (original input plus generated items, suitable to continue)
  - final_output: any (typed result if the agent defines an output schema; otherwise text or null)
  - text_output: string | null (last assistant text message, if any)
  - input_guardrails: object[] (guardrail outputs for input)
  - output_guardrails: object[] (guardrail outputs for final output)

### Item: messages[] entry (non-streamed endpoint)
- Common envelope:
  - type: string (e.g., "message_output_item", "tool_call_item", "tool_call_output_item", "handoff_output_item")
  - agent: string | null (agent name that produced it)
  - payload: object (raw Pydantic model dump for the underlying output/input item)
  - output: any (only present for tool_call_output_item; the structured tool return value)

- message_output_item
  - payload: ResponseOutputMessage (OpenAI Responses message with content array)
  - text extraction: text_output consolidates last text chunk

- tool_call_item
  - payload: ResponseFunctionToolCall | ResponseComputerToolCall | ResponseFileSearchToolCall
  - typical fields (function call): name, arguments

- tool_call_output_item
  - output: any (decoded tool result)

- handoff_output_item
  - payload: handoff input item
  - Includes implicit source/target agent names in the envelope (agent + payload content)

### Streaming events (reasoning_step)
- Emitted from /messages/stream; one SSE per step.
- step.type values and fields:
  - message
    - agent: string | null
    - text: string (full assistant message; no token deltas)
  - tool_call
    - agent: string | null
    - tool: string (tool/function name)
    - arguments: object | string (as available)
  - tool_output
    - agent: string | null
    - output: any (structured tool output)
  - handoff
    - from_agent: string | null
    - to_agent: string | null
  - agent_switched
    - agent: string | null (new active agent)

Final event (event: final)
- steps: the array of emitted reasoning_step payloads
- final_message: string | null
- final_output: any

## Errors and status codes
- 401 Unauthorized — missing/invalid `X-CAI-API-Key` when auth is enabled
  - {"detail":"Invalid or missing API key"}
- 404 Not Found — e.g., unknown session id
  - {"detail":"Session not found"}
- 422 Unprocessable Entity — malformed request body
  - Standard FastAPI validation error
- 500 Internal Server Error — unexpected agent execution failure
  - {"detail":"Agent execution failed: ..."}

## Building a client (quick recipes)

Python (requests; SSE via iter_lines)
```python
import json
import os
import requests

BASE = "http://127.0.0.1:8080/api/v1"
HEADERS = {"X-CAI-API-Key": os.environ.get("ALIAS_API_KEY", ""), "Content-Type": "application/json"}

# 1) Create session
sess = requests.post(f"{BASE}/sessions", headers=HEADERS, json={"agent":"redteam_agent","model":"alias1","stateful":True}).json()
sid = sess["id"]

# 2) Non-streamed
res = requests.post(f"{BASE}/sessions/{sid}/messages", headers=HEADERS, json={"input":"List current risks"}).json()
print(res["result"]["text_output"])  # final message

# 3) Streaming (SSE)
stream_headers = HEADERS | {"Accept": "text/event-stream"}
with requests.post(f"{BASE}/sessions/{sid}/messages/stream", headers=stream_headers, json={"input":"List current risks"}, stream=True) as r:
    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("event:"):
            evt = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data = json.loads(line.split(":", 1)[1].strip())
            if evt == "reasoning_step":
                print("step:", data)
            elif evt == "final":
                print("final:", data)
```

Node (browser/EventSource)
```js
const key = process.env.ALIAS_API_KEY;
const sid = "<SESSION_ID>"; // create via POST /sessions
const es = new EventSource(`http://localhost:8080/api/v1/sessions/${sid}/messages/stream`, {
  withCredentials: false
});
// Note: To send headers with SSE in the browser, proxy or use fetch+ReadableStream.
es.addEventListener('reasoning_step', ev => console.log('step', JSON.parse(ev.data)));
es.addEventListener('final', ev => console.log('final', JSON.parse(ev.data)));
```

Node (fetch + ReadableStream; set auth header)
```js
import fetch from 'node-fetch';
const key = process.env.ALIAS_API_KEY;
const sid = process.env.SID;
const resp = await fetch(`http://localhost:8080/api/v1/sessions/${sid}/messages/stream`, {
  method: 'POST',
  headers: { 'Content-Type':'application/json', 'Accept':'text/event-stream', 'X-CAI-API-Key': key },
  body: JSON.stringify({ input: 'List current risks' })
});
for await (const chunk of resp.body) {
  const s = chunk.toString();
  // parse SSE lines: event: <name> / data: <json>
  process.stdout.write(s);
}
```

Best practices
- Always include `Accept: text/event-stream` for streaming.
- Expect multiple `reasoning_step` events, then exactly one `final` event.
- No token deltas are emitted; each message step contains the full assistant message text.
- Tool calls can be frequent; handle backpressure in your client.
- Keep your connection timeouts relaxed for long runs.

## Request examples (quick copy/paste)

```bash
# Healthcheck
curl -s http://localhost:8080/api/v1/health

# List agents
curl -s -H "X-CAI-API-Key: $ALIAS_API_KEY" http://localhost:8080/api/v1/agents | jq .

# List models
curl -s -H "X-CAI-API-Key: $ALIAS_API_KEY" http://localhost:8080/api/v1/models | jq .

# List commands
curl -s -H "X-CAI-API-Key: $ALIAS_API_KEY" http://localhost:8080/api/v1/commands

# Run a command
curl -s -X POST http://localhost:8080/api/v1/commands/memory \
  -H 'Content-Type: application/json' \
  -H "X-CAI-API-Key: $ALIAS_API_KEY" \
  -d '{"args": ["show"]}'

# Create a session
curl -s -X POST http://localhost:8080/api/v1/sessions \
  -H 'Content-Type: application/json' \
  -H "X-CAI-API-Key: $ALIAS_API_KEY" \
  -d '{"agent": "redteam_agent", "model": "alias1", "stateful": true}'

# Interrupt and reload
curl -s -X POST -H "X-CAI-API-Key: $ALIAS_API_KEY" \
  http://localhost:8080/api/v1/sessions/<SESSION_ID>/interrupt
curl -s -X POST -H "Content-Type: application/json" -H "X-CAI-API-Key: $ALIAS_API_KEY" \
  -d '{"preserve_history": true}' \
  http://localhost:8080/api/v1/sessions/<SESSION_ID>/reload

# Send a non-streamed prompt
curl -s -X POST http://localhost:8080/api/v1/sessions/<SESSION_ID>/messages \
  -H 'Content-Type: application/json' \
  -H "X-CAI-API-Key: $ALIAS_API_KEY" \
  -d '{"input": "List current risks"}'

# Stream reasoning steps (SSE)
curl -N -X POST http://localhost:8080/api/v1/sessions/<SESSION_ID>/messages/stream \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -H "X-CAI-API-Key: $ALIAS_API_KEY" \
  -d '{"input": "List current risks"}'

# Reset and delete session
curl -s -X POST -H "X-CAI-API-Key: $ALIAS_API_KEY" http://localhost:8080/api/v1/sessions/<SESSION_ID>/reset
curl -s -X DELETE -H "X-CAI-API-Key: $ALIAS_API_KEY" http://localhost:8080/api/v1/sessions/<SESSION_ID>
```

## Example CLIs

- `examples/cai_api_cli.py` — minimal loop: prompts → responses.
- `examples/cai_api_tester.py` — interactive menu that covers all endpoints including streaming.
### GET /api/v1/agents
- Description: List available agents and patterns in the runtime (from `cai.agents`).
- Headers: `X-CAI-API-Key`
- Response 200 (AgentsResponse):

```json
{
  "agents": [
    {
      "name": "redteam_agent",
      "description": "...",
      "type": "agent",
      "pattern_type": null,
      "tools": [
        {"name": "nmap_scan", "description": "Scan a host or subnet"},
        {"name": "http_get", "description": "Fetch a URL"}
      ]
    },
    {
      "name": "swarm_pattern",
      "description": "Swarm agentic pattern",
      "type": "pattern",
      "pattern_type": "swarm",
      "tools": []
    }
  ]
}
```

### GET /api/v1/models
- Description: List known models by combining predefined model catalog and `pricings/pricing.json` if present.
- Headers: `X-CAI-API-Key`
- Response 200 (ModelsResponse):

```json
{
  "models": [
    {
      "name": "alias1",
      "provider": "OpenAI",
      "category": "Alias",
      "description": "Best model for Cybersecurity AI tasks",
      "input_cost": 0.50,
      "output_cost": 0.50,
      "pricing": {
        "input_cost_per_token": 0.000005,
        "output_cost_per_token": 0.000005,
        "max_tokens": 128000,
        "max_input_tokens": 200000,
        "max_output_tokens": 128000,
        "supports_function_calling": true,
        "supports_vision": true,
        "supports_response_schema": true,
        "supports_tool_choice": true
      }
    }
  ]
}
```
### POST /api/v1/sessions/{id}/interrupt
- Description: Interrupt the currently running work (if any) for the given session. Cancels the active server-side run task.
- Headers: `X-CAI-API-Key`
- Response 200:

```json
{"interrupted": true}
```

### POST /api/v1/sessions/{id}/reload
- Description: Recreate the session’s agent. Optionally preserve message history.
- Headers: `X-CAI-API-Key`, `Content-Type: application/json`
- Body:

```json
{"preserve_history": true}
```

- Response 200: SessionDetailModel

<!-- Removed: /api/v1/sessions/{id}/ux/summarize and /api/v1/sessions/{id}/ux/title endpoints -->

### POST /api/v1/sessions/{id}/ux/final_message/stream_tokens (SSE)
- Description: Stream a final assistant message (token-level) that explains to the user what just happened. Your app calls this after a task completes, sending a prompt (tone/instructions) and optionally the steps you observed client-side; if you omit steps, the backend uses server-side steps.
- Headers: `X-CAI-API-Key`, `Content-Type: application/json`, `Accept: text/event-stream`
- Body (FinalMessageRequest):

```json
{
  "prompt": "Explain to the user what we found and next steps.",
  "steps": [ /* optional: client-collected steps; otherwise server uses session.last_steps */ ],
  "include_history": true,
  "max_turns": 8
}
```

- Stream events:
  - `event: token` with `{ "type": "message_start" }`
  - `event: token` with `{ "type": "token_delta", "text": "..." }` repeated
  - `event: token` with `{ "type": "message_end" }`
  - `event: reasoning_step` may appear if the UX agent emits steps
  - `event: final` with `{ "steps": [...], "final_message": "...", "final_output": ... }`

Notes for iOS

### POST /api/v1/ux/title
- Description: Genera un título conciso mediante una única tool call en el modelo `alias1` vía LiteLLM. No usa sesiones.
- Headers: `X-CAI-API-Key`, `Content-Type: application/json`
- Body:

```json
{
  "messages": [
    {"role": "user", "content": "Analiza CVE-2024-..."}
  ],
  "title_hint": "(opcional)"
}
```

- Response 200:

```json
{"title": "Analizando CVE-2024-..."}
```

### POST /api/v1/ux/summarize
- Description: Devuelve un resumen en una línea usando una única tool call en `alias1` vía LiteLLM. No usa sesiones.
- Headers: `X-CAI-API-Key`, `Content-Type: application/json`
- Body:

```json
{
  "messages": [
    {"role": "user", "content": "Escanea 10.0.0.5"}
  ],
  "steps": [
    {"type": "tool_call", "agent": "Red Team", "tool": "nmap_scan", "arguments": {"target": "10.0.0.5"}},
    {"type": "tool_output", "agent": "Red Team"}
  ],
  "max_len": 100
}
```

- Response 200:

```json
{"summary_text": "Tool output procesado por Red Team"}
```

Implementation notes
- Ambos endpoints fuerzan `tool_choice: required` con una única función `produce_title_and_summary` y usan siempre `model: alias1` con `api_base` Alias y `ALIAS_API_KEY`.
- El servidor no almacena ni lee estado de sesión.
- Call this to stream the “final message” of a task. Use a UX prompt tuned to your voice (“Explain briefly in a friendly tone, with next steps”).
- If you already collected steps client-side, pass them; otherwise the backend uses `session.last_steps`.
- Render arriving `token_delta` chunks into the chat bubble; close on `message_end`/`final`.
