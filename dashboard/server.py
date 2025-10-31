#!/usr/bin/env python3
import http.server
import socketserver
import os

PORT = 8082
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()
    
    def log_message(self, format, *args):
        # Custom logging
        print(f"[Dashboard] {self.address_string()} - {format%args}")

print(f"""
╔════════════════════════════════════════════════════════╗
║     📊 JOB SEARCH TRACKER DASHBOARD                    ║
║                                                        ║
║     Server running at: http://localhost:{PORT}         ║
║     Dashboard ready for use!                           ║
║                                                        ║
║     Press Ctrl+C to stop the server                    ║
╚════════════════════════════════════════════════════════╝
""")

with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n🛑 Dashboard server stopped")
        httpd.shutdown()
