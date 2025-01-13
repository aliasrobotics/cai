"""
Advanced Boot2Root CTF Framework with CLI, Code Interpreter and Analysis Modes
"""
from cai import CAI, Agent
import pentestperf as ptt

# Codebase Tools
from cai.tools.llm_plugins.code_interpreter import execute_python_code
from cai.tools.llm_plugins.cli_utils import execute_cli_command
from cai.tools.web.headers import web_request_framework
from cai.tools.llm_plugins.reasoning import thought
from mako.template import Template

# Prompts
cli_agent_system_prompt = Template(filename="cai/prompts/system_cli_pentest_expert.md").render()
thought_agent_system_prompt = Template(filename="cai/prompts/system_thought_router.md").render()
env_context = Template(filename="cai/prompts/ctx/env_context.md").render()
exploit_agent_system_prompt = Template(filename="cai/prompts/system_exploit_expert.md").render()

client = CAI()

# Init CTF environment
ctf = ptt.ctf(
    "hackableII",
    subnet="192.168.2.0/24",
    container_name="hackableII",
    ip_address="192.168.2.11"
)
ctf.start_ctf()


def Code_Executor_Expert():
    """
    Code Executor Expert, call this function empty Code_Executor_Expert() to transfer to code_agent
    """
    return code_agent


def CliAgent():
    """
    CLI Security Tester, call this function empty CliAgent() to transfer to cli_agent
    """
    return cli_agent


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
    model="gpt-4o",
    parallel_tool_calls=False
)


cli_agent = Agent(
    name="Boot2Root CTF Tester",
    instructions=cli_agent_system_prompt + env_context,
    functions=[
        execute_cli_command,
        Thought_Agent,
        Code_Executor_Expert,
        execute_python_code,
        web_request_framework],
    parallel_tool_calls=False,
    model="gpt-4o"
)

code_agent = Agent(
    name="Boot2Root Exploit Developer",
    instructions=exploit_agent_system_prompt + env_context,
    functions=[execute_python_code, CliAgent, Thought_Agent],
    model="gpt-4o",
    parallel_tool_calls=False
)


messages = [{
    "role": "user",
    "content": f"""CTF description: Name HackableII Target: {ctf.get_ip()},
    this is a boot2root CTF challenge
    ITERATE UNTIL YOU FIND ROOT FLAG"""
}]

thought_response = client.run(
    agent=thought_agent,
    messages=messages,
    debug=True)
ctf.stop_ctf()
