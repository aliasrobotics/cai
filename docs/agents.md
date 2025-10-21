# Agents

Agents are the core of CAI. An agent uses Large Language Models (LLMs), configured with instructions and tools to perform specialized cybersecurity tasks. Each agent is defined in its own `.py` file in `src/cai/agents` and optimized for specific security domains.

## Available Agents

CAI provides a comprehensive suite of specialized agents for different cybersecurity scenarios:

| Agent | Description | Primary Use Case | Key Tools |
|-------|-------------|------------------|-----------|
| **redteam_agent** | Offensive security specialist for penetration testing | Active exploitation, vulnerability discovery | nmap, metasploit, burp |
| **blueteam_agent** | Defensive security expert for threat mitigation | Security hardening, incident response | wireshark, suricata, osquery |
| **bug_bounter_agent** | Bug bounty hunter optimized for vulnerability research | Web app security, API testing | ffuf, sqlmap, nuclei |
| **one_tool_agent** | Minimalist agent focused on single-tool execution | Quick scans, specific tool operations | Generic Linux commands |
| **dfir_agent** | Digital Forensics and Incident Response expert | Log analysis, forensic investigation | volatility, autopsy, log2timeline |
| **reverse_engineering_agent** | Binary analysis and reverse engineering | Malware analysis, firmware reversing | ghidra, radare2, ida |
| **memory_analysis_agent** | Memory dump analysis specialist | RAM forensics, process analysis | volatility, rekall |
| **network_traffic_analyzer** | Network packet analysis expert | PCAP analysis, traffic inspection | wireshark, tcpdump, tshark |
| **android_sast_agent** | Android Static Application Security Testing | APK analysis, Android vulnerability scanning | jadx, apktool, mobsf |
| **wifi_security_tester** | Wireless network security assessment | WiFi penetration testing, WPA cracking | aircrack-ng, reaver, wifite |
| **replay_attack_agent** | Replay attack execution specialist | Protocol replay, authentication bypass | custom scripts, burp |
| **subghz_sdr_agent** | Sub-GHz SDR signal analysis expert | RF analysis, IoT protocol testing | hackrf, gqrx, urh |

### Quick Start with Agents

```bash
# Launch CAI with a specific agent
CAI_AGENT_TYPE=redteam_agent cai

# Launch with custom model
CAI_AGENT_TYPE=bug_bounter_agent CAI_MODEL=alias0 cai

# Or switch agents during a session
CAI>/agent redteam_agent

# List all available agents with descriptions
CAI>/agent list

# Get detailed info about a specific agent
CAI>/agent info redteam_agent
```

### Choosing the Right Agent

- **For general pentesting**: Start with `redteam_agent`
- **For web applications**: Use `bug_bounter_agent`
- **For forensics**: Use `dfir_agent` or `memory_analysis_agent`
- **For IoT/embedded**: Try `subghz_sdr_agent` or `reverse_engineering_agent`
- **For network security**: Use `network_traffic_analyzer` or `blueteam_agent`
- **For mobile apps**: Use `android_sast_agent`
- **For wireless networks**: Use `wifi_security_tester`

---

## Agent Capabilities Matrix

| Capability | redteam | blueteam | bug_bounty | dfir | reverse_eng | network |
|-----------|---------|----------|------------|------|-------------|---------|
| **Web App Testing** | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ |
| **Network Analysis** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| **Binary Analysis** | ⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ |
| **Forensics** | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **IoT/Embedded** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **API Testing** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ |
| **Exploit Development** | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ |

**Legend**: ⭐ Limited | ⭐⭐⭐ Moderate | ⭐⭐⭐⭐⭐ Excellent

---

## Common Agent Workflows

### Scenario 1: Full Web Application Pentest

```bash
# 1. Start with reconnaissance
CAI>/agent bug_bounter_agent
CAI> Scan https://target.com for vulnerabilities

# 2. Switch to exploitation
CAI>/agent redteam_agent  
CAI> Exploit the SQL injection found at /login

# 3. Post-exploitation analysis
CAI>/agent dfir_agent
CAI> Analyze the logs to understand the attack surface
```

