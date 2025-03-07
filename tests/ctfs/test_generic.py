"""
Generic test module for automating CTF challenge
benchmarking in CI/CD jobs.

Usage Examples:
    # Run test for a specific CTF challenge:
    $ CTF_NAME="picoctf_static_flag" pytest -s tests/ctfs/test_generic.py

    # Run test with a specific challenge and custom model:
    $ CTF_NAME="picoctf_static_flag" CAI_MODEL="gpt-4o" CTF_CHALLENGE="FLAG" pytest -s tests/ctfs/test_generic.py

    # Run test with tracing disabled:
    $ CTF_NAME="picoctf_static_flag" CAI_TRACING="false" pytest -s tests/ctfs/test_generic.py

    # Run test using a specific challenge:
    $ CTF_NAME="kiddoctf" CTF_CHALLENGE="02 linux ii" CAI_MODEL="gpt-4o" pytest -s tests/ctfs/test_generic.py

    # Run generating a report
    $ CTF_NAME="kiddoctf" CTF_CHALLENGE="02 linux ii" CAI_TRACING=False CAI_REPORT=ctf CAI_MODEL="gpt-4o" pytest -s tests/ctfs/test_generic.py

    # Run against a CTF with RAG memory
    CTF_NAME="hackableII" CAI_MEMORY="True" CAI_MODEL="o3-mini" CTF_INSIDE="False" python3 cai/cli.py

    # Run against a CTF with RAG memory and store in memory every 3 interactions
    CTF_NAME="hackableII" CAI_MEMORY="True" CAI_MEMORY_ONLINE_INTERVAL=3 CAI_MODEL="o3-mini" CTF_INSIDE="False" python3 cai/cli.py    

    # Run against a CTF with RAG memory and limit the cost to 5 dollars
    CTF_NAME="hackableII" CAI_MODEL="o3-mini" CTF_INSIDE="False" CAI_PRICE_LIMIT="5" python3 cai/cli.py

CI/CD Pipeline Configuration:
    Add the following structure to .ctf.yml file:

    🚩 generic_ctf_test:
      <<: *run_test
      stage: ctf-super-easy  # or any other stage
      variables:
        CTF_NAME: picoctf_static_flag
        CTF_CHALLENGE: challenge_name  # optional

Environment Variables:
    Required:
        CTF_NAME: Name of the CTF challenge to run (e.g. "picoctf_static_flag")

    Optional:
        CTF_CHALLENGE: Specific challenge name within the CTF to test
        CTF_SUBNET: Network subnet for the CTF container (default: "192.168.2.0/24")
        CTF_IP: IP address for the CTF container (default: "192.168.2.100")        
        CTF_RERUN: Number of times to retry failed tests (default: "0")
        CTF_INSIDE: Whether to conquer the CTF from within the CTF's Docker container
          or from outside (meaning the dev environment) (default: "true")

    Other optional:
        CAI_MODEL: Model to use for agents
            (default: "qwen2.5:14b")
        CAI_DEBUG: Set debug output level (default: "1")
            - 0: Only tool outputs
            - 1: Verbose debug output
            - 2: CLI debug output
        CAI_BRIEF: Enable/disable brief output mode (default: "false")
        CAI_MAX_TURNS: Maximum number of turns for
            agent interactions (default: "inf")
        CAI_TRACING: Enable/disable OpenTelemetry tracing
            (default: "true"). When enabled, traces execution 
            flow and agent interactions for debugging and analysis.
        CAI_AGENT_TYPE: Specify the agents to use it could take
            the value of (default: "one_tool_agent"). Use "/agent"
            command in CLI to list all available agents.
        CAI_STATE: Enable/disable stateful mode (default: "false").
            When enabled, the agent will use a state agent to keep 
            track of the state of the network and the flags found.
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
        CAI_SUPPORT_MODEL: Model to use for the support agent
            (default: "o3-mini")
        CAI_SUPPORT_INTERVAL: Number of turns between
            support agent executions (default: "5")
    
    Extensions (only applicable if the right extension is installed):

        "report"
            CAI_REPORT: Enable/disable reporter mode. Possible values:
                - ctf (default): do a report from a ctf resolution
                - nis2: do a report for nis2
                - pentesting: do a report from a pentesting      
"""

import pytest
import os
import sys
import json
from cai.core import CAI
from cai import (
    cai_initial_agent,
    is_caiextensions_report_available,
    is_pentestperf_available
)
from cai.util import check_flag
from wasabi import color
from importlib.resources import files
from mako.template import Template  # pylint: disable=import-error
if is_caiextensions_report_available():
    from caiextensions.report.ctf.ctf_reporter_agent import reporter_agent # pylint: disable=import-error
    from caiextensions.report.common import create_report  # pylint: disable=import-error # noqa: E501
else:
    print("caiextensions-report is not available. Skipping test.")
    pytest.skip("caiextensions-report is not available. Skipping test.", allow_module_level=True)

if is_pentestperf_available():
    import pentestperf as ptt
else:
    print("PentestPerf is not available. Skipping test.")
    pytest.skip("PentestPerf is not available. Skipping test.", allow_module_level=True)
    
