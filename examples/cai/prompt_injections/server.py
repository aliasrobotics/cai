from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import urllib.parse
import os

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse query parameters if any
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)
        
        # Log the request details
        print(f"\nReceived GET request:")
        print(f"Path: {parsed_path.path}")
        print(f"Query Parameters: {query_params}")
        print(f"Headers: {self.headers}")
        
        try:
            # Read content from index.html
            with open('index.html', 'r', encoding='utf-8') as file:
                index_content = file.read()
                
            # Send index.html content as response
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(index_content.encode('utf-8'))
        except FileNotFoundError:
            # Handle case where index.html is not found
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Error: index.html not found')
        except Exception as e:
            # Handle other potential errors
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f'Error: {str(e)}'.encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            # Try to parse JSON data if possible
            data = json.loads(post_data.decode('utf-8'))
        except json.JSONDecodeError:
            # If not JSON, treat as raw string
            data = post_data.decode('utf-8')
        
        # Log the request details
        print(f"\nReceived POST request:")
        print(f"Path: {self.path}")
        print(f"Headers: {self.headers}")
        print(f"Body: {data}")
        
        # Send response
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Request received')

def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f"Starting server on port {port}...")
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()
