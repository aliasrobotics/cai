#!/usr/bin/env python3
import requests
import socket

target_ip = "192.168.2.1"

# Function to make HTTP request
def make_http_request():
    try:
        print(f"[+] Attempting HTTP request to http://{target_ip}")
        response = requests.get(f"http://{target_ip}", timeout=5)
        print(f"[+] Response status code: {response.status_code}")
        print(f"[+] Response headers: {response.headers}")
        print(f"[+] Response content (first 500 chars): {response.text[:500]}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"[-] HTTP request failed: {e}")
        return False

# Function to check if port 80 is open
def check_port_80():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    result = s.connect_ex((target_ip, 80))
    s.close()
    if result == 0:
        print(f"[+] Port 80 is open on {target_ip}")
        return True
    else:
        print(f"[-] Port 80 is closed on {target_ip}")
        return False

# Main execution
print(f"[*] Target IP: {target_ip}")

# First check if port 80 is open
if check_port_80():
    make_http_request()
else:
    # Try a simple ping to see if host is alive
    print(f"[*] Attempting ping to {target_ip}")
    try:
        import subprocess
        result = subprocess.run(['ping', '-c', '1', '-W', '2', target_ip], 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            print(f"[+] Host {target_ip} is reachable (ping successful)")
        else:
            print(f"[-] Host {target_ip} is not responding to ping")
    except Exception as e:
        print(f"[-] Error during ping: {e}")

print("[*] Script execution completed")
