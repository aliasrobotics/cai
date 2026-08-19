# GLM (Z.ai) Configuration

#### [GLM models by Z.ai](https://z.ai/model-api)

GLM is Z.ai's family of models (the GLM-4.x / GLM-5.x series). They are strong at
function/tool calling and offer large context windows, which makes them a
practical backend for CAI's agents. GLM is served over an OpenAI-compatible Chat
Completions API, so CAI can reach it through two paths. Pick one and add it to
your `.env`.

## Option A — OpenRouter (recommended)

CAI has native OpenRouter support, so this is the simplest route:

```bash
CAI_MODEL=openrouter/z-ai/glm-4.6      # see OpenRouter's Z.ai page for other slugs
OPENROUTER_API_KEY=sk-or-your-key      # from https://openrouter.ai/keys
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-123                  # keep non-empty even via OpenRouter (see Requirements)
```

Other current GLM slugs (e.g. `z-ai/glm-4.7`, `z-ai/glm-5.2`, and the zero-cost
`z-ai/glm-5.2:free`) are on OpenRouter's
[Z.ai models page](https://openrouter.ai/z-ai).

## Option B — Z.ai general (pay-per-token) API

Z.ai also exposes a general, pay-per-token API that speaks the OpenAI protocol.
Recent LiteLLM has a native `zai/` provider that targets it directly:

```bash
CAI_MODEL=zai/glm-4.6                   # zai/ routes to https://api.z.ai/api/paas/v4
ZAI_API_KEY=your_zai_api_key            # from https://z.ai/manage-apikey/apikey-list
```

If a model isn't mapped by LiteLLM yet (e.g. the newer GLM-5.x line), use the
generic OpenAI-compatible route instead:

```bash
CAI_MODEL=openai/glm-5.2
OPENAI_API_BASE=https://api.z.ai/api/paas/v4
OPENAI_API_KEY=your_zai_api_key
```

(For the Zhipu/BigModel platform in China, use
`https://open.bigmodel.cn/api/paas/v4` with a BigModel key.)

!!! note "Which endpoint to use"
    Use OpenRouter (Option A) or the general `https://api.z.ai/api/paas/v4` API
    (Option B). Z.ai's `https://api.z.ai/api/anthropic` and
    `https://api.z.ai/api/coding/paas/v4` endpoints belong to its Coding Plan,
    which is limited to a set of officially supported coding tools, so
    they aren't a supported path for CAI.

**Requirements:**
1. An API key from your chosen provider — [OpenRouter](https://openrouter.ai/keys) (Option A) or the [Z.ai console](https://z.ai/manage-apikey/apikey-list) (Option B).
2. Set `CAI_MODEL` with the matching prefix: `openrouter/` (Option A) or `zai/` / `openai/` (Option B).
3. Keep `OPENAI_API_KEY` non-empty — a placeholder like `sk-123` is enough. CAI reads it at launch even when another provider is active, and a blank value can stop it from starting.

**Notes / tips:**
- **Tool calling.** GLM models are strong at function/tool calling, which CAI's agents rely on; `glm-4.7` handles multi-step tool use especially well. `glm-5.2` offers a very large (~1M-token) context, useful for long recon transcripts.
- **Parallel tool calls.** Some GLM models can emit several `tool_calls` in a single turn. If a run stalls right after such a turn, that interaction is the likely cause — it's tracked in [issue #469](https://github.com/aliasrobotics/cai/issues/469). If you hit it, steer the agent toward one tool call at a time.
- **Long / autonomous runs.** Launch CAI inside `tmux` so a long headless session survives disconnects and you can re-attach.
- Model IDs and pricing change often — check [Z.ai models & pricing](https://docs.z.ai/guides/overview/pricing) or [OpenRouter](https://openrouter.ai/z-ai) for the current list.
