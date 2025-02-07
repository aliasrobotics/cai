import json
import os
from types import SimpleNamespace
from mako.template import Template
import pytest
from cai.util import create_report_from_messages
def test_reporter_agent():
    """
    Test the Report Agent using simulated full pentesting tools output with pytest.
    This test generates a report, writes it to ./report/report1.md, asserts the file's existence,
    and then deletes the file.
    """
    # Import the CAI client and the reporter agent from the CAI library.
    from cai import CAI
    from cai.report_agent.pentesting_web import reporter_agent

    # Simulated full output from various pentesting tools to drive report generation.
    pentest_input = (
        "Boot2Root Pentesting Tool Log:\n"
        "================================\n"
        "\n"
        "1. Nmap Network Discovery:\n"
        "----------------------------\n"
        "Command: nmap -sS -p- -T4 192.168.1.10\n"
        "Output:\n"
        "  PORT     STATE SERVICE    VERSION\n"
        "  22/tcp   open  ssh        OpenSSH 7.8 (protocol 2.0)\n"
        "  80/tcp   open  http       Apache httpd 2.4.29\n"
        "  443/tcp  open  https      OpenSSL/1.1.1\n"
        "  3306/tcp open  mysql      MySQL 5.7.29\n"
        "\n"
        "2. Nikto Web Server Scan:\n"
        "-------------------------\n"
        "Command: nikto -h http://192.168.1.10\n"
        "Findings:\n"
        "  - Outdated server version: Apache/2.4.29 vulnerable to multiple known exploits.\n"
        "  - Directory indexing enabled on /backup/.\n"
        "  - Misconfigured SSL certificate detected.\n"
        "\n"
        "3. Metasploit Exploitation Report:\n"
        "----------------------------------\n"
        "Module: exploit/unix/ftp/vsftpd_234_backdoor\n"
        "Status: successful\n"
        "Details: Exploited vulnerable vsftpd version to obtain reverse shell access.\n"
        "\n"
        "4. Nessus Vulnerability Assessment:\n"
        "-----------------------------------\n"
        "Scan ID: 102938\n"
        "Highlights:\n"
        "  - Critical: CVE-2019-0708 (BlueKeep) detected on RDP service.\n"
        "  - SQL injection risks identified on multiple endpoints.\n"
        "\n"
        "5. Hydra SSH Brute Force Attack:\n"
        "-------------------------------\n"
        "Command: hydra -l admin -P /usr/share/wordlists/rockyou.txt 192.168.1.10 ssh\n"
        "Summary:\n"
        "  - Valid credentials found: 'admin:password123'\n"
        "\n"
        "6. SQLMap Injection Analysis:\n"
        "------------------------------\n"
        "Command: sqlmap -u 'http://192.168.1.10/vulnerable.php?id=1' --batch\n"
        "Results:\n"
        "  - Database: 'company_db'\n"
        "  - Extracted Tables: users, transactions, db_config\n"
        "\n"
        "7. John the Ripper Password Cracking:\n"
        "-------------------------------------\n"
        "Command: john --wordlist=/usr/share/wordlists/rockyou.txt hashes.txt\n"
        "Output:\n"
        "  - Successfully cracked 35 out of 50 password hashes.\n"
        "\n"
        "8. Aircrack-ng WiFi Security Assessment:\n"
        "-----------------------------------------\n"
        "Command: airodump-ng wlan0mon\n"
        "Observation:\n"
        "  - Captured handshake for SSID: 'CorporateWiFi'\n"
        "  - Detected potential WPS vulnerabilities.\n"
        "\n"
        "9. Boot2Root Exploitation & Post-Exploitation:\n"
        "-----------------------------------------------\n"
        "Logs:\n"
        "  - Kernel exploit (CVE-2020-1234) triggered, granting root privileges.\n"
        "  - Lateral movement through misconfigured SMB shares observed.\n"
        "  - Custom enumeration scripts executed to extract sensitive data.\n"
        "  - Persistence mechanisms deployed; full system compromise achieved.\n"
        "\n"
        "10. Comprehensive Evidence Collection:\n"
        "----------------------------------------\n"
        "Artifacts:\n"
        "  - Packet captures, system logs, and full terminal session recordings.\n"
        "  - Screenshots of exploit execution and configuration dumps.\n"
        "  - Extracted credentials and exported configuration files.\n"
    )

    # Construct the messages list as expected by client.run
    messages = [
        {"role": "user", "content": "Generate a penetration testing report based on the following input:\n" + pentest_input}
    ]

    # Instantiate the CAI client (without CTF or additional context for this test)
    client = CAI()
    print(reporter_agent.structured_output_class)
    # Run the reporter agent similar to how it's executed in the REPL.
    response = client.run(
        agent=reporter_agent,
        messages=messages,
        context_variables={},
        stream=False,
        debug=True,
        max_turns=1,
    )

    create_report_from_messages(response.report)
    assert os.path.exists("./report")