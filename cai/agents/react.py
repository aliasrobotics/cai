"""
ReAct (Reasoning + Acting) agents for CAI.

This module implements the ReAct pattern for AI agents, which combines:
1. Reasoning: Reflecting on previous steps and current state
2. Acting: Taking concrete actions by invoking tools
3. Observing: Processing the results of actions

The agents work together in a cycle:
- ReAct Reason Agent: Plans next steps based on context
- ReAct Act Agent: Executes planned actions using tools
- ReAct Observe Agent: Analyzes results and updates context

This creates a continuous loop of reflection, action and observation
that enables more strategic and effective CTF solving.
"""


from cai.types import Agent
import os
from cai.tools.reconnaissance.generic_linux_command import generic_linux_command  # noqa
from cai.agents.flag_discriminator import transfer_to_flag_discriminator  # noqa

model = os.getenv('CAI_MODEL', "qwen2.5:14b")

REACT_COMMON_INSTRUCTIONS = """You are a Cybersecurity expert Leader facing
                     a CTF challenge.
                    INSTRUCTIONS:
                    1. Execute the generic_linux_command tool without any
                    explanation.
                    2. Be efficient and strategic when executing commands.
                    3. Never assume the flag format - it could be any string
                    4. NEVER GIVE UP. KEEP EXECUTING TOOLS UNTIL YOU FIND
                    THE FLAG.
                    5. IF YOU ENCOUNTER A PROBLEM, IT IS HIGHLY LIKELY
                    THAT YOU ARE ASSUMING WRONG FILENAMES, PORTS,
                    IP ADDRESSES, ETC. PAY ATTENTION TO YOUR HALLUCINATIONS.
                    6. YOU MUST USE THE flag_discriminator to check the flag
                    when you have it in DECODED 64-bit format
                    7. Do a initial recon (nmap, service enumeration)
                    """

react_reason_agent = Agent(
    model=model,
    name="ReAct 'Reasoning' Agent",
    instructions=REACT_COMMON_INSTRUCTIONS + """

                    Your goal is to act as a reasoning agent that reflects
                    on the previous steps and the current state of the CTF
                    challenge and then decide what to do next.

                    After doing that reasoning, you will handoff and transfer
                    to thereact_act_agent to invoke a tool.
                    """,
)


react_act_agent = Agent(
    model=model,
    name="ReAct 'Acting' Agent",
    instructions=REACT_COMMON_INSTRUCTIONS + """

                    Your goal is to act as a acting agent that invokes a tool.

                    Then, you will handoff and transfer to the
                    react_observe_agent to observe and reflect on the output.
                    """,
    functions=[
        generic_linux_command,
    ],
    parallel_tool_calls=False,
    tool_choice="required"

)

react_observe_agent = Agent(
    model=model,
    name="ReAct 'Observing' Agent",
    instructions=REACT_COMMON_INSTRUCTIONS + """

                    Your goal is to act as a observing agent that observes
                    the output of the react_act_agent and reflects
                    on the output.

                    Then, you will handoff and transfer to the
                    react_reason_agent to reason again.
                    """,
)


def transfer_to_react_act_agent(**kwargs):  # pylint: disable=W0613
    """Transfer to react act agent after reasoning"""
    return react_act_agent


def transfer_to_react_observe_agent(**kwargs):  # pylint: disable=W0613
    """Transfer to react observe agent after reasoning"""
    return react_observe_agent


def transfer_to_react_reason_agent(**kwargs):  # pylint: disable=W0613
    """Transfer to react reason agent after observing"""
    return react_reason_agent


react_reason_agent.functions.extend([
    transfer_to_react_act_agent,
    transfer_to_flag_discriminator,
])

react_act_agent.functions.extend([
    transfer_to_react_observe_agent,
])

react_observe_agent.functions.extend([
    transfer_to_react_reason_agent,
    transfer_to_flag_discriminator,
])