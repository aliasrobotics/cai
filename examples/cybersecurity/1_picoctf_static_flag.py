"""
This is a short example of how we can solve ctf scenarios programmatically. With CAI framework
"""
# 1. Instance CAI, pentestperf and tools
import sys
from cai.core import CAI, Agent, is_pentestperf_available
from cai.tools.reconnaissance.filesystem import list_dir, cat_file
from cai.util import check_flag


if is_pentestperf_available():
    import pentestperf as ptt    
else:
    print("PentestPerf is not available. Skipping.")
    sys.exit(1)


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

# 4. Create instances the agent/agents to solve the CTF
ctf_agent = Agent(
    model="qwen2.5:14b",
    name="File listing and reader",
    instructions="You are an agent tailored to list and read files within a file system.",
    functions=[list_dir, cat_file],  # This code can execute by LLM
    # parallel_tool_calls=True, Enable multi function calling
)

flag_discriminator = Agent(
    model="qwen2.5:14b",
    name="Flag discriminator",
    instructions="You are an agent tailored to extract the flag from the output. ONLY return the flag, nothing else.",
    # functions=[check_flag],  # This code can execute by LLM
)

#  handoff from ctf_agent to flag_discriminator


def transfer_to_flag_discriminator(**kwargs):
    """Transfer flag discriminator. Accepts any keyword arguments but ignores them."""
    return flag_discriminator


ctf_agent.functions.append(transfer_to_flag_discriminator)

messages = [{
    "role": "user",
    "content": "Instructions: " + ctf.get_instructions() +
               "\nChallenge: " + ctf.get_challenges()[challenge] +
               "\nTechniques: " + ctf.get_techniques() +
               "\nExtract the flag and once finished, handoff to the flag discriminator."
}]

# 5. Run the CAI
response = client.run(
    agent=ctf_agent,
    messages=messages,
    debug=True,
    brief=False)
print(response.messages[-1]["content"])
print(f"Time taken: {response.time} seconds")

# 6. Check if the flag is correct
success, flag = check_flag(response.messages[-1]["content"], ctf, challenge)

# 7. Stop the CTF environment
ctf.stop_ctf()
