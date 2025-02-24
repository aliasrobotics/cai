<%
    # A template for the user prompt
    # Args:
    #   ctf: CTF object
    #   challenge: Challenge flag name
    #   ip: Target IP address

    import os

    # Get CTF_NAME environment variable
    ctf_name = os.getenv('CTF_NAME', '').lower()

    # Get instructions from CTF
    # NOTE: consider case of no CTF
    #
    ctf_instructions = ctf.get_instructions() if ctf else None

    # Challenge
    # NOTE: consider case of no CTF
    #
    challenge_tip = ctf.get_challenges()[challenge] if challenge else None

    # Get CTF_INSIDE environment variable
    ctf_inside = os.getenv('CTF_INSIDE', 'true').lower()
%>
%if ctf_instructions:
Instructions: ${ctf_instructions}
%endif

%if challenge:
Challenge: ${challenge_tip}
%endif

%if ip:
Target IP: ${ip}
%endif

% if ctf_inside == 'true':
You are INSIDE the target machine in a docker container. Try not to use network commands unless necessary.
% else:
You are OUTSIDE the target machine which is a docker container. You may use network commands like nmap for initial reconnaissance.
%endif
