CAI focuses on making cybersecurity agent **coordination** and **execution** lightweight, highly controllable, and useful for humans. To do so it builds upon 8 pillars: `Agent`s, `Tools`, `Handoffs`, `Patterns`, `Turns`, `Tracing`, `Guardrails` and `HITL`.


```
                  ┌───────────────┐           ┌───────────┐
                  │      HITL     │◀─────────▶│   Turns   │
                  └───────┬───────┘           └───────────┘
                          │
                          ▼
┌───────────┐       ┌───────────┐       ┌───────────┐      ┌───────────┐
│  Patterns │◀─────▶│  Handoffs │◀────▶ │   Agents  │◀────▶│    LLMs   │
└───────────┘       └─────┬─────┘       └─────┬─────┘      └───────────┘
                          │                   │
                          │                   ▼
┌────────────┐       ┌────┴──────┐       ┌───────────┐     ┌────────────┐
│ Extensions │◀─────▶│  Tracing  │       │   Tools   │◀───▶│ Guardrails │
└────────────┘       └───────────┘       └───────────┘     └────────────┘
                                              │
                          ┌─────────────┬─────┴────┬─────────────┐
                          ▼             ▼          ▼             ▼
                    ┌───────────┐┌───────────┐┌────────────┐┌───────────┐
                    │ LinuxCmd  ││ WebSearch ││    Code    ││ SSHTunnel │
                    └───────────┘└───────────┘└────────────┘└───────────┘
```


---

## 📚 Research Foundation

The CAI architecture is built on rigorous research establishing best practices for cybersecurity AI systems:

