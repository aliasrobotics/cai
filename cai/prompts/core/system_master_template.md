<%
    # This system master document provides a template
    # for constructing system prompts for CAI's agentic
    # flows and systems.
    #
    # The structure of the prompts include the following
    # sections:
    #
    # 1. Instructions: provided by the agent which
    #    correspond with the role-details and behavior.
    #
    # 2. Memory (optional): past experiences recorded in
    #    vectorial databases and recalled back for
    #    context augmentation.
    #
    # 3. Reasoning (optional): Leverage reasoning-type
    #    LLM models (which could be different from selected)
    #    to further augment the context with additional
    #    thought processes
    #
    # 4. Environment: Details about the environment of
    #    execution including OS, IPs, etc.
    #

    import os
    from cai.util import cli_print_tool_call
    from cai.rag.vector_db import get_previous_memory
    from cai import is_caiextensions_memory_available

    # Get system prompt from agent if provided
    system_prompt = (
        agent.instructions(context_variables)
        if callable(agent.instructions)
        else agent.instructions
    )

    # Get CTF_INSIDE environment variable
    ctf_inside = os.getenv('CTF_INSIDE')
    env_context = os.getenv('CAI_ENV_CONTEXT', 'true').lower()
    # Get memory from vector db if RAG is enabled
    rag_enabled = os.getenv("CAI_MEMORY", "?").lower() in ["episodic", "semantic", "all"]
    memory = ""
    if rag_enabled:
        if os.getenv("CAI_MEMORY", "?").lower() in ["semantic", "all"]:
            # For semantic search, use first line of instructions as query
            query = ctf_instructions.split('\n')[0].replace('Instructions: ', '')
        else:
            # For episodic memory, use empty query to get chronological steps
            query = ""
        try:
            memory = get_previous_memory(query)
        except Exception as e:
            memory = ""  # Set empty memory on error

        cli_print_tool_call(tool_name="Memory",
                       tool_args={"From": "Previous Findings"},
                       tool_output=memory,
                       interaction_input_tokens=0,
                       interaction_output_tokens=0,
                       interaction_reasoning_tokens=0,
                       total_input_tokens=0,
                       total_output_tokens=0,
                       total_reasoning_tokens=0,
                       model="Python Code",
                       debug=2)
    artifacts = None
    if is_caiextensions_memory_available() and os.getenv('CTF_NAME') and os.getenv("CTF_ARTIFACTS"):
        from caiextensions.memory import get_artifacts
        artifacts = get_artifacts(os.getenv('CTF_NAME').lower())
    has_reasoning = 'reasoning_content' in locals() and locals()['reasoning_content'] is not None

%>
${system_prompt}
% if rag_enabled:

<memory>
${memory}
</memory>

Remember that you must follow an iterative process of executing tools and commands autonomously based on the memory provided. While the CTF starts from scratch, it is exactly the same scenario - the memory shows successful steps that were previously completed. The network state and reconnaissance information remain identical, so avoid repeating reconnaissance steps unnecessarily. Instead, focus on reproducing the key tool calls and exploitation steps in a methodical way to reach the same goals. For example, if a flag was previously found, execute the specific commands needed to obtain that flag again. Always use the flag discriminator to validate flags. Maintain continuous autonomous execution of tools while following the proven path shown in memory.
% endif

% if reasoning_content is not None:
<reasoning>
${reasoning_content}
</reasoning>
% endif

% if env_context.lower() == 'true':
<%
    import platform
    import socket
    import os

    from pathlib import Path

    # Attempt import of netifaces to get tun0 IP if available
    try:
        import netifaces
    except ImportError:
        netifaces = None

    # Gather system info
    os_name = platform.system()
    hostname = socket.gethostname()
    ip_addr = socket.gethostbyname(hostname)

    # Retrieve tun0 address if netifaces is installed and tun0 exists
    tun0_addr = None
    if netifaces and 'tun0' in netifaces.interfaces():
        addrs = netifaces.ifaddresses('tun0')
        if netifaces.AF_INET in addrs:
            tun0_addr = addrs[netifaces.AF_INET][0].get('addr', None)

    # Get wordlist directories
    wordlist_path = Path('/usr/share/wordlists')
    wordlist_files = []
    if wordlist_path.exists():
        wordlist_files = [
            f.name for f in wordlist_path.iterdir() if f.is_file()
        ]

    seclists_path = wordlist_path / 'seclists'
    seclist_dirs = []
    if seclists_path.exists():
        seclist_dirs = [
            d.name for d in seclists_path.iterdir() if d.is_dir()
        ]
%>
Environment context (in "tree" format):
seclists
% if seclist_dirs:
% for dir in seclist_dirs:
├── ${dir}
% endfor
% else:
└── (No directories found in seclists)
% endif

- When in doubt, list again.

Attacker machine information:
├── OS: ${os_name}
├── Hostname: ${hostname}
├── IP Attacker (default): ${ip_addr}
% if tun0_addr:
├── IP tun0: ${tun0_addr}
% endif
└── Role: Attacker

% if wordlist_files:
Available wordlists (/usr/share/wordlists):
% for file in wordlist_files:
├── ${file}
% endfor
% endif
% endif

% if artifacts:
Useful information: ${artifacts}
% endif
