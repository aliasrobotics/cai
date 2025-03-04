"""
CAI agents init
"""

# Standard library imports
import os
import pkgutil

# Local application imports
from cai.agents.flag_discriminator import (
    flag_discriminator,
    transfer_to_flag_discriminator
)
from cai.state.pydantic import state_agent


# Extend the search path for namespace packages (allows merging)
__path__ = pkgutil.extend_path(__path__, __name__)

# Get model from environment or use default
model = os.getenv('CAI_MODEL', "qwen2.5:14b")


########################################################
# MAIN
########################################################

cai_agent = os.getenv('CAI_AGENT_TYPE', "one_tool").lower()

if cai_agent == "one_tool":
    from cai.agents.one_tool import ctf_agent_one_tool, transfer_to_ctf_agent_one_tool  # noqa
    cai_initial_agent = ctf_agent_one_tool  # noqa
    cai_initial_agent.functions.append(
        transfer_to_flag_discriminator
    )
    flag_discriminator.functions.append(transfer_to_ctf_agent_one_tool)
elif cai_agent == "codeagent":
    from cai.agents.codeagent import codeagent
    cai_initial_agent = codeagent
elif cai_agent == "boot2root":
    from cai.agents.cli_basic import boot2root_agent
    cai_initial_agent = boot2root_agent
else:
    # stop and raise error
    raise ValueError(f"Invalid CAI agent type: {cai_agent}")


def transfer_to_state_agent():
    """
    Transfer to the state agent
    """
    return state_agent
