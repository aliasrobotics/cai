"""
Example demonstrating how to use different NetworkState implementations 
with a state-building agent.
"""

import os
import time
from cai.core import CAI
from cai.state.pydantic import state_agent as pydantic_agent
from cai.state.free import state_agent as plain_agent

# litellm.enable_json_schema_validation = True
# litellm.set_verbose = True # see the raw request made by litellm

def main():
    """Main function demonstrating both NetworkState implementations"""
    
    # Sample chat history - using proper message format
    history = [
        {
            "role": "user", 
            "content": "Scanning target...\n"
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "generic_linux_command",
                        "arguments": "{\"args\":\"-lha\",\"command\":\"ls\"}"
                    },
                    "id": "call_j4yqqa77",
                    "type": "function"
                },
                {
                    "function": {
                        "name": "generic_linux_command", 
                        "arguments": "{\"args\":\"/ -type f -name 'flag.txt' 2\\u003e/dev/null\",\"command\":\"find\"}"
                    },
                    "id": "call_5pps7qt4",
                    "type": "function"
                }
            ]
        },
        {
            "role": "tool",
            "content": "Starting Nmap 7.95 ( https://nmap.org ) at 2025-01-22 10:59 UTC\nNmap scan report for hackableii.cybersecurity_ais_devcontainer_cainet (192.168.2.11)\nHost is up (0.0000020s latency).\nNot shown: 997 closed tcp ports (reset)\nPORT   STATE SERVICE VERSION\n21/tcp open  ftp     ProFTPD\n22/tcp open  ssh     OpenSSH 7.2p2 Ubuntu 4ubuntu2.10 (Ubuntu Linux; protocol 2.0)\n80/tcp open  http    Apache httpd 2.4.18 ((Ubuntu))\nMAC Address: 08:00:27:85:55:86 (PCS Systemtechnik/Oracle VirtualBox virtual NIC)\nService Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel\n\nService detection performed. Please report any incorrect results at https://nmap.org/submit/ .\nNmap done: 1 IP address (1 host up) scanned in 11.29 seconds\n",
            "tool_call_id": "call_j4yqqa77"    
        },
        {
            "role": "tool",
            "content": "total 12K\r\ndrwxr-xr-x 2 root root 4.0K Sep 19 13:49 .\r\ndrwxr-xr-x 1 root root 4.0K Jan 22 11:11 ..\r\n-rw-rw-r-- 1 root root   26 Sep 19 13:42 flag.txt",
            "tool_call_id": "call_5pps7qt4"
        },
        {
            "role": "assistant", 
            "content": "Attempting exploit...\nSuccessfully exploited target through buffer overflow",
        }
    ]

    agents = [
        pydantic_agent,
        plain_agent
    ]

    models = [
        # # closed models
        # "gpt-4o-mini",
        # "gpt-4o",
        # "deepseek/deepseek-chat",
        # "claude-3-5-sonnet-20240620",
        
        # open weight models
        # "qwen2.5:1.5b",
        # "qwen2.5:3b",
        # "qwen2.5:7b",
        "qwen2.5:14b",
        #
        # "qwen2.5:32b",
        # "qwen2.5:72b",
        #
        # "qwen2.5-coder:32b",
        # "qwen2.5:14b-instruct-q8_0",
        # "qwen2.5-coder:32b-instruct-q8_0",
        # "qwen2.5:72b-instruct-q8_0",
        # "qwen2.5:72b-instruct-q8_0",
        # "qwen2.5-coder:72b-instruct-q8_0",
    ]

    # Initialize results dictionary
    results = {}

    for model in models:
        results[model] = {}
        for agent in agents:
            # Skip pydantic agent for deepseek model
            if "deepseek" in model and agent is pydantic_agent:
                continue
                
            if "claude" in model:
                import litellm
                litellm.modify_params = True  # necessary for Anthropic models

            agent.model = model
            cai = CAI()  # reinitialize CAI for each model/agent

            start_time = time.time()
            response = cai.run(
                agent=agent,
                messages=history,
                debug=2
            )
            elapsed_time = time.time() - start_time
            assert response
            results[model][agent.name] = elapsed_time

    # Generate markdown table
    print("\n### State Building Model Performance Results\n")
    print(f"| LLM Model | {agents[0].name} | {agents[1].name} |")
    print("|-------|-------------------|------------|")
    for model in models:
        row = [model]
        for agent in agents:
            if model in results and agent.name in results[model]:
                row.append(f"{results[model][agent.name]:.2f}s")
            else:
                row.append("N/A")
        print(f"| {' | '.join(row)} |")


if __name__ == "__main__":
    os.environ["CAI_TRACING"] = "false"
    main()