### Scenario 2: IoT Device Security Assessment

```bash
# 1. RF signal analysis
CAI>/agent subghz_sdr_agent
CAI> Analyze the 433MHz signals from the device

# 2. Firmware analysis
CAI>/agent reverse_engineering_agent
CAI> Extract and analyze the firmware from dump.bin

# 3. Memory analysis if device captured
CAI>/agent memory_analysis_agent
CAI> Analyze the memory dump for secrets
```

### Scenario 3: Network Incident Response

```bash
# 1. Network traffic analysis
CAI>/agent network_traffic_analyzer
CAI> Analyze capture.pcap for suspicious activity

# 2. Forensic investigation
CAI>/agent dfir_agent
CAI> Investigate the compromised host logs

# 3. Defensive recommendations
CAI>/agent blueteam_agent
CAI> Provide mitigation strategies based on findings
```

---

## Basic Configuration

Key agent properties include:

-   `name`: Name of the agent (e.g., the name of `one_tool_agent` is 'CTF Agent')
-   `instructions`: The system prompt that defines agent behavior
-   `model`: Which LLM to use, with optional `model_settings` to configure parameters like temperature, top_p, etc.
-   `tools`: Tools that the agent can use to achieve its tasks
-   `handoffs`: Allows an agent to delegate tasks to another agent

## Example: `one_tool_agent.py`

```python
from cai.sdk.agents import Agent, OpenAIChatCompletionsModel
from cai.tools.reconnaissance.generic_linux_command import generic_linux_command 
from openai import AsyncOpenAI

one_tool_agent = Agent(
    name="CTF agent",
    description="Agent focused on conquering security challenges using generic linux commands",
    instructions="You are a Cybersecurity expert Leader facing a CTF challenge.",
    tools=[
        generic_linux_command,
    ],
    model=OpenAIChatCompletionsModel(
        model="qwen2.5:14b",
        openai_client=AsyncOpenAI(),
    )
)
```


## Context

There are two main context types. See [context](context.md) for details.

Agents are generic on their `context` type. Context is a dependency-injection tool: it's an object you create and pass to `Runner.run()`, that is passed to every agent, tool, handoff etc, and it serves as a grab bag of dependencies and state for the agent run. You can provide any Python object as the context.

```python
@dataclass
class SecurityContext:
  target_system: str
  is_compromised: bool

  async def get_exploits() -> list[Exploits]:
     return ...

agent = Agent[SecurityContext](
    ...,
)
```

## Output types

