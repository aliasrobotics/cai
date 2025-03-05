"""
Tests for state building agents.
"""

import os
import time
import pytest
from cai.core import CAI
from cai.state.pydantic import state_agent as pydantic_agent
from cai.state.free import state_agent as plain_agent

# Sample chat history used in tests
HISTORY = [
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

# Test models
MODELS = [
    # Open weight models
    # "qwen2.5:1.5b",
    "qwen2.5:14b",

    ## Closed models 
    # "gpt-4o-mini",
    #"gpt-4o",
    # "deepseek/deepseek-chat",
    # "claude-3-5-sonnet-20240620"
]

@pytest.fixture(autouse=True)
def setup_env():
    """Setup test environment"""
    os.environ["CAI_TRACING"] = "false"

# exclude deepseek model
# 
# NOTE: not operational Pydantic agent for deepseek model
@pytest.mark.parametrize("model", [m for m in MODELS if "deepseek" not in m])
def test_pydantic_state_agent(model):
    """Test the pydantic state agent's ability to build state"""
    if "claude" in model:
        import litellm
        litellm.modify_params = True  # necessary for Anthropic models
        
    cai = CAI()
    pydantic_agent.model = model
    
    response = cai.run(
        agent=pydantic_agent,
        messages=HISTORY,
        debug=2
    )
    
    assert response is not None
    # Add more specific assertions about the response structure/content if needed

@pytest.mark.parametrize("model", MODELS)
def test_plain_state_agent(model):
    """Test the plain state agent's ability to build state"""
    if "claude" in model:
        import litellm
        litellm.modify_params = True  # necessary for Anthropic models
        
    cai = CAI()
    plain_agent.model = model
    
    response = cai.run(
        agent=plain_agent,
        messages=HISTORY,
        debug=2
    )
    
    assert response is not None
    # Add more specific assertions about the response structure/content if needed
