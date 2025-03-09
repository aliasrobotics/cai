#!/usr/bin/env python3
import requests
import sys

def make_http_request(url, method="GET", timeout=10):
    """
    Make an HTTP request to the specified URL
    
    Args:
        url (str): The URL to make the request to
        method (str): HTTP method (GET, POST, etc.)
        timeout (int): Request timeout in seconds
        
    Returns:
        Response object
    """
    try:
        # Add http:// prefix if not present
        if not url.startswith('http://') and not url.startswith('https://'):
            url = f'http://{url}'
            
        print(f"Making {method} request to: {url}")
        
        if method.upper() == "GET":
            response = requests.get(url, timeout=timeout)
        elif method.upper() == "POST":
            response = requests.post(url, timeout=timeout)
        else:
            print(f"Unsupported method: {method}")
            return None
            
        print(f"Status code: {response.status_code}")
        print("\nHeaders:")
        for key, value in response.headers.items():
            print(f"{key}: {value}")
            
        print("\nResponse body:")
        print(response.text[:1000])  # Print first 1000 chars to avoid overwhelming output
        if len(response.text) > 1000:
            print("... (response truncated)")
            
        return response
        
    except requests.exceptions.ConnectionError:
        print(f"Connection error: Failed to connect to {url}")
    except requests.exceptions.Timeout:
        print(f"Timeout error: Request to {url} timed out after {timeout} seconds")
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    return None

if __name__ == "__main__":
    target = "192.168.2.1"
    
    # If arguments provided, use the first as the target
    if len(sys.argv) > 1:
        target = sys.argv[1]
    
    make_http_request(target)
