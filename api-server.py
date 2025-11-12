#!/usr/bin/env python3
import http.server
import socketserver
import json
import sqlite3
from urllib.parse import urlparse
import sys
import threading
from datetime import datetime

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

            # SQL PRACTICE TRACKING ENDPOINTS
            elif path == '/api/sql-practice-stats':
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_sessions,
                        SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_count,
                        ROUND(100.0 * SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) / COUNT(*), 1) as accuracy_percentage,
                        SUM(time_spent_minutes) as total_minutes,
                        COUNT(DISTINCT platform) as platforms_used,
                        COUNT(CASE WHEN difficulty = 'Easy' THEN 1 END) as easy_count,
                        COUNT(CASE WHEN difficulty = 'Medium' THEN 1 END) as medium_count,
                        COUNT(CASE WHEN difficulty = 'Hard' THEN 1 END) as hard_count
                    FROM sql_practice_sessions
                """)
                result = dict(cursor.fetchone())
                self.wfile.write(json.dumps(result).encode())

            elif path == '/api/sql-keyword-mastery':
                cursor.execute("SELECT * FROM sql_keyword_mastery")
                results = [dict(row) for row in cursor.fetchall()]
                self.wfile.write(json.dumps(results).encode())

            elif path == '/api/recent-practice':
                cursor.execute("""
                    SELECT *
                    FROM sql_practice_sessions
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                results = [dict(row) for row in cursor.fetchall()]
                self.wfile.write(json.dumps(results).encode())

            elif path == '/api/weekly-summary':
                cursor.execute("SELECT * FROM weekly_practice_summary LIMIT 8")
                results = [dict(row) for row in cursor.fetchall()]
                self.wfile.write(json.dumps(results).encode())

            elif path == '/api/common-mistakes':
                cursor.execute("SELECT * FROM common_practice_mistakes")
                results = [dict(row) for row in cursor.fetchall()]
                self.wfile.write(json.dumps(results).encode())

            # SACRED WORK ENDPOINTS
            elif path == '/api/sacred-work-stats':
                cursor.execute("SELECT * FROM sacred_work_stats")
                result = cursor.fetchone()
                if result:
                    stats = dict(result)
                    # Handle NULL values for empty table
                    if stats.get('total_stones') is None:
                        stats = {
                            'total_stones': 0,
                            'total_minutes': 0,
                            'avg_minutes_per_stone': 0,
                            'first_stone_date': None,
                            'latest_stone_date': None,
                            'total_hours': 0
                        }
                else:
                    stats = {
                        'total_stones': 0,
                        'total_minutes': 0,
                        'avg_minutes_per_stone': 0,
                        'first_stone_date': None,
                        'latest_stone_date': None,
                        'total_hours': 0
                    }
                self.wfile.write(json.dumps(stats).encode())

            elif path == '/api/sacred-work-progress':
                cursor.execute("SELECT * FROM sacred_work_progress ORDER BY stone_number ASC")
                results = [dict(row) for row in cursor.fetchall()]
                self.wfile.write(json.dumps(results).encode())

            elif path == '/api/recent-sacred-work':
                cursor.execute("""
                    SELECT * FROM sacred_work_log
                    ORDER BY date DESC, created_at DESC
                    LIMIT 5
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
        elif self.path == '/api/add-question':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                conn = get_db()
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO interview_questions (
                        opportunity_id, question_text, question_type, difficulty,
                        my_response, ideal_response, my_rating, tags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get('opportunity_id'),
                    data.get('question_text', ''),
                    data.get('question_type', ''),
                    data.get('difficulty', 'Medium'),
                    data.get('my_response', ''),
                    data.get('ideal_response', ''),
                    data.get('my_rating', 3),
                    data.get('tags', '')
                ))

                new_id = cursor.lastrowid

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "message": "Question added successfully",
                    "id": new_id
                }).encode())

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        elif self.path == '/api/add-sacred-work':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                # Validate required fields
                required = ['stone_number', 'stone_title', 'time_spent_minutes', 'what_built']
                missing = [f for f in required if f not in data or not data[f]]
                if missing:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "error": f'Missing required fields: {", ".join(missing)}'
                    }).encode())
                    return

                conn = get_db()
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO sacred_work_log
                    (stone_number, stone_title, time_spent_minutes, what_built,
                     insights, next_stone, felt_sense, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    int(data['stone_number']),
                    data['stone_title'],
                    int(data['time_spent_minutes']),
                    data['what_built'],
                    data.get('insights', ''),
                    data.get('next_stone', ''),
                    data.get('felt_sense', ''),
                    data.get('date', datetime.now().strftime('%Y-%m-%d'))
                ))

                new_id = cursor.lastrowid

                self.send_response(201)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "message": "Sacred stone placed successfully",
                    "id": new_id,
                    "stone_number": data['stone_number']
                }).encode())

            except sqlite3.IntegrityError as e:
                self.send_response(409)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": f"Stone number already exists: {str(e)}"
                }).encode())
            except ValueError as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": f"Invalid data format: {str(e)}"
                }).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": f"Failed to log sacred work: {str(e)}"
                }).encode())
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
║     🚀 JOB TRACKER API SERVER + LEARNING SYSTEM        ║
║                                                        ║
║     Running on: http://localhost:{PORT}                ║
║                                                        ║
║     Job Tracking Endpoints:                            ║
║     GET  /api/metrics                                  ║
║     GET  /api/todays-agenda                            ║
║     GET  /api/pipeline                                 ║
║     POST /api/add-opportunity                          ║
║                                                        ║
║     Learning Endpoints:                                ║
║     GET  /api/learning-gaps                            ║
║     GET  /api/study-priority                           ║
║     GET  /api/recent-questions                         ║
║     POST /api/add-question                             ║
║                                                        ║
║     SQL Practice Endpoints:                            ║
║     GET  /api/sql-practice-stats                       ║
║     GET  /api/sql-keyword-mastery                      ║
║     GET  /api/recent-practice                          ║
║     GET  /api/weekly-summary                           ║
║     GET  /api/common-mistakes                          ║
║                                                        ║
║     Sacred Work Endpoints:           🪨 NEW            ║
║     GET  /api/sacred-work-stats      🪨 NEW            ║
║     GET  /api/sacred-work-progress   🪨 NEW            ║
║     GET  /api/recent-sacred-work     🪨 NEW            ║
║     POST /api/add-sacred-work        🪨 NEW            ║
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
