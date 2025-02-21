<%
    import os
    from cai.util import cli_print_tool_call
    from cai.rag.vector_db import get_previous_memory

    # Get system prompt from agent if provided

    system_prompt = (
        agent.instructions(context_variables)
        if callable(agent.instructions)
        else agent.instructions
    )

    # Get CTF_INSIDE environment variable
    ctf_inside = os.getenv('CTF_INSIDE')

    # Get memory from vector db if RAG is enabled
    rag_enabled = os.getenv("CTF_RAG_MEMORY", "false").lower() == "true"
    memory = ""
    if rag_enabled:
        if os.getenv('AGNOSTIC_MEMORY', 'false').lower() == 'true':
            query = ctf_instructions.split('\n')[0].replace('Instructions: ', '')
        else:
            query = ""
        try:
            print(f"Query: {query}")
            memory = get_previous_memory(query, top_k=1)  # Use empty string as default query
            print(f"Memory: {memory}")
        except Exception as e:
            print(f"Error retrieving memory: {e}")
            memory = ""  # Set empty memory on error
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
