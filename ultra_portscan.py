#!/usr/bin/env python3
import socket
import concurrent.futures
import time

def scan_port(target, port):
    """Scan a single port on the target"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)  # 500ms timeout
    result = sock.connect_ex((target, port))
    sock.close()
    if result == 0:
        return port
    return None

def main():
    target = "192.168.1.1"
    start_time = time.time()
    print(f"Starting ultra fast port scan on {target}")
    
    # List to store open ports
    open_ports = []
    
    # Use ThreadPoolExecutor for concurrent scanning
    with concurrent.futures.ThreadPoolExecutor(max_workers=500) as executor:
        # Create a list of futures
        futures = [executor.submit(scan_port, target, port) for port in range(1, 65536)]
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(futures):
            port = future.result()
            if port:
                open_ports.append(port)
                print(f"{port}/tcp open")
    
    # Sort and display all open ports
    open_ports.sort()
    print("\nScan summary:")
    if open_ports:
        print("Open ports:", ", ".join(map(str, open_ports)))
    else:
        print("No open ports found")
    
    print(f"Scan completed in {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    main()
