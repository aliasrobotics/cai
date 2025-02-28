"""
A library to build Bug Bounty-level grade Cybersecurity AIs (CAIs).
"""
# Standard library imports
import os
import pkgutil

from cai.agents.flag_discriminator import (flag_discriminator,
                                           transfer_to_flag_discriminator)


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


def is_caiextensions_memory_available():
    """
    Check if caiextensions memory is available
    """
    try:
        from caiextensions.memory import is_memory_installed  # pylint: disable=import-error,import-outside-toplevel,unused-import  # noqa: E501,F401
    except ImportError:
        return False
    return True


def is_caiextensions_platform_available():
    """
    Check if caiextensions-platform is available
    """
    try:
        from caiextensions.platform.base import platform_manager  # pylint: disable=import-error,import-outside-toplevel,unused-import  # noqa: E501,F401
    except ImportError:
        return False
    return True
