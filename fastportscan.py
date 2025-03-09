import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

def scan_port(target, port):
    """Scan a single port on the target"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.2)  # 200ms timeout for speed
    
    try:
        result = sock.connect_ex((target, port))
        if result == 0:
            print(f"Port {port} is open")
        sock.close()
    except:
        pass

def main():
    target = "192.168.1.1"
    print(f"Starting ultra fast port scan on {target}")
    start_time = time.time()
    
    # Common ports to scan first (for faster results)
    common_ports = [21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 443, 445, 
                    993, 995, 1723, 3306, 3389, 5900, 8080]
    
    # First scan common ports
    print("Scanning common ports...")
    with ThreadPoolExecutor(max_workers=50) as executor:
        for port in common_ports:
            executor.submit(scan_port, target, port)
    
    # Then scan all other ports
    print("Starting full port scan...")
    with ThreadPoolExecutor(max_workers=500) as executor:
        for port in range(1, 65536):
            if port not in common_ports:
                executor.submit(scan_port, target, port)
    
    elapsed_time = time.time() - start_time
    print(f"Port scan completed in {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    main()
