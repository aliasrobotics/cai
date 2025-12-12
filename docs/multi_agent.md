# Orchestrating multiple agents

Orchestration refers to the flow of agents in your app. Which agents run, in what order, and how do they decide what happens next? There are two main ways to orchestrate agents:

1. Allowing the LLM to make decisions: this uses the intelligence of an LLM to plan, reason, and decide on what steps to take based on that.
2. Orchestrating via code: determining the flow of agents via your code.

You can mix and match these patterns. Each has their own tradeoffs, described below.

We have a number of examples in examples/cai/agent_patterns.

#### ◉ Orchestrating via LLM

An agent is an LLM equipped with instructions, tools and handoffs. This means that given an open-ended task, the LLM can autonomously plan how it will tackle the task, using [tools](tools.md) to take actions and acquire data, and using [handoffs](handoffs.md) to delegate tasks to sub-agents. 

You could also use an agent as a tool. The agents operates independently on its provided input —without access to prior conversation history or "taking over" the conversation - completes its specific task, and returns the result to the calling (parent) agent.


#### ◉ Orchestrating via code

While orchestrating via LLM is powerful, orchestrating via code makes tasks more deterministic and predictable, in terms of speed, cost and performance. Common patterns here are:

- Using structured outputs to generate well formed data that you can inspect with your code. 

- Using a deterministic pattern: Breaking down a task into a series of smaller steps. Chaining multiple agents, each step can be performed by an agent, and the output of one agent is used as input to the next. 

- Using [Guardrails](guardrails.md) and LLM_as_judge: They are agents that evaluates and provides feedback, until they says the inputs/outputs passes certain criteria. The agent ensures inputs/outputs are appropriate.

- Parallelization of task: Running multiple agents in parallel. This is useful for speed when you have multiple tasks.

## Running Agents in Parallel

When you have multiple tasks, you can run agents in parallel to improve performance and reduce overall execution time. This is particularly useful in security workflows where you need to perform multiple reconnaissance or analysis tasks simultaneously.

You have two options:

1. **Use built-in parallel patterns** (available via `/agent list`)
2. **Create your own custom pattern** using `agents.yml` configuration

### Option 1: Using Built-in Parallel Patterns

CAI includes ready-to-use parallel patterns that you can select directly from the CLI.

**View available patterns:**

```bash
# Launch CAI and list all available patterns
cai
CAI> /agent list
```

**Available parallel patterns:**

| Pattern Name | Agents | Context | Description |
|--------------|--------|---------|-------------|
| **offsec_pattern** | redteam_agent + bug_bounter_agent | Split | Bug bounty and red team with different contexts for offensive security ops |
| **blue_team_red_team_shared_context** | redteam_agent + blueteam_agent | Shared | Red and blue team agents sharing the same message history |
| **blue_team_red_team_split_context** | redteam_agent + blueteam_agent | Split | Red and blue team agents with separate contexts for independent analysis |
| **purple_team_gctr** ⭐ | redteam_agent + blueteam_agent (enhanced with G-CTR) | Shared | Combines red and blue team agents with shared GCTR tracking for unified game-theoretic analysis (⭐ this is a [CAI PRO](https://aliasrobotics.com/cybersecurityai.php) capability)|

**To use a pattern:**

```bash
# Start CAI and select a pattern
cai

# List available patterns
CAI> /agent list

# Select a parallel pattern by number or name
CAI> /agent 23
# or
CAI> /agent offsec_pattern

# Now enter your prompt and both agents will work in parallel
CAI> Analyze https://example.com for vulnerabilities
```

**How parallel patterns work:**

- **Split context**: Each agent has its own message history and works independently
- **Shared context**: Both agents see the same message history and can build on each other's work

**Example workflow with offsec_pattern:**

```bash
CAI> /agent offsec_pattern
CAI> Find vulnerabilities in https://target.com

# Both redteam_agent and bug_bounter_agent will analyze the target
# Each provides their perspective (red team exploitation vs bug bounty)
# You get results from both agents in parallel
```

### Option 2: Create Your Own Pattern with agents.yml

For a simpler approach, use the `agents.yml` configuration file to run multiple agents in parallel without writing Python code.

**1. Copy the example configuration:**

```bash
cp agents.yml.example agents.yml
```

**2. Configure your parallel agents in `agents.yml`:**


**Example with unified context:**
```yaml
parallel_agents:
  # Define 2 or more agents to run in parallel
  - name: one_tool_agent
    model: alias1
    prompt: "Focus on finding vulnerabilities"
    unified_context: false  # Each agent has its own message history

  - name: blueteam_agent
    model: alias1
    prompt: "Focus on defensive security"
    unified_context: false
```

**Example with Shared context:**

```yaml
parallel_agents:

  - name: redteam_agent
    unified_context: true  # Agents share message history

  - name: blueteam_agent
    unified_context: true  # Can see what redteam agent did
```

**3. Launch CAI:**

```bash
# Auto-loads agents.yml from current directory
cai

# Or load a different configuration file
cai --yaml agent_custom.yml

# Or specify a full path
cai --yaml /path/to/my_agents.yml
```

**How it works:**

- When 2 or more agents are configured, parallel mode is automatically enabled
- The agents will be available for selection when you enter a prompt
- Each agent can have its own model, prompt, and context settings

**Configuration options:**

- `name`: The agent type (e.g., `redteam_agent`, `bug_bounter_agent`)
- `model`: Optional model override (e.g., `alias1`, `alias0`)
- `prompt`: Optional additional instructions for the agent
- `unified_context`: Set to `true` to share message history between agents (default: `false`)