def check_env_variables():
    required_vars = ['CTF_NAME']
    for var in required_vars:
        if not os.getenv(var):
            print(f"Environment variable {var} is not set. Exiting tests.")
            sys.exit(1)


@pytest.fixture(scope="class")
def basic_ctf():
    check_env_variables()
    ctf = ptt.ctf(
        os.getenv('CTF_NAME'),
        subnet=os.getenv('CTF_SUBNET', "192.168.2.0/24"),
        container_name="ctf_target",
        ip_address=os.getenv('CTF_IP', "192.168.2.100"),
    )
    ctf.start_ctf()
    flag = ctf.get_flag()  # not used
    yield ctf, flag
    ctf.stop_ctf()

# NOTE.
# If you want to keep using pytest fixtures, you need to change your
# test class to inherit from object instead of unittest.TestCase and
# use pytest's test discovery
#
# That's why this class inherits from object and not unittest.TestCase
#
class TestGenericCTF:
    @pytest.mark.flaky(reruns=int(os.getenv('CTF_RERUN', '0')), reruns_delay=1)
    def test_ctf_solver(self, basic_ctf):
        # create ctf object
        ctf, flag = basic_ctf

        # Get the challenge from the environment variable or default to the
        # first challenge
        challenge_key = os.getenv('CTF_CHALLENGE')  # TODO:
        challenges = list(ctf.get_challenges().keys())
        challenge = challenge_key if challenge_key in challenges else (
            challenges[0] if len(challenges) > 0 else None)

        print(
            color(
                "Testing CTF: ",
                fg="black",
                bg="yellow") +
            color(
                ctf.name,
                fg="black",
                bg="yellow"))
        if not challenge_key or challenge_key not in challenges:
            print(
                color(
                    "No challenge provided or challenge not found. Attempting to use the first challenge.",
                    fg="white",
                    bg="blue"))
        if challenge:
            print(
                color(
                    "Testing challenge: ",
                    fg="white",
                    bg="blue") +
                color(
                    "'" +
                    challenge +
                    "' (" +
                    repr(
                        ctf.flags[challenge]) +
                    ")",
                    fg="white",
                    bg="blue"))

            # Get model from environment or use default
            model = os.getenv('CAI_MODEL', "qwen2.5:14b")

            # Determine if stateful or stateless
            state_agent = None
            stateful = os.getenv('CAI_STATE', "false").lower() == "true"
            if stateful:
                from cai.state.pydantic import state_agent
                # from cai.state.free import state_agent
                state_agent.model = model  # set model

            # Instance the cybersecurity AI Framework client
            if ctf: 
                if os.getenv('CTF_INSIDE', "true").lower() == "true":
                    client = CAI(ctf=ctf, state_agent=state_agent, force_until_flag=True, challenge=challenge, source="test_generic")
                else:
                    client = CAI(ctf=ctf, state_agent=state_agent, force_until_flag=True, challenge=challenge, ctf_inside=False, source="test_generic")
            else:
                client = CAI(state_agent=state_agent, force_until_flag=True, challenge=challenge, ctf_inside=False, source="test_generic")

            # Use the user master template
            messages = [{
                "role": "user", 
                "content": Template(
                    filename="cai/prompts/core/user_master_template.md").render(
                        ctf=ctf,
                        challenge=challenge,
                        ip=ctf.get_ip() if ctf else None,
                        )
            }]
            # Run the CAI
            response = client.run(
                # cli=True,
                agent=cai_initial_agent,
                messages=messages,
                debug=float(os.getenv('CAI_DEBUG', 2)),
                max_turns=float(os.getenv('CAI_MAX_TURNS', 'inf')),
                brief=os.getenv('CAI_BRIEF', 'false').lower() == 'true')
            
            print(f"Time taken: {response.time} seconds")

            # Do a report in case the environment variable is true
            if os.getenv("CAI_REPORT"):
                template = str(files('caiextensions.report.ctf') / 'template.md')
                # New instace of CAI, because force_until_flag
                client = CAI(state_agent=state_agent, force_until_flag=False, source="test_generic")
                response_report = client.run(
                    agent=reporter_agent,
                    messages=[{"role": "user", "content": "Do a report from " +
                            "\n".join(msg['content'] for msg in response.messages if msg.get('content') is not None)}], # noqa: E501
                    debug=float(os.getenv('CAI_DEBUG', 2)),
                    max_turns=float(os.getenv('CAI_MAX_TURNS', 'inf')),
                )
                 # Add user message to history
                response.messages.insert(0, messages[0])

                # Render the report with function create_report
                report_data = json.loads(response_report.messages[0]['content'])
                report_data["history"] = json.dumps(response.messages, indent=4)
                create_report(report_data, template)

            # Check if the flag is correct
            success, flag = check_flag(
                response.messages[-1]["content"], ctf, challenge)
            # assert results
            assert success, "Flag found"
        else:
            print(color("No challenge found", fg="white", bg="red"))
            assert False, "No challenge found"


if __name__ == '__main__':
    check_env_variables()
    pytest.main()
