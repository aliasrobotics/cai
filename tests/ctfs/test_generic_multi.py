"""
Generic test module for automating CTF challenge
benchmarking in CI/CD jobs.

Usage Examples:
    # Run test for a specific CTF challenge:
    $ CTF_NAME="picoctf_static_flag" pytest -s tests/ctfs/test_generic.py

    # Run test with a specific challenge and custom model:
    $ CTF_NAME="picoctf_static_flag" CTF_MODEL="gpt-4" CTF_CHALLENGE="FLAG" pytest -s tests/ctfs/test_generic.py

    # Run test with tracing disabled:
    $ CTF_NAME="picoctf_static_flag" CAI_TRACING="false" pytest -s tests/ctfs/test_generic.py

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
        CTF_MODEL: Model to use for agents (default: "qwen2.5:14b")
        CTF_RERUN: Number of times to retry failed tests (default: "0")
        CTF_INSIDE: Whether to conquer the CTF from within the CTF's Docker container
          or from outside (meaning the dev environment) (default: "true")

    Other optional:
        CAI_DEBUG: Enable/disable debug output (default: "true")
        CAI_BRIEF: Enable/disable brief output mode (default: "false")
        CAI_MAX_TURNS: Maximum number of turns for agent interactions (default: "inf")
        CAI_TRACING: Enable/disable OpenTelemetry tracing (default: "true"). When enabled,
                    traces execution flow and agent interactions for debugging and analysis.
"""

import pytest
import os
import sys
import cai as CAI
import pentestperf as ptt
from cai import CAI, Agent
from cai.tools.reconnaissance.filesystem import list_dir, cat_file
from cai.util import check_flag
from wasabi import color
from cai.logger import exploit_logger


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

            # 3. Instance the cybersecurity AI Framework client
            if os.getenv('CTF_INSIDE', "true").lower() == "true":
                client = CAI(ctf=ctf)
                ctf_inside = "You are inside the CTF docker container" 
            else:
                client = CAI()
                ctf_inside = "You are outside the CTF docker container"

            # Get model from environment or use default
            model = os.getenv('CTF_MODEL', "qwen2.5:14b")

            # 4. Create instances the agent/agents to solve the CTF
            ctf_agent = Agent(
                model=model,
                name="File listing and reader",
                instructions="You are an agent tailored to list and read files within a file system.",
                functions=[list_dir, cat_file],  # This code can execute by LLM
                # parallel_tool_calls=True, Enable multi function calling
            )

            flag_discriminator = Agent(
                model=model,
                name="Flag discriminator",
                instructions="You are an agent tailored to extract the flag from the output. ONLY return the flag, nothing else.",
                # functions=[check_flag],  # This code can execute by LLM
            )

            def transfer_to_flag_discriminator(**kwargs):
                """Transfer flag discriminator. Accepts any keyword arguments but ignores them."""
                return flag_discriminator

            ctf_agent.functions.append(transfer_to_flag_discriminator)


            messages = [{
                "role": "user",
               "content": "Instructions: " + ctf.get_instructions() +
                    "\nChallenge: " + ctf.get_challenges()[challenge] +
                    "\nTechniques: " + ctf.get_techniques() +
                    "\nIP address: " + ctf.ip_address +
                    "\n" + ctf_inside  # +
                    # "\nExtract the flag and once finished, handoff to the flag extractor
            }]

            # 5. Run the CAI
            response = client.run(
                agent=ctf_agent,
                messages=messages,
                debug=os.getenv('CAI_DEBUG', 'true').lower() == 'true',
                max_turns=float(os.getenv('CAI_MAX_TURNS', 'inf')),
                brief=os.getenv('CAI_BRIEF', 'false').lower() == 'true')
            print(response.messages[-1]["content"])
            print(f"Time taken: {response.time} seconds")

            # 6. Check if the flag is correct
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
