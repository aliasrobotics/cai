"""
A library to build Bug Bounty-level grade Cybersecurity AIs (CAIs).
"""

# Standard library imports
# None
########################################################
# Extensions utilities
########################################################
# Import agents
from cai.agents import (  # pylint: disable=unused-import # noqa: F401
    cai_initial_agent, 
    transfer_to_state_agent,  
    state_agent, 
    flag_discriminator,  
    transfer_to_flag_discriminator,  
)  


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
