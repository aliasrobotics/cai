"""
Implementation of a Cyclic Swarm Pattern for Bug Bounty Triage Operations

This module establishes a coordinated multi-agent system where specialized agents
collaborate on vulnerability discovery and verification tasks. The pattern 
implements a directed graph of agent relationships, where each agent can transfer 
context (message history) to another agent through handoff functions, creating a 
complete communication network for comprehensive bug bounty and triage analysis.
"""
from cai.agents.retester import retester_agent
from cai.agents.bug_bounter import bug_bounter_agent
from cai.sdk.agents import handoff
from cai.util import append_instructions


# Clone agents to avoid modifying the original instances
_retester_agent_copy = retester_agent.clone()
_bug_bounter_agent_copy = bug_bounter_agent.clone()

# Clear any existing handoffs to ensure independence
_retester_agent_copy.handoffs = []
_bug_bounter_agent_copy.handoffs = []

# Create handoffs using the SDK handoff function
_retester_handoff = handoff(
    agent=_retester_agent_copy,
    tool_description_override="Transfer to Retester Agent for vulnerability confirmation and triage"
)

_bug_bounter_handoff = handoff(
    agent=_bug_bounter_agent_copy,
    tool_description_override="Transfer to Bug Bounter Agent for vulnerability discovery and bug bounty hunting"
)

# Register handoff to enable inter-agent communication pathways
_bug_bounter_agent_copy.handoffs.append(_retester_handoff)
_retester_agent_copy.handoffs.append(_bug_bounter_handoff)

# Customize agent properties and add handoff instructions
_bug_bounter_agent_copy.name = "Bug bounty Triage Agent"
_bug_bounter_agent_copy.description = (
    "Agent that specializes in vulnerability discovery and bug bounty "
    "hunting without false positives"
)

# Add handoff instructions to Bug Bounter agent
append_instructions(
    _bug_bounter_agent_copy,
    "\n\nWhen you discover potential vulnerabilities, transfer to "
    "the Retester Agent for verification and triage."
)

# Add handoff instructions to Retester agent
append_instructions(
    _retester_agent_copy,
    "\n\nAfter completing verification and triage, transfer back "
    "to the Bug Bounter Agent to continue vulnerability discovery."
)

# Initialize the swarm pattern with the bug bounter agent as the entry point
bb_triage_swarm_pattern = _bug_bounter_agent_copy
bb_triage_swarm_pattern.pattern = "swarm"
