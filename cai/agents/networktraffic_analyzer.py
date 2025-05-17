"""Network Traffic Security Analyzer Agent
Network Traffic Security Analysis Agent module for monitoring and analyzing network communications from a cybersecurity perspective.
This agent specializes in:

- Security-focused packet analysis: Identifying malicious patterns in network packets
- Protocol security analysis: Detecting protocol abuse and malicious exploitation
- Threat monitoring: Real-time detection of suspicious network traffic patterns
- Attack surface identification: Mapping potential network entry points for attackers
- Network anomaly detection: Identifying unusual patterns indicating potential security incidents
- Lateral movement detection: Spotting signs of attackers moving through the network
- Security event correlation: Connecting related security events across the network
- Malicious traffic identification: Detecting command and control traffic and data exfiltration
- Continuous traffic monitoring: Real-time analysis of ongoing network traffic captures

Objectives:
- Incident root cause analysis: Identifying the original cause of security incidents
- Threat actor analysis: Analyzing network patterns to identify and profile potential threat actors
- Vulnerability impact understanding: Assessing how vulnerabilities affect network security
"""
import os
from cai.types import Agent  # pylint: disable=import-error
from cai.util import load_prompt_template  # Add this import
from cai.tools.command_and_control.sshpass import (  # pylint: disable=import-error # noqa: E501
    run_ssh_command_with_credentials
)

from cai.tools.reconnaissance.generic_linux_command import (  # pylint: disable=import-error # noqa: E501
    generic_linux_command
)

from cai.tools.reconnaissance.exec_code import (  # pylint: disable=import-error # noqa: E501
    execute_code
)
from cai.tools.web.search_web import (  # pylint: disable=import-error # noqa: E501
    make_web_search_with_explanation,
)
# Import remote traffic capture tools

from cai.tools.network.capture_traffic import (
    capture_remote_traffic,
    remote_capture_session
)

from cai.agents.dfir import transfer_to_dfir_agent
from cai.agents.replay_attack_agent import transfer_to_replay_attack_agent


# Prompts
network_security_analyzer_prompt = load_prompt_template("prompts/system_network_analyzer.md")
# Define functions list based on available API keys
functions = [
    generic_linux_command,
    run_ssh_command_with_credentials,
    execute_code,
    capture_remote_traffic,
    remote_capture_session,
]

if os.getenv('PERPLEXITY_API_KEY'):
    functions.append(make_web_search_with_explanation)

# Handoff to agents for further analysis
functions.append(transfer_to_dfir_agent)
functions.append(transfer_to_replay_attack_agent)

network_security_analyzer_agent = Agent(
    name="Network Security Analyzer",
    instructions=network_security_analyzer_prompt,
    description="""Agent that specializes in network security analysis.
                   Expert in monitoring, capturing, and analyzing network communications for security threats.""",
    model=os.getenv('CAI_MODEL', "qwen2.5:14b"),
    functions=functions,
    parallel_tool_calls=False,
)

def transfer_to_network_security_agent():
    return network_security_analyzer_agent
