<%
    import os

    # Get CTF_NAME environment variable
    ctf_name = os.getenv('CTF_NAME', '').lower()
    # Get CTF_IP environment variable
    ctf_ip = os.getenv('CTF_IP', '192.168.2.100').lower()
    # Get instructions from CTF
    ctf_instructions = ctf.get_instructions()
    # Get CTF_CHALLENGE environment variable
    challenge = os.getenv('CTF_CHALLENGE', '').lower()
    ctf_challenges = None
    if challenge:    
        ctf_challenges = ctf.get_challenges()[challenge]
    # Get CTF_INSIDE environment variable
    ctf_inside = os.getenv('CTF_INSIDE', 'true').lower()
%>


%if ctf_name:
CTF_NAME: ${ctf_name}
%endif
%if ctf_instructions:
Instructions: ${ctf_instructions}
%endif
%if ctf_challenges:
Challenge: ${ctf_challenges}
%endif


% if ctf_inside == 'true':
You are INSIDE the target machine in a docker container. Try not to use network commands unless necessary.
% else:
You are OUTSIDE the target machine which is a docker container. You may use network commands like nmap for initial reconnaissance.
%if ctf_ip:
Target IP: ${ctf_ip}
%endif
%endif


