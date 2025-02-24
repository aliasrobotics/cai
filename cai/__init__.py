"""
A library to build Bug Bounty-level grade Cybersecurity AIs (CAIs).
"""
# Standard library imports
import os
import pkgutil

from cai.agents.flag_discriminator import flag_discriminator, transfer_to_flag_discriminator

# RAG memory
from cai.agents.memory import (
    episodic_builder,
    query_agent,
    semantic_builder
)
# Extend the search path for namespace packages (allows merging)
__path__ = pkgutil.extend_path(__path__, __name__)

# Import state transfer functions
# NOTE: this, together with the logic in test_generic.py,
# is a workaround to make the state agent work.
# Need to unify it all together and make it work
# agnostic to the state agent implementation.
#
# TODO: fix this  # pylint: disable=fixme
from cai.state.pydantic import state_agent

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
else:
    # stop and raise error
    raise ValueError(f"Invalid CAI agent type: {cai_agent}")


def transfer_to_state_agent():
    """
    Transfer to the state agent
    """
    return state_agent



def transfer_to_episodic_memory_agent(**kwargs):  # pylint: disable=W0613
    """ Transfer to episodic memory agent.
    Accepts any keyword arguments but ignores them."""
    return episodic_builder


def transfer_to_semantic_memory_agent(**kwargs):  # pylint: disable=W0613
    """ Transfer to semantic memory agent.
    Accepts any keyword arguments but ignores them."""
    return semantic_builder


def transfer_to_query_memory_agent(**kwargs):  # pylint: disable=W0613
    """ Transfer to query memory agent.
    Accepts any keyword arguments but ignores them."""
    return query_agent

########################################################
# Extensions utilities
########################################################
def is_pentestperf_available():
    """
    Check if pentestperf is available
    """
    try:
        from pentestperf.ctf import CTF  # pylint: disable=import-error,import-outside-toplevel,unused-import  # noqa: E501,F401
    except ImportError:
        return False
    return True


def is_caiextensions_report_available():
    """
    Check if caiextensions report is available
    """
    try:
        from caiextensions.report.common import get_base_instructions  # pylint: disable=import-error,import-outside-toplevel,unused-import  # noqa: E501,F401
    except ImportError:
        return False
    return True