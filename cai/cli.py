"""
This module provides a CLI interface for testing and
interacting with CAI agents.

Environment Variables
---------------------
    Required:
        N/A

    Optional:
        CTF_NAME: Name of the CTF challenge to
            run (e.g. "picoctf_static_flag")
        CTF_CHALLENGE: Specific challenge name
            within the CTF to test
        CTF_SUBNET: Network subnet for the CTF
            container (default: "192.168.2.0/24")
        CTF_IP: IP address for the CTF
            container (default: "192.168.2.100")
        CTF_INSIDE: Whether to conquer the CTF from
            within container (default: "true")

        CAI_MODEL: Model to use for agents
            (default: "qwen2.5:14b")
        CAI_DEBUG: Set debug output level (default: "1")
        CAI_BRIEF: Enable/disable brief output mode (default: "false")
        CAI_MAX_TURNS: Maximum number of turns for
            agent interactions (default: "inf")
        CAI_TRACING: Enable/disable OpenTelemetry tracing
            (default: "true")
        CAI_AGENT_TYPE: Specify agent type (default: "one_tool")
        CAI_STATE: Enable/disable stateful mode (default: "false")
        CAI_MEMORY: Enable/disable memory mode (default: "false")
            - episodic: use episodic memory
            - semantic: use semantic memory
            - all: use both episodic and semantic memorys
        CAI_MEMORY_ONLINE: Enable/disable online memory mode
            (default: "false")
        CAI_MEMORY_OFFLINE: Enable/disable offline memory
            (default: "false")
        CAI_ENV_CONTEXT: Add enviroment context, dirs and
            current env available (default: "true")
        CAI_MEMORY_ONLINE_INTERVAL: Number of turns between
            online memory updates (default: "5")
        CAI_PRICE_LIMIT: Price limit for the conversation in dollars
            (default: "1")
    Extensions (only applicable if the right extension is installed):

        "report"
            CAI_REPORT: Enable/disable reporter mode. Possible values:
                - ctf (default): do a report from a ctf resolution
                - nis2: do a report for nis2
                - pentesting: do a report from a pentesting

Usage Examples:

    # Run against a CTF
    CTF_NAME="kiddoctf" CTF_CHALLENGE="02 linux ii" \
        CAI_MODEL="gpt-4o" CAI_TRACING="false" python3 cai/cli.py

    # Run without a target in human-in-the-loop mode, generating a report
    CAI_TRACING=False CAI_REPORT=pentesting CAI_MODEL="gpt-4o" \
        python3 cai/cli.py

    # Run with online episodic memory
    #   registers memory every 5 turns:
    #   limits the cost to 5 dollars
    CTF_NAME="hackableII" CAI_MEMORY="episodic" \
        CAI_MODEL="o3-mini" CAI_MEMORY_ONLINE="True" \
        CTF_INSIDE="False" CTF_HINTS="False"  \
        CAI_PRICE_LIMIT="5" python3 cai/cli.py

    # Run with custom long_term_memory interval
    # Executes memory long_term_memory every 3 turns:
    CTF_NAME="hackableII" CAI_MEMORY="episodic" \
        CAI_MODEL="o3-mini" CAI_MEMORY_ONLINE_INTERVAL="3" \
        CAI_MEMORY_ONLINE="False" CTF_INSIDE="False" \
        CTF_HINTS="False" python3 cai/cli.py
"""
# Standard library imports
import os

# Third-party imports
from wasabi import color  # pylint: disable=import-error

# Local imports

from cai import (
    is_pentestperf_available,
    cai_initial_agent
)
from cai.repl import run_demo_loop
from cai.agents.cli_basic import cli_agent

if is_pentestperf_available():
    import pentestperf as ptt  # pylint: disable=import-error

# Import and register platforms at startup


def initialize_platforms():
    """Initialize and register available platforms."""
    try:
        from caiextensions.platform.base import platform_manager  # pylint: disable=import-error,import-outside-toplevel,unused-import,line-too-long,no-name-in-module # noqa: E501
        from caiextensions.platform.htb.platform import HTBPlatform  # pylint: disable=import-error,import-outside-toplevel,unused-import,line-too-long,no-name-in-module # noqa: E501
        platform_manager.register_platform("htb", HTBPlatform())
    except ImportError:
        pass


def setup_ctf():
    """Setup CTF environment if CTF_NAME is provided"""
    ctf_name = os.getenv('CTF_NAME', None)
    if not ctf_name:
        return None

    print(color("Setting up CTF: ", fg="black", bg="yellow") +
          color(ctf_name, fg="black", bg="yellow"))

    ctf = ptt.ctf(
        ctf_name,
        subnet=os.getenv('CTF_SUBNET', "192.168.2.0/24"),
        container_name="ctf_target",
        ip_address=os.getenv('CTF_IP', "192.168.2.100"),
    )
    ctf.start_ctf()
    return ctf


def run_with_env():
    """
    Run the CAI CLI with environment variable configuration.

    This function sets up and runs the CAI CLI with env-vars:

    Environment Variables:
        CTF_NAME: Name of CTF to set up and run
        CTF_SUBNET: Subnet for CTF environment (default: 192.168.2.0/24)
        CTF_IP: IP address for CTF target (default: 192.168.2.100)
        CAI_STATE: Enable state tracking agent if "true" (default: "false")
        CAI_MODEL: Model to use for agents (default: "qwen2.5:14b")
        CAI_DEBUG: Debug level (default: 2)
        CAI_MAX_TURNS: Maximum conversation turns (default: inf)

    The function:
    1. Sets up CTF environment if CTF_NAME is provided
    2. Configures state tracking agent if CAI_STATE is enabled
    3. Runs interactive conversation loop with specified parameters
    4. Cleans up CTF environment on completion
    """
    from cai.state.pydantic import state_agent  # pylint: disable=import-outside-toplevel # noqa: E501

    # Initialize platforms first
    initialize_platforms()

    if (is_pentestperf_available() and
            os.getenv('CTF_NAME', None)):
        ctf = setup_ctf()
    else:
        ctf = None

    try:
        # Configure state agent if enabled
        if os.getenv('CAI_STATE', "false").lower() == "true":
            state_agent.model = os.getenv('CAI_MODEL', "qwen2.5:14b")
        else:
            state_agent = None

        # Run interactive loop with CTF and state agent if available
        run_demo_loop(
            cai_initial_agent,
            debug=float(os.getenv('CAI_DEBUG', '2')),
            max_turns=float(os.getenv('CAI_MAX_TURNS', 'inf')),
            ctf=ctf if os.getenv('CTF_NAME', None) else None,
            state_agent=state_agent
        )

    finally:
        # Cleanup CTF if started
        if (is_pentestperf_available() and
                os.getenv('CTF_NAME', None)):
            ctf.stop_ctf()


if __name__ == "__main__":
    run_with_env()
