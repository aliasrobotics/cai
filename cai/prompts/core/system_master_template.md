<%
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
                       debug=False)
    if is_caiextensions_memory_available():
        from caiextensions.memory import get_artifacts
        artifacts = get_artifacts(os.getenv('CTF_NAME').lower())
%>

${system_prompt}

% if ctf_inside is not None:
    % if ctf_inside.lower() == 'true':
You are INSIDE the target machine in a docker container. Try not to use network commands unless necessary.
    % elif ctf_inside.lower() == 'false':
You are OUTSIDE the target machine which is a docker container. You may use network commands like nmap for initial reconnaissance.
    % endif
% endif

% if rag_enabled:
<memory>
${memory}
</memory>

Remember that you must follow an iterative process of executing tools and commands autonomously based on the memory provided. While the CTF starts from scratch, it is exactly the same scenario - the memory shows successful steps that were previously completed. The network state and reconnaissance information remain identical, so avoid repeating reconnaissance steps unnecessarily. Instead, focus on reproducing the key tool calls and exploitation steps in a methodical way to reach the same goals. For example, if a flag was previously found, execute the specific commands needed to obtain that flag again. Always use the flag discriminator to validate flags. Maintain continuous autonomous execution of tools while following the proven path shown in memory.
% endif

% if env_context.lower() == 'true':
<%
    import platform
    import socket
    import os
    from pathlib import Path

    # Get system info
    os_name = platform.system()
    hostname = socket.gethostname()
    ip_addr = socket.gethostbyname(hostname)

    # Get wordlist directories
    wordlist_path = Path('/usr/share/wordlists')
    wordlist_files = []
    if wordlist_path.exists():
        wordlist_files = [f.name for f in wordlist_path.iterdir() if f.is_file()]

    seclists_path = wordlist_path / 'seclists'
    seclist_dirs = []
    if seclists_path.exists():
        seclist_dirs = [d.name for d in seclists_path.iterdir() if d.is_dir()]
%>

Environment context:
- OS: ${os_name}
- IP Attacker: ${ip_addr}
- Role: Attacker

% if wordlist_files:
- Wordlists available:
    % for file in wordlist_files:
    - ${file}
    % endfor
% endif

% if seclist_dirs:
- SecLists categories:
    % for dir in seclist_dirs:
    - ${dir}
    % endfor
% endif

% endif

% if artifacts:
Some useful information: ${artifacts}
% endif
