# Agents

Agents are the core of CAI. An agent uses Large Language Models (LLMs), configured with instructions and tools to perform specialized cybersecurity tasks. Each agent is defined in its own `.py` file in `src/cai/agents` and optimized for specific security domains.

## Available Agents

CAI provides a comprehensive suite of specialized agents for different cybersecurity scenarios:

| Agent | Description | Primary Use Case | Key Tools |
|-------|-------------|------------------|-----------|
| **redteam_agent** | Offensive security specialist for penetration testing | Active exploitation, vulnerability discovery | generic_linux_command, execute_code, web_search |
| **blueteam_agent** | Defensive security expert for threat mitigation | Security hardening, incident response | generic_linux_command, ssh_command, execute_code, web_search |
| **bug_bounter_agent** | Bug bounty hunter optimized for vulnerability research | Web app security, API testing | generic_linux_command, execute_code, shodan_search, google_search |
| **one_tool_agent** | Minimalist agent focused on single-tool execution | Quick scans, specific tool operations | generic_linux_command |
| **dfir_agent** | Digital Forensics and Incident Response expert | Log analysis, forensic investigation | generic_linux_command, ssh_command, execute_code, think, web_search, shodan_search |
| **reverse_engineering_agent** | Binary analysis and reverse engineering | Malware analysis, firmware reversing | generic_linux_command, ssh_command, execute_code, web_search |
| **memory_analysis_agent** | Memory dump analysis specialist | RAM forensics, process analysis | generic_linux_command, ssh_command, execute_code, web_search |
| **network_security_analyzer_agent** | Network packet analysis expert | PCAP analysis, traffic inspection | generic_linux_command, ssh_command, execute_code, capture_remote_traffic, web_search |
| **app_logic_mapper** | Android application logic mapper | APK analysis, app logic understanding | generic_linux_command, execute_code |
| **android_sast** | Android SAST specialist | Static application security testing for Android | app_mapper (handoff), generic_linux_command, execute_code |
| **wifi_security_agent** | Wireless network security assessment | WiFi penetration testing, WPA cracking | generic_linux_command, ssh_command, execute_code, web_search |
| **replay_attack_agent** | Replay attack execution specialist | Protocol replay, authentication bypass | generic_linux_command, ssh_command, execute_code, capture_remote_traffic, web_search |
| **subghz_sdr_agent** | Sub-GHz SDR signal analysis expert | RF analysis, IoT protocol testing | generic_linux_command, ssh_command, execute_code, web_search |
| **selection_agent** ⭐ | Agent selection and routing | Automatically selects the best agent for a task | check_available_agents, analyze_task_requirements, get_agent_number, web_search |
| **retester_agent** | Vulnerability retesting specialist | Re-validates previously discovered vulnerabilities | generic_linux_command, execute_code, google_search |
| **reporting_agent** | Security report generation | Creates formatted security reports from findings | generic_linux_command, execute_code |
| **dns_smtp_agent** | DNS and SMTP security testing | Email security and DNS configuration analysis | check_mail_spoofing_vulnerability, execute_cli_command |
| **thought_agent** | Strategic planning and analysis | Analyzes and plans next steps in security assessments | think |
| **use_case_agent** | Case study generation | Creates high-quality cybersecurity case studies | null_tool |
| **flag_discriminator** | Flag extraction specialist | Extracts flags from CTF challenge outputs | handoff to one_tool_agent |
| **redteam_gctr_agent** ⭐ | Red team with CTR game-theoretic analysis | Offensive security with strategic game theory | generic_linux_command, execute_code, web_search |
| **blueteam_gctr_agent** ⭐ | Blue team with CTR game-theoretic analysis | Defensive security with strategic game theory | generic_linux_command, ssh_command, execute_code, web_search |
| **bug_bounter_gctr_agent** ⭐ | Bug bounty with CTR game-theoretic analysis | Vulnerability research with strategic analysis | generic_linux_command, execute_code, shodan_search, google_search |
| **purple_redteam_agent** ⭐ | Purple team red component with shared GCTR | Red team operations with shared GCTR tracking | generic_linux_command, execute_code, web_search |
| **purple_blueteam_agent** ⭐ | Purple team blue component with shared GCTR | Blue team operations with shared GCTR tracking | generic_linux_command, ssh_command, execute_code, web_search |

