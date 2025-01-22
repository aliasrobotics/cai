"""
Example demonstrating how to use different NetworkState implementations 
with a state-building agent.
"""

import json
import os
import time
import litellm
from typing import List, Dict, Any
from cai.core import CAI
from cai.types import Agent
from cai.state.json import NetworkState as JsonNetworkState
from cai.state.pydantic import NetworkState as PydanticNetworkState

# litellm.enable_json_schema_validation = True
# litellm.set_verbose = True # see the raw request made by litellm

def build_state_agent(state_class) -> Agent:
    """Creates an agent that builds network state from chat history"""

    return Agent(
        name="StateBuilder",
        instructions="""
        I am a state building agent that analyzes chat history to 
        construct network state.

        I look for information about ports, services, 
        exploits and build a structured state representation.
        """,
        structured_output_class=state_class,
        # model="qwen2.5:72b-instruct-q8_0"
        # model="gpt-4o"
        # model="deepseek/deepseek-chat"
        # model="claude-3-5-sonnet-20240620"
    )

def main():
    """Main function demonstrating both NetworkState implementations"""
    
    # Sample chat history - using proper message format
    history = [
        {
            "role": "user",
            "content": "Scanning target...\n"
        },
        {
            "role": "tool",
            "content": "Starting Nmap 7.95 ( https://nmap.org ) at 2025-01-22 10:59 UTC\nNmap scan report for hackableii.cybersecurity_ais_devcontainer_cainet (192.168.2.11)\nHost is up (0.0000020s latency).\nNot shown: 997 closed tcp ports (reset)\nPORT   STATE SERVICE VERSION\n21/tcp open  ftp     ProFTPD\n22/tcp open  ssh     OpenSSH 7.2p2 Ubuntu 4ubuntu2.10 (Ubuntu Linux; protocol 2.0)\n80/tcp open  http    Apache httpd 2.4.18 ((Ubuntu))\nMAC Address: 08:00:27:85:55:86 (PCS Systemtechnik/Oracle VirtualBox virtual NIC)\nService Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel\n\nService detection performed. Please report any incorrect results at https://nmap.org/submit/ .\nNmap done: 1 IP address (1 host up) scanned in 11.29 seconds\n",
            "tool_call_id": "call_gdwszmjr"    
        },
        {
            "role": "tool",
            "content": "total 12K\r\ndrwxr-xr-x 2 root root 4.0K Sep 19 13:49 .\r\ndrwxr-xr-x 1 root root 4.0K Jan 22 11:11 ..\r\n-rw-rw-r-- 1 root root   26 Sep 19 13:42 flag.txt",
            "tool_call_id": "call_j4yqqa77"
        },
        {
            "role": "assistant", 
            "content": "Attempting exploit...\nSuccessfully exploited target through buffer overflow",
        }
    ]
    
    cai = CAI()
    
    # Test with JSON NetworkState implementation
    print("\nTesting with JSON NetworkState implementation:")
    json_agent = build_state_agent(JsonNetworkState)
    start_time = time.time()
    json_response = cai.run(
        agent=json_agent,
        messages=history,
        debug=2
    )
    elapsed_time = time.time() - start_time
    print(f"\nJSON state generation took {elapsed_time:.2f} seconds")
    # Parse the string content back into a dict, then dump with indentation
    # json_content = json.loads(json_response.messages[-1]["content"])
    # print(json.dumps(json_content, indent=2))
    
    # Test with Pydantic NetworkState implementation 
    print("\nTesting with Pydantic NetworkState implementation:")
    pydantic_agent = build_state_agent(PydanticNetworkState)
    start_time = time.time()
    pydantic_response = cai.run(
        agent=pydantic_agent,
        messages=history,
        debug=2
    )
    elapsed_time = time.time() - start_time
    print(f"\nPydantic state generation took {elapsed_time:.2f} seconds")
    # Parse the string content back into a dict, then dump with indentation
    # json_content = json.loads(pydantic_response.messages[-1]["content"])
    # print(json.dumps(json_content, indent=2))

    # Test with Plain Free-form Text NetworkState
    print("\nTesting with Plain Free-form Text NetworkState implementation:")
    plain_agent = Agent(
        name="Plain Free-form Text to NetworkState",
        instructions="""
        I am a network state building agent that analyzes chat history to 
        construct network state in Plain Free-form Text that represents 
        the current state of the network.
        """
    )
    start_time = time.time()
    pydantic_response = cai.run(
        agent=pydantic_agent,
        messages=history,
        debug=2
    )
    elapsed_time = time.time() - start_time
    print(f"\nPydantic state generation took {elapsed_time:.2f} seconds")


if __name__ == "__main__":
    os.environ["CAI_TRACING"] = "false"
    main()
