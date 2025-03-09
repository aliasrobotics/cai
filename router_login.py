import requests
from urllib.parse import urljoin
import re

router_url = "http://192.168.1.1/"
login_url = urljoin(router_url, "login.cgi")

# Common credentials for Movistar routers
credentials = [
    {"username": "admin", "password": "admin"},
    {"username": "admin", "password": "1234"},
    {"username": "1234", "password": "1234"},
    {"username": "admin", "password": ""},
    {"username": "root", "password": "admin"},
    {"username": "root", "password": "root"},
    {"username": "user", "password": "user"},
]

# Get the login page first to get any tokens or cookies
session = requests.Session()
try:
    response = session.get(router_url)
    print(f"Initial page status code: {response.status_code}")
    
    # Extract CSRF token if present
    csrf_token = None
    csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    if csrf_match:
        csrf_token = csrf_match.group(1)
        print(f"Found CSRF token: {csrf_token}")
    
    # Try each credential
    for cred in credentials:
        print(f"\nTrying credentials: {cred['username']} / {cred['password']}")
        
        # Prepare login data
        login_data = {
            "loginUsername": cred["username"],
            "Password": cred["password"],
        }
        
        # Add CSRF token if found
        if csrf_token:
            login_data["csrf_token"] = csrf_token
        
        # Try to login
        login_response = session.post(login_url, data=login_data, allow_redirects=True)
        print(f"Login response status code: {login_response.status_code}")
        
        # Check for successful login indicators
        success_indicators = ["logout", "dashboard", "admin", "configuration", "setup"]
        failure_indicators = ["incorrect", "invalid", "failed", "error", "retry"]
        
        if any(indicator in login_response.text.lower() for indicator in success_indicators):
            print("Login appears successful!")
            print(f"Working credentials: {cred['username']} / {cred['password']}")
            break
        elif any(indicator in login_response.text.lower() for indicator in failure_indicators):
            print("Login failed.")
        else:
            print("Login result unclear. Check response:")
            print(login_response.text[:200] + "..." if len(login_response.text) > 200 else login_response.text)

except Exception as e:
    print(f"Error: {e}")