⭐ this is a [CAI PRO](https://aliasrobotics.com/cybersecurityai.php) capability.

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
CAI>/agent network_security_analyzer_agent
CAI> Analyze capture.pcap for suspicious activity

# 2. Forensic investigation
CAI>/agent dfir_agent
CAI> Investigate the compromised host logs

# 3. Defensive recommendations
CAI>/agent blueteam_agent
CAI> Provide mitigation strategies based on findings
```

---


## Creating Custom Agents

CAI makes it easy to create custom agents tailored to your specific security needs. Custom agents can be configured with specialized instructions, tools, guardrails, and models.

### Key Agent Properties

-   `name`: Display name of the agent (e.g., 'Custom Pentester')
-   `description`: Brief description of the agent's purpose
-   `instructions`: The system prompt that defines agent behavior (can be static string or dynamic function)
-   `model`: Which LLM to use, with optional `model_settings` to configure parameters like temperature, top_p, etc.
-   `tools`: Tools that the agent can use to achieve its tasks
-   `input_guardrails`: Security guardrails that validate and filter inputs before processing
-   `output_guardrails`: Security guardrails that validate outputs before execution
-   `handoffs`: Allows an agent to delegate tasks to another agent

### Complete Custom Agent Example

This example demonstrates creating a security-focused agent with all recommended components:

```python
import os
from cai.sdk.agents import Agent, OpenAIChatCompletionsModel
from cai.tools.reconnaissance.generic_linux_command import generic_linux_command
from openai import AsyncOpenAI
from cai.util import create_system_prompt_renderer

# Define agent instructions
instructions = """Behave as a pentester and
                 use the generic_linux_command tool
                 to run simulated Linux commands.
                 Stay focused, concise, and task-oriented."""

custom_agent = Agent(
    name="Custom Pentester",
    description="Offensive security pentesting agent with guardrails.",
    instructions=create_system_prompt_renderer(instructions),
    tools=[
        generic_linux_command,
    ],
    model=OpenAIChatCompletionsModel(
        model=os.getenv("CAI_MODEL", "alias1"),
        openai_client=AsyncOpenAI(),
    ),
)
```

### Extend Existing Agents

This example demonstrates extending Red Team Agent **instructions** to write 'Red Team Agent at your service.' at the end of each message:

```python
from cai.cli import run_cai_cli
from cai.agents.red_teamer import redteam_agent
from cai.util import load_prompt_template
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Customize the red team agent's instructions
redteam_prompt = load_prompt_template("prompts/system_red_team_agent.md")

# Custom instruction to append
custom_append = "\n\nAt the end of each message, write 'Red Team Agent at your service.'"
modified_prompt = str(redteam_prompt) + custom_append

# Save the new instructions back to the red team agent
redteam_agent.instructions = modified_prompt

# Run your brand new red team agent with the CAI CLI
run_cai_cli(redteam_agent)
```

In the same way you could add a **custom/existing tools**:

```python
from cai.cli import run_cai_cli
from cai.agents.red_teamer import redteam_agent
from cai.sdk.agents.tool import function_tool
from cai.tools.reconnaissance.shodan import shodan_search, shodan_host_info
from dotenv import load_dotenv

# Create new fucntion for a tool
@function_tool
def hello_world() -> str:
    """
    Prints Hello, World!
    Args: None
    Returns: str: A greeting message.
    """
    return "Hello, World!"

# Load environment variables from .env file
load_dotenv()

# Add the new function and CAI shodan tools to the red team agent
redteam_agent.tools.extend([shodan_search, shodan_host_info, hello_world])

# Run the red team agent
run_cai_cli(redteam_agent)
```

If you want to create your own custom tools for your agents, see the [tools documentation](tools.md) for detailed instructions.

If you want to create Multi-Agent Patterns, see [multi_agent documentation](multi_agent.md) for orchestration patterns. 

## Context

There are two main context types. See [context](context.md) for details.

Agents are generic on their `context` type. Context is a dependency-injection tool: it's an object you create and pass to `Runner.run()`, that is passed to every agent, tool, handoff, etc., and it serves as a grab bag of dependencies and state for the agent run. You can provide any Python object as the context.

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