!!! tip "Key Research Papers"
    - 🚀 [**CAI Framework**](https://arxiv.org/pdf/2504.06017) (2025) - Core architecture demonstrating 3,600× speedup over manual testing
    - 🤖 [**Automation vs Autonomy**](https://www.arxiv.org/pdf/2506.23592) (2025) - 6-level taxonomy defining cybersecurity AI capabilities
    - 🎯 [**Agentic Cybersecurity Evaluation**](https://arxiv.org/pdf/2510.17521) (2025) - Real-world validation of agent coordination patterns
    - 🛡️ [**Prompt Injection Defense**](https://arxiv.org/pdf/2508.21669) (2025) - Four-layer guardrail system architecture
    - 📊 [**CAIBench**](https://arxiv.org/pdf/2510.24317) (2025) - Meta-benchmark framework for evaluating agent performance

**📖 Explore all research:** [Alias Robotics Research Library →](https://aliasrobotics.com/research-security.php#papers)

The architecture emphasizes **transparency**, **modularity**, and **human oversight** to ensure responsible and effective cybersecurity automation. Our [research demonstrates](https://arxiv.org/pdf/2506.23592) that semi-autonomous systems with human-in-the-loop capabilities significantly outperform fully autonomous approaches for complex security tasks.

---

If you want to dive deeper into the code, check the following files as a start point for using CAI:

```
cai
├── benchmarks
├── ci
├── docs
├── examples                     # Basic use of CAI for start building on your own
├── src
│   └── cai
│        ├── __init__.py
│        ├── agents
│        │   ├── one_tool.py     # Agent definitions, one agent per file
│        │   └── patterns
│        ├── cli.py              # Entrypoint for CLI
│        ├── prompts
│        ├── repl                # CLI aesthetics and commands
│        │   ├── commands
│        │   └── ui
│        ├── sdk                 # Necessary class for chat completions
│        │   └── agents
│        │       └── model
│        ├── tools               # Agent tools
│        │   └──common.py
│        └── util.py             # Utility functions
├── tests
└── tools                        # Usable tools
```

---

### 🔹 Agent

At its core, CAI abstracts its cybersecurity behavior via `Agents` and agentic `Patterns`. An Agent in *an intelligent system that interacts with some environment*. More technically, within CAI we embrace a robotics-centric definition wherein an agent is anything that can be viewed as a system perceiving its environment through sensors, reasoning about its goals and and acting accordingly upon that environment through actuators (*adapted* from Russel & Norvig, AI: A Modern Approach). In cybersecurity, an `Agent` interacts with systems and networks, using peripherals and network interfaces as sensors, reasons accordingly and then executes network actions as if actuators. Correspondingly, in CAI, `Agent`s implement the `ReACT` (Reasoning and Action) agent model[3].

For more details, including examples and implementation guidance, see the [Agents documentation](agents.md).


### 🔹 Tools

`Tools` let cybersecurity agents take actions by providing interfaces to execute system commands, run security scans, analyze vulnerabilities, and interact with target systems and APIs - they are the core capabilities that enable CAI agents to perform security tasks effectively; in CAI, tools include built-in cybersecurity utilities (like LinuxCmd for command execution, WebSearch for OSINT gathering, Code for dynamic script execution, and SSHTunnel for secure remote access), function calling mechanisms that allow integration of any Python function as a security tool, and agent-as-tool functionality that enables specialized security agents (such as reconnaissance or exploit agents) to be used by other agents, creating powerful collaborative security workflows without requiring formal handoffs between agents.

You may find different [tools](src/cai/tools). They are grouped in 6 major categories inspired by the security kill chain[2]:

1. Reconnaissance and weaponization - *reconnaissance*  (crypto, listing, etc)
2. Exploitation - *exploitation*
3. Privilege escalation - *escalation*
4. Lateral movement - *lateral*
5. Data exfiltration - *exfiltration*
6. Command and control - *control*

For more information, examples, and implementation details, please refer to the [Tools documentation](tools.md).


### 🔹 Patterns

An agentic `Pattern` is a *structured design paradigm* in artificial intelligence systems where autonomous or semi-autonomous agents operate within a defined *interaction framework* (the pattern) to achieve a goal. These `Patterns` specify the organization, coordination, and communication
methods among agents, guiding decision-making, task execution, and delegation.

An agentic pattern (`AP`) can be formally defined as a tuple:

\\[
AP = (A, H, D, C, E)
\\]

wherein:

- **\\(A\\) (Agents):** A set of autonomous entities, \\( A = \\{a_1, a_2, ..., a_n\\} \\), each with defined roles, capabilities, and internal states.
- **\\(H\\) (Handoffs):** A function \\( H: A \times T \to A \\) that governs how tasks \\( T \\) are transferred between agents based on predefined logic (e.g., rules, negotiation, bidding).
- **\\(D\\) (Decision Mechanism):** A decision function \\( D: S \to A \\) where \\( S \\) represents system states, and \\( D \\) determines which agent takes action at any given time.
- **\\(C\\) (Communication Protocol):** A messaging function \\( C: A \times A \to M \\), where \\( M \\) is a message space, defining how agents share information.
- **\\(E\\) (Execution Model):** A function \\( E: A \times I \to O \\) where \\( I \\) is the input space and \\( O \\) is the output space, defining how agents perform tasks.

When building `Patterns`, we generall y classify them among one of the following categories, though others exist:

| **Agentic** `Pattern` **categories** | **Description** |
|--------------------|------------------------|
| `Swarm` (Decentralized) | Agents share tasks and self-assign responsibilities without a central orchestrator. Handoffs occur dynamically. *An example of a peer-to-peer agentic pattern is the `CTF Agentic Pattern`, which involves a team of agents working together to solve a CTF challenge with dynamic handoffs.* |
| `Hierarchical` | A top-level agent (e.g., "PlannerAgent") assigns tasks via structured handoffs to specialized sub-agents. Alternatively, the structure of the agents is harcoded into the agentic pattern with pre-defined handoffs. |
| `Chain-of-Thought` (Sequential Workflow) | A structured pipeline where Agent A produces an output, hands it to Agent B for reuse or refinement, and so on. Handoffs follow a linear sequence. *An example of a chain-of-thought agentic pattern is the `ReasonerAgent`, which involves a Reasoning-type LLM that provides context to the main agent to solve a CTF challenge with a linear sequence.*[1] |
| `Auction-Based` (Competitive Allocation) | Agents "bid" on tasks based on priority, capability, or cost. A decision agent evaluates bids and hands off tasks to the best-fit agent. |
| `Recursive` | A single agent continuously refines its own output, treating itself as both executor and evaluator, with handoffs (internal or external) to itself. *An example of a recursive agentic pattern is the `CodeAgent` (when used as a recursive agent), which continuously refines its own output by executing code and updating its own instructions.* |
| `Parallelization` | Multiple agents run in parallel, each handling different subtasks or independent inputs simultaneously. This approach speeds up processing when tasks do not depend on each other. *For example, you can launch several agents to analyze different log files or scan multiple IP addresses at the same time, leveraging concurrency to improve efficiency.* |
 
Moreover in this new version we could orchestrate agents and add decision mechanism in several ways. See [Orchestrating multiple agents](multi_agent.md)


### 🔹 Turns 
During the agentic flow (conversation), we distinguish between **interactions** and **turns**.

- **Interactions** are sequential exchanges between one or multiple agents. Each agent executing its logic corresponds with one *interaction*. Since an `Agent` in CAI generally implements the `ReACT` agent model[3], each *interaction* consists of 1) a reasoning step via an LLM inference and 2) act by calling zero-to-n `Tools`. 
- **Turns**: A turn represents a cycle of one ore more **interactions** which finishes when the `Agent` (or `Pattern`) executing returns `None`, judging there're no further actions to undertake.


> CAI Agents are not related to Assistants in the Assistants API. They are named similarly for convenience, but are otherwise completely unrelated. CAI is entirely powered by the Chat Completions API and is hence stateless between calls.


### 🔹 Tracing
> ⚠️ TRACING IS STILL IN PROGRESS


### 🔹 Guardrails

`Guardrails` provide a critical security layer for CAI agents, protecting against prompt injection attacks and preventing execution of dangerous commands. These guardrails run in parallel to agents, validating both input and output to ensure safe operation. The framework includes:

- **Input Guardrails**: Detect and block prompt injection attempts before they reach agents, using pattern matching, Unicode homograph detection, and AI-powered analysis
- **Output Guardrails**: Validate agent outputs before execution, preventing dangerous commands like reverse shells, fork bombs, or data exfiltration  
- **Multi-layered Defense**: Protection at input, processing, and execution stages with tool-level validation
- **Base64/Base32 Aware**: Automatically decodes and analyzes encoded payloads to detect hidden malicious commands
- **Configurable**: Can be enabled/disabled via `CAI_GUARDRAILS` environment variable

For detailed implementation and examples, see [Guardrails documentation](guardrails.md) and [Prompt Injection Mitigation](cai_prompt_injection.md).


### 🔹 Human-In-The-Loop (HITL)

```
                      ┌─────────────────────────────────┐
                      │                                 │
                      │      Cybersecurity AI (CAI)     │
                      │                                 │
                      │       ┌─────────────────┐       │
                      │       │  Autonomous AI  │       │
                      │       └────────┬────────┘       │
                      │                │                │
                      │                │                │
                      │       ┌────────▼─────────┐      │
                      │       │ HITL Interaction │      │
                      │       └────────┬─────────┘      │
                      │                │                │
                      └────────────────┼────────────────┘
                                       │
                                       │ Ctrl+C (cli.py)
                                       │
                           ┌───────────▼───────────┐
                           │   Human Operator(s)   │
                           │  Expertise | Judgment │
                           │    Teleoperation      │
                           └───────────────────────┘
```

CAI delivers a framework for building Cybersecurity AIs with a strong emphasis on *semi-autonomous* operation, as the reality is that **fully-autonomous** cybersecurity systems remain premature and face significant challenges when tackling complex tasks. While CAI explores autonomous capabilities, we recognize that effective security operations still require human teleoperation providing expertise, judgment, and oversight in the security process.

Accordingly, the Human-In-The-Loop (`HITL`) module is a core design principle of CAI, acknowledging that human intervention and teleoperation are essential components of responsible security testing. Through the `cli.py` interface, users can seamlessly interact with agents at any point during execution by simply pressing `Ctrl+C`. 


---

[1] Arguably, the Chain-of-Thought agentic pattern is a special case of the Hierarchical agentic pattern.
[2] Kamhoua, C. A., Leslie, N. O., & Weisman, M. J. (2018). Game theoretic modeling of advanced persistent threat in internet of things. Journal of Cyber Security and Information Systems.
[3] Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., & Cao, Y. (2023, January). React: Synergizing reasoning and acting in language models. In International Conference on Learning Representations (ICLR).
