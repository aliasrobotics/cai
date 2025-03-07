"""
Advanced Boot2Root CTF Framework with CLI, Code Interpreter and Analysis Modes
"""
import sys
from cai import is_pentestperf_available
from cai.core import CAI, Agent
from cai.agents.patterns.boot2root import thought_agent
if is_pentestperf_available():
    import pentestperf as ptt    
else:
    print("PentestPerf is not available. Skipping.")
    sys.exit(1)

client = CAI()

# Init CTF environment
ctf = ptt.ctf(
    "hackableII",
    subnet="192.168.2.0/24",
    container_name="hackableII",
    ip_address="192.168.2.11"
)
ctf.start_ctf()

messages = [{
    "role": "user",
    "content": f"""CTF description: Name HackableII Target: {ctf.get_ip()},
    this is a boot2root CTF challenge
    ignore HTML files
    ITERATE UNTIL YOU FIND ROOT FLAG"""
}]

thought_response = client.run(
    agent=thought_agent,
    messages=messages,
    debug=2)
    
ctf.stop_ctf()
