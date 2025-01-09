"""
This is a short example of how we can solve ctf scenarios programmatically. With CAI framework
"""
# 1. Instance CAI, pentestperf and tools
from cai import CAI, Agent
from cai.tools.cli import list_dir, cat_file
import pentestperf as ptt
from wasabi import color

# 2. Init the CTF environment
ctf = ptt.ctf(
    "picoctf_static_flag",
    subnet="192.168.9.0/24",
    container_name="ancient",
    ip_address="192.168.9.52"
)
ctf.start_ctf()
challenges = list(ctf.get_challenges().keys())
challenge = challenges[0]

# 3. Instance the cybersecurity AI Framework client
client = CAI(ctf=ctf)

# 4. Instance the agent/agents to solve the CTF
ctf_agent = Agent(
    model="qwen2.5:14b",
    name="A file listing tool",
    instructions="You are an agent tailored to list and read files within a file system.",
    functions=[list_dir, cat_file],  # This code can execute by LLM
    # parallel_tool_calls=True, Enable multi function calling
)


messages = [{
    "role": "user",
    "content": "Instructions: " + ctf.get_instructions() +
               "\nChallenge: " + ctf.get_challenges()[challenge] +
               "\nTechniques: " + ctf.get_techniques() +
               "\nExtract and return only the flag"
}]

# 5. Run the swarm
response = client.run(agent=ctf_agent, messages=messages, debug=True)
print(response.messages[-1]["content"])

ctf.stop_ctf()
