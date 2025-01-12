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
# Prompts
cli_agent_system_prompt = open(
    "cai/prompts/system_cli_pentest_expert.txt").read()
thought_agent_system_prompt = open(
    "cai/prompts/system_thought_router.txt").read()
env_context = open("cai/prompts/ctx/env_context.txt").read()
exploit_agent_system_prompt = open(
    "cai/prompts/system_exploit_expert.txt").read()

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
    model="claude-3-5-sonnet-20240620",
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
    "content": f"""CTF description: Name HackableII Target: {ctf.get_ip()},
    this is a boot2root CTF challenge
    ITERATE UNTIL YOU FIND ROOT FLAG"""
}]

thought_response = client.run(
    agent=thought_agent,
    messages=messages,
    debug=True,
    record_training_data=True)
ctf.stop_ctf()