By default, agents produce plain text (i.e. `str`) outputs. If you want the agent to produce a particular type of output, you can use the `output_type` parameter. A common choice is to use [Pydantic](https://docs.pydantic.dev/) objects, but we support any type that can be wrapped in a Pydantic [TypeAdapter](https://docs.pydantic.dev/latest/api/type_adapter/) - dataclasses, lists, TypedDict, etc.

```python
from pydantic import BaseModel
from cai.sdk.agents import Agent

class SecurityVulnerability(BaseModel):
    name: str
    severity: str
    affected_files: list[str]
    description: str

agent = Agent(
    name="Vulnerability scanner",
    instructions="Analyze system output and identify security vulnerabilities",
    output_type=SecurityVulnerability,
)
```

!!! note
   When you pass an `output_type`, that tells the model to use structured outputs instead of regular plain text responses.

## Handoffs

Handoffs are sub-agents that the agent can delegate to. You provide a list of handoffs, and the agent can choose to delegate to them if relevant. This is a powerful pattern that allows orchestrating modular, specialized agents that excel at a single task. Read more in the [handoffs](handoffs.md) documentation.

```python
from cai.sdk.agents import Agent

crypto_agent = Agent(
    name="Cryptography agent",
    description="Agent specialized in solving cryptographic challenges and decoding encrypted messages",
    instructions="Analyze encrypted data and apply cryptographic techniques to decode it.",
    tools=[
        execute_cli_command,
    ],
    handoff_description="Specialized agent in Cryptography and code breaking",
    model=OpenAIChatCompletionsModel(
        model=os.getenv('CAI_MODEL', "qwen2.5:14b"),
        openai_client=AsyncOpenAI(),
    )
)
network_agent = Agent(
    name="Network Agent",
    description="Agent specialized in network analysis, packet inspection, and network security assessments",
    instructions="Analyze network traffic, identify suspicious patterns, and help with network-related CTF challenges",
    handoff_description="Specialized agent in network security, traffic analysis, and protocol understanding",
    model=OpenAIChatCompletionsModel(
        model=os.getenv('CAI_MODEL', "qwen2.5:72b"),
        openai_client=AsyncOpenAI(),
    )
)
lead_agent = Agent(
    name="Cybersecurity Lead Agent",
    instructions=(
        "You are a lead cybersecurity expert coordinating security operations."
        "If the user needs network analysis or traffic inspection, handoff to the network agent."
        "If the user needs cryptographic solutions or code breaking, handoff to the crypto agent."
    ),
    handoffs=[network_agent, crypto_agent],
    model="qwen2.5:72b"
)
```

## Dynamic instructions

In most cases, you can provide instructions when you create the agent. However, you can also provide dynamic instructions via a function. The function will receive the agent and context, and must return the prompt. Both regular and `async` functions are accepted.

```python
def dynamic_instructions(
    context: RunContextWrapper[UserContext], agent: Agent[UserContext]
) -> str:
    security_level = "high" if context.context.is_admin else "standard"
    return f"You are assisting {context.context.name} with cybersecurity operations. Their security clearance level is {security_level}. Tailor your security recommendations appropriately and prioritize addressing their immediate security concerns."


agent = Agent[UserContext](
    name="Cybersecurity Triage Agent",
    instructions=dynamic_instructions,
)
```


### Launch

```bash
cai
```

### Performance Optimization

**1. Use streaming for better responsiveness:**
```bash
CAI_STREAM=true cai
```
**2. Enable tracing for debugging:**
```bash
CAI_TRACING=true cai
```

---

## Agent Best Practices

### 1. Start with the Right Agent

Don't use a specialized agent for general tasks. Match the agent to your objective:

```bash
# ✅ Good: Using bug bounty agent for web testing
CAI_AGENT_TYPE=bug_bounter_agent cai
CAI> Test https://target.com for vulnerabilities

# ❌ Bad: Using reverse engineering agent for web testing
CAI_AGENT_TYPE=reverse_engineering_agent cai
CAI> Test https://target.com for vulnerabilities
```

### 2. Switch Agents as Needed

Don't hesitate to switch agents mid-session:

```bash
CAI>/agent bug_bounter_agent
CAI> Find vulnerabilities in the web app
# ... agent finds SQL injection ...

CAI>/agent redteam_agent
CAI> Exploit the SQL injection to gain access
# ... successful exploitation ...

CAI>/agent dfir_agent
CAI> Analyze what data was exposed during the test
```

### 3. Monitor Resource Usage

Keep an eye on costs and performance:

```bash
# During session, check costs
CAI>/cost

# Set limits before starting
CAI_PRICE_LIMIT="5.00" CAI_MAX_TURNS=50 cai
```

### 4. Save Successful Sessions

Use `/load` to reuse successful approaches:

```bash

# In future session
CAI>/load logs/logname.jsonl
```

---


## Next Steps

- **Running Agents**: See [running_agents documentation](running_agents.md) for execution details
- **Understanding Results**: See [results documentation](results.md) for output interpretation
- **Agent Tools**: See [tools documentation](tools.md) for available tools
- **Handoffs**: See [handoffs documentation](handoffs.md) for agent coordination
- **MCP Integration**: See [mcp documentation](mcp.md) for connecting external tools
- **Multi-Agent Patterns**: See [multi_agent documentation](multi_agent.md) for orchestration patterns