#!/usr/bin/env python3
import http.server
import socketserver
import json
import sqlite3
from urllib.parse import urlparse
import sys
import threading

PORT = 8081
DB_PATH = './data/jobs-tracker.db'

# Thread-local storage for database connections
thread_local = threading.local()

def get_db():
    """Get thread-local database connection"""
    if not hasattr(thread_local, 'conn') or thread_local.conn is None:
        thread_local.conn = sqlite3.connect(
            DB_PATH,
            timeout=30.0,
            isolation_level=None,  # Autocommit mode
            check_same_thread=False
        )
        thread_local.conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency
        thread_local.conn.execute("PRAGMA journal_mode=WAL")
    return thread_local.conn

class APIHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        try:
            conn = get_db()
            cursor = conn.cursor()

            if path == '/api/metrics':
                cursor.execute("""
                    SELECT
                        (SELECT COUNT(*) FROM opportunities WHERE status NOT IN ('Rejected', 'Declined', 'Ghosted', 'Accepted')) as active_count,
                        (SELECT COUNT(*) FROM interactions WHERE date BETWEEN DATE('now') AND DATE('now', '+7 days') AND type = 'Interview') as interview_count,
                        (SELECT COUNT(*) FROM opportunities WHERE is_remote = 1 AND status NOT IN ('Rejected', 'Declined', 'Ghosted', 'Accepted')) as remote_count,
                        (SELECT COUNT(*) FROM opportunities WHERE priority = 'High' AND status NOT IN ('Rejected', 'Declined', 'Ghosted', 'Accepted')) as priority_count
                """)
                result = dict(cursor.fetchone())
                self.wfile.write(json.dumps(result).encode())

            elif path == '/api/todays-agenda':
                cursor.execute("""
                    SELECT i.id, i.type, i.date, i.time, i.meet_link,
                           o.company, o.role, o.status, i.participants, i.summary
                    FROM interactions i
                    JOIN opportunities o ON i.opportunity_id = o.id
                    WHERE i.date BETWEEN DATE('now') AND DATE('now', '+7 days')
                      AND i.type = 'Interview'
                    ORDER BY i.date, i.time ASC
                """)
                results = [dict(row) for row in cursor.fetchall()]
                self.wfile.write(json.dumps(results).encode())

            elif path == '/api/pipeline':
                cursor.execute("""
                    SELECT o.id, o.company, o.role, o.status, o.is_remote, o.priority,
                           o.tech_stack, o.salary_range, o.recruiter_name, o.recruiter_phone,
                           o.notes, o.discovered_date, o.last_interaction_date, o.updated_at
                    FROM opportunities o
                    WHERE o.status NOT IN ('Rejected', 'Declined', 'Ghosted', 'Accepted')
                    ORDER BY
                        CASE o.priority
                            WHEN 'High' THEN 1
                            WHEN 'Medium' THEN 2
                            WHEN 'Low' THEN 3
                        END,
                        o.updated_at DESC
                    LIMIT 50
                """)
                results = [dict(row) for row in cursor.fetchall()]
                self.wfile.write(json.dumps(results).encode())
            
            # NEW LEARNING ENDPOINTS (PROPERLY PLACED INSIDE do_GET)
            elif path == '/api/learning-gaps':
                cursor.execute("SELECT * FROM learning_gaps")
                results = [dict(row) for row in cursor.fetchall()]
                self.wfile.write(json.dumps(results).encode())

            elif path == '/api/study-priority':
                cursor.execute("SELECT * FROM study_priority")
                results = [dict(row) for row in cursor.fetchall()]
                self.wfile.write(json.dumps(results).encode())

            elif path == '/api/recent-questions':
                cursor.execute("""
                    SELECT iq.*, o.company
                    FROM interview_questions iq
                    LEFT JOIN opportunities o ON iq.opportunity_id = o.id
                    ORDER BY iq.created_at DESC
                    LIMIT 20
                """)
                results = [dict(row) for row in cursor.fetchall()]
                self.wfile.write(json.dumps(results).encode())

            else:
                self.wfile.write(json.dumps({"error": "Not found"}).encode())

        except Exception as e:
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_POST(self):
        if self.path == '/api/add-opportunity':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                conn = get_db()
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO opportunities (
                        company, role, source, is_remote, tech_stack,
                        recruiter_phone, notes, status, priority
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get('company', ''),
                    data.get('role', ''),
                    data.get('source', 'Other'),
                    1 if data.get('is_remote') else 0,
                    data.get('tech_stack', ''),
                    data.get('recruiter_phone', ''),
                    data.get('notes', ''),
                    data.get('status', 'Lead'),
                    data.get('priority', 'Medium')
                ))

                new_id = cursor.lastrowid

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "message": "Opportunity added successfully",
                    "id": new_id
                }).encode())

            except json.JSONDecodeError as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Invalid JSON: {str(e)}"}).encode())
            except sqlite3.Error as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Database error: {str(e)}"}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        sys.stdout.write(f"[API] {self.address_string()} - {format%args}\n")

if __name__ == "__main__":
    print(f"""
╔════════════════════════════════════════════════════════╗
║     🚀 JOB TRACKER API SERVER (ENHANCED)               ║
║                                                        ║
║     Running on: http://localhost:{PORT}                ║
║                                                        ║
║     Endpoints:                                         ║
║     GET  /api/metrics                                  ║
║     GET  /api/todays-agenda                            ║
║     GET  /api/pipeline                                 ║
║     GET  /api/learning-gaps          ⭐ NEW            ║
║     GET  /api/study-priority         ⭐ NEW            ║
║     GET  /api/recent-questions       ⭐ NEW            ║
║     POST /api/add-opportunity                          ║
║                                                        ║
║     Press Ctrl+C to stop                               ║
╚════════════════════════════════════════════════════════╝
""")

    with socketserver.TCPServer(("", PORT), APIHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n🛑 API server stopped")
            httpd.shutdown()
