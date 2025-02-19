"""
This is a short example of how we can solve ctf scenarios programmatically. With CAI framework
"""
# 1. Instance CAI, pentestperf and tools
import sys
from cai.core import CAI, Agent, is_pentestperf_available
from cai.tools.reconnaissance.crypto_tools import *
from cai.tools.reconnaissance.nmap import *
from cai.tools.reconnaissance.netcat import *

if is_pentestperf_available():
    import pentestperf as ptt    
else:
    print("PentestPerf is not available. Skipping.")
    sys.exit(1)


# 2. Init the CTF environment
ctf = ptt.ctf(
    "picoctf_reversing_python",
    subnet="192.168.2.0/24",
    container_name="ancient",
    ip_address="192.168.2.52"
)
ctf.start_ctf()
challenges = list(ctf.get_challenges().keys())
challenge = challenges[0]

# 3. Instance the cybersecurity AI Framework client
client = CAI()

# 4. Instance the agent/agents to solve the CTF
ctf_agent = Agent(
    model="qwen2.5:14b",
    name="CTF agent",
    instructions="You are an CTF solver agent",
    functions=[netcat, nmap, decode64],  # This code can execute by LLM
    # parallel_tool_calls=True, Enable multi function calling
)


messages = [{
    "role": "user",
    "content": "Instructions: " + ctf.get_instructions() +
               "\nChallenge: " + ctf.get_challenges()[challenge] +
               "\nTechniques: " + ctf.get_techniques() +
               "\nTarget IP: " + ctf.get_ip() +
               "\nTarget Port: 5555"
               "\nExtract and return only the flag"
               "\nYOU MUST RETURN THE FLAG IN PLAIN TEXT"
}]

# 5. Run the CAI
response = client.run(
    agent=ctf_agent,
    messages=messages,
    debug=True,
    brief=True)
print(response.messages[-1]["content"])

ctf.stop_ctf()
