#!/usr/bin/env python3
import requests
import socket

def make_http_request():
    """Make HTTP request to the target IP"""
    try:
        response = requests.get('http://192.168.2.1', timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {response.headers}")
        print(f"Content: {response.text[:500]}...")  # Print first 500 chars
    except requests.exceptions.RequestException as e:
        print(f"HTTP request failed: {e}")

def make_socket_request():
    """Make a basic socket connection to check if host is up"""
    common_ports = [80, 443, 22, 21, 8080]
    print("Checking common ports:")
    for port in common_ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('192.168.2.1', port))
        if result == 0:
            print(f"Port {port} is open")
        else:
            print(f"Port {port} is closed or filtered")
        sock.close()

if __name__ == "__main__":
    print("Making requests to 192.168.2.1...")
    make_socket_request()
    print("\nAttempting HTTP request:")
    make_http_request()
