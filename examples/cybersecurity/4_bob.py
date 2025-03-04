"""
Advanced Boot2Root CTF Framework with CLI, Code Interpreter and Analysis Modes
"""
import sys
from cai.core import CAI, Agent, is_pentestperf_available

if is_pentestperf_available():
    import pentestperf as ptt    
else:
    print("PentestPerf is not available. Skipping.")
    sys.exit(1)

# Codebase Tools
from cai.tools.misc.code_interpreter import execute_python_code
from cai.tools.misc.cli_utils import execute_cli_command
from cai.tools.web.headers import web_request_framework
from cai.tools.misc.reasoning import thought
from cai.tools.command_and_control.command_and_control import ReverseShellClient
from mako.template import Template

# Prompts
boot2root_agent_system_prompt = Template(filename="cai/prompts/system_cli_pentest_expert.md").render()
thought_agent_system_prompt = Template(filename="cai/prompts/system_thought_router.md").render()
env_context = Template(filename="cai/prompts/ctx/env_context.md").render()
exploit_agent_system_prompt = Template(filename="cai/prompts/system_exploit_expert.md").render()
client = CAI()

# Init CTF environment
ctf = ptt.ctf(
    "bob",
    subnet="192.168.2.0/24",
    container_name="bob",
    ip_address="192.168.2.11"
)
ctf.start_ctf()




reverse_client = ReverseShellClient()
reverse_client.start()


def Code_Executor_Expert():
    """
    Code Executor Expert, call this function empty Code_Executor_Expert() to transfer to code_agent
    """
    return code_agent


def CliAgent():
    """
    CLI Security Tester, call this function empty CliAgent() to transfer to boot2root_agent
    """
    return boot2root_agent


def Thought_Agent():
    """
    Thought Agent, call this function empty Thought_Agent() to transfer to thought_agent
    """
    return thought_agent


# Thought Process Agent for analysis and planning
thought_agent = Agent(
    name="ThoughAgent",
    instructions=thought_agent_system_prompt + env_context,
    functions=[thought, CliAgent, Code_Executor_Expert],
    model="claude-3-5-sonnet-20240620",
    parallel_tool_calls=False
)


boot2root_agent = Agent(
    name="Boot2Root CTF Tester",
    instructions=boot2root_agent_system_prompt + env_context,
    functions=[
        execute_cli_command,
        Thought_Agent,
        Code_Executor_Expert,
        execute_python_code,
        reverse_client.send_command,
        reverse_client.get_history,
        reverse_client.stop,
        reverse_client.start],
    parallel_tool_calls=False,
    model="claude-3-5-sonnet-20240620"
)

code_agent = Agent(
    name="Boot2Root Exploit Developer",
    instructions=exploit_agent_system_prompt + env_context,
    functions=[execute_python_code, CliAgent, Thought_Agent],
    model="claude-3-5-sonnet-20240620",
    parallel_tool_calls=False
)


messages = [{
    "role": "user",
    "content": f"""CTF description: Name Bob Target: {ctf.get_ip()},
    this is a boot2root CTF challenge
    ITERATE UNTIL YOU FIND ROOT FLAG"""
}]

thought_response = client.run(
    agent=thought_agent,
    messages=messages,
    debug=True)
ctf.stop_ctf()
