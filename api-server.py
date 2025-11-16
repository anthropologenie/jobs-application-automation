#!/usr/bin/env python3
import http.server
import socketserver
import json
import sqlite3
from urllib.parse import urlparse, parse_qs
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
                self._send_json_response(result)

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
                self._send_json_response(results)

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
                self._send_json_response(results)

            elif path == '/api/archived-pipeline':
                cursor.execute("""
                    SELECT o.id, o.company, o.role, o.status, o.is_remote, o.priority,
                           o.tech_stack, o.salary_range, o.recruiter_name, o.recruiter_phone,
                           o.notes, o.discovered_date, o.last_interaction_date, o.updated_at
                    FROM opportunities o
                    WHERE o.status IN ('Rejected', 'Declined', 'Ghosted', 'Accepted')
                    ORDER BY o.updated_at DESC
                    LIMIT 50
                """)
                results = [dict(row) for row in cursor.fetchall()]
                self._send_json_response(results)

            # NEW LEARNING ENDPOINTS (PROPERLY PLACED INSIDE do_GET)
            elif path == '/api/learning-gaps':
                cursor.execute("SELECT * FROM learning_gaps")
                results = [dict(row) for row in cursor.fetchall()]
                self._send_json_response(results)

            elif path == '/api/study-priority':
                cursor.execute("SELECT * FROM study_priority")
                results = [dict(row) for row in cursor.fetchall()]
                self._send_json_response(results)

            elif path == '/api/recent-questions':
                cursor.execute("""
                    SELECT iq.*, o.company
                    FROM interview_questions iq
                    LEFT JOIN opportunities o ON iq.opportunity_id = o.id
                    ORDER BY iq.created_at DESC
                    LIMIT 20
                """)
                results = [dict(row) for row in cursor.fetchall()]
                self._send_json_response(results)

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
                self._send_json_response(result)

            elif path == '/api/sql-keyword-mastery':
                cursor.execute("SELECT * FROM sql_keyword_mastery")
                results = [dict(row) for row in cursor.fetchall()]
                self._send_json_response(results)

            elif path == '/api/recent-practice':
                cursor.execute("""
                    SELECT *
                    FROM sql_practice_sessions
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                results = [dict(row) for row in cursor.fetchall()]
                self._send_json_response(results)

            elif path == '/api/weekly-summary':
                cursor.execute("SELECT * FROM weekly_practice_summary LIMIT 8")
                results = [dict(row) for row in cursor.fetchall()]
                self._send_json_response(results)

            elif path == '/api/common-mistakes':
                cursor.execute("SELECT * FROM common_practice_mistakes")
                results = [dict(row) for row in cursor.fetchall()]
                self._send_json_response(results)

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
                self._send_json_response(stats)

            elif path == '/api/sacred-work-progress':
                cursor.execute("SELECT * FROM sacred_work_progress ORDER BY stone_number ASC")
                results = [dict(row) for row in cursor.fetchall()]
                self._send_json_response(results)

            elif path == '/api/recent-sacred-work':
                cursor.execute("""
                    SELECT * FROM sacred_work_log
                    ORDER BY date DESC, created_at DESC
                    LIMIT 5
                """)
                results = [dict(row) for row in cursor.fetchall()]
                self._send_json_response(results)

            # JOB SOURCES ENDPOINT
            elif path == '/api/sources':
                cursor.execute("""
                    SELECT id, source_name, is_default
                    FROM job_sources
                    ORDER BY is_default DESC, source_name ASC
                """)
                results = [dict(row) for row in cursor.fetchall()]
                self._send_json_response(results)

            # SCRAPED JOBS ENDPOINTS
            elif path == '/api/scraped-jobs/stats':
                self._handle_scraped_jobs_stats()
                return  # _handle_scraped_jobs_stats sends its own response

            elif self.path.startswith('/api/scraped-jobs'):
                query_components = parse_qs(urlparse(self.path).query)
                self._handle_scraped_jobs(query_components)
                return  # _handle_scraped_jobs sends its own response

            else:
                self._send_json_response({"error": "Not found"})

        except Exception as e:
            self._send_json_response({"error": str(e)})

    def do_POST(self):
        if self.path == '/api/add-opportunity':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                conn = get_db()
                cursor = conn.cursor()

                # Smart parsing of recruiter_contact field
                recruiter_contact = data.get('recruiter_contact', '')
                recruiter_phone = ''
                recruiter_email = ''

                if recruiter_contact:
                    if '@' in recruiter_contact:
                        recruiter_email = recruiter_contact
                    else:
                        recruiter_phone = recruiter_contact

                cursor.execute("""
                    INSERT INTO opportunities (
                        company, role, source, is_remote, tech_stack,
                        recruiter_phone, recruiter_email, notes, status, priority
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get('company', ''),
                    data.get('role', ''),
                    data.get('source', 'Other'),
                    1 if data.get('is_remote') else 0,
                    data.get('tech_stack', ''),
                    recruiter_phone,
                    recruiter_email,
                    data.get('notes', ''),
                    data.get('status', 'Lead'),
                    data.get('priority', 'Medium')
                ))

                new_id = cursor.lastrowid

                self._send_json_response({
                    "success": True,
                    "message": "Opportunity added successfully",
                    "id": new_id
                })

            except json.JSONDecodeError as e:
                self._send_json_response({"error": f"Invalid JSON: {str(e)}"}, 400)
            except sqlite3.Error as e:
                self._send_json_response({"error": f"Database error: {str(e)}"}, 500)
            except Exception as e:
                self._send_json_response({"error": str(e)}, 500)
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

                self._send_json_response({
                    "success": True,
                    "message": "Question added successfully",
                    "id": new_id
                })

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self._send_json_response({"error": str(e)})
        elif self.path == '/api/add-sacred-work':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                # Validate required fields
                required = ['stone_number', 'stone_title', 'time_spent_minutes', 'what_built']
                missing = [f for f in required if f not in data or not data[f]]
                if missing:
                    self._send_json_response({
                        "error": f'Missing required fields: {", ".join(missing)}'
                    }, 400)
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

                self._send_json_response({
                    "success": True,
                    "message": "Sacred stone placed successfully",
                    "id": new_id,
                    "stone_number": data['stone_number']
                }, 201)

            except sqlite3.IntegrityError as e:
                self._send_json_response({
                    "error": f"Stone number already exists: {str(e)}"
                }, 409)
            except ValueError as e:
                self._send_json_response({
                    "error": f"Invalid data format: {str(e)}"
                }, 400)
            except Exception as e:
                self._send_json_response({
                    "error": f"Failed to log sacred work: {str(e)}"
                }, 500)
        elif self.path == '/api/add-source':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                source_name = data.get('source_name', '').strip()

                if not source_name:
                    self._send_json_response({
                        "error": "Source name is required"
                    }, 400)
                    return

                conn = get_db()
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO job_sources (source_name, is_default)
                    VALUES (?, 0)
                """, (source_name,))

                new_id = cursor.lastrowid

                self._send_json_response({
                    "success": True,
                    "message": "Source added successfully",
                    "id": new_id,
                    "source_name": source_name
                }, 201)

            except sqlite3.IntegrityError:
                self._send_json_response({
                    "error": f"Source '{source_name}' already exists"
                }, 409)
            except Exception as e:
                self._send_json_response({
                    "error": f"Failed to add source: {str(e)}"
                }, 500)
        else:
            self._send_json_response({"error": "Not found"}, 404)

    def do_PATCH(self):
        # Extract opportunity ID from path
        if self.path.startswith('/api/update-opportunity/'):
            try:
                # Extract ID from path like /api/update-opportunity/5
                opp_id = self.path.split('/')[-1]

                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                conn = get_db()
                cursor = conn.cursor()

                # Build dynamic UPDATE query based on provided fields
                update_fields = []
                update_values = []

                if 'status' in data:
                    update_fields.append('status = ?')
                    update_values.append(data['status'])

                if 'is_remote' in data:
                    update_fields.append('is_remote = ?')
                    update_values.append(1 if data['is_remote'] else 0)

                if 'notes' in data:
                    update_fields.append('notes = ?')
                    update_values.append(data['notes'])

                if 'priority' in data:
                    update_fields.append('priority = ?')
                    update_values.append(data['priority'])

                if not update_fields:
                    self._send_json_response({
                        "error": "No valid fields to update"
                    }, 400)
                    return

                # Always update updated_at timestamp
                update_fields.append('updated_at = CURRENT_TIMESTAMP')
                update_values.append(opp_id)  # For WHERE clause

                query = f"""
                    UPDATE opportunities
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                """

                cursor.execute(query, update_values)

                if cursor.rowcount == 0:
                    self._send_json_response({
                        "error": f"Opportunity {opp_id} not found"
                    }, 404)
                    return

                self._send_json_response({
                    "success": True,
                    "message": "Opportunity updated successfully",
                    "id": int(opp_id),
                    "updated_fields": list(data.keys())
                })

            except ValueError as e:
                self._send_json_response({
                    "error": f"Invalid opportunity ID: {str(e)}"
                }, 400)
            except Exception as e:
                self._send_json_response({
                    "error": f"Failed to update opportunity: {str(e)}"
                }, 500)
        else:
            self._send_json_response({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _send_json_response(self, data, status_code=200):
        """Helper method to send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _handle_scraped_jobs(self, params):
        """Get scored jobs from scraper with filtering"""
        try:
            # Parse query parameters
            min_score = float(params.get('min_score', [70])[0])
            limit = int(params.get('limit', [50])[0])
            classification = params.get('classification', [None])[0]
            source = params.get('source', [None])[0]

            # Build query
            query = '''
                SELECT
                    id, external_id, source, job_title, company, job_url,
                    location, tags, salary_range, posted_date,
                    match_score, classification, matched_skills, matched_domains,
                    red_flags, recommendation, scraped_at, imported_to_opportunities,
                    description
                FROM scraped_jobs
                WHERE match_score >= ?
            '''

            query_params = [min_score]

            # Add classification filter if provided
            if classification:
                query += ' AND classification = ?'
                query_params.append(classification)

            # Add source filter if provided
            if source:
                query += ' AND source = ?'
                query_params.append(source)

            # Order and limit
            query += ' ORDER BY match_score DESC, scraped_at DESC LIMIT ?'
            query_params.append(limit)

            # Execute query
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(query, query_params)

            # Format results
            jobs = []
            for row in cursor.fetchall():
                jobs.append({
                    'id': row[0],
                    'external_id': row[1],
                    'source': row[2],
                    'job_title': row[3],
                    'company': row[4],
                    'job_url': row[5],
                    'location': row[6],
                    'tags': row[7],
                    'salary_range': row[8],
                    'posted_date': row[9],
                    'match_score': round(row[10], 1),
                    'classification': row[11],
                    'matched_skills': json.loads(row[12]) if row[12] else [],
                    'matched_domains': json.loads(row[13]) if row[13] else [],
                    'red_flags': json.loads(row[14]) if row[14] else [],
                    'recommendation': row[15],
                    'scraped_at': row[16],
                    'imported': bool(row[17]),
                    'description': row[18][:200] + '...' if row[18] and len(row[18]) > 200 else row[18]
                })

            # Send response
            self._send_json_response({
                'success': True,
                'jobs': jobs,
                'count': len(jobs),
                'filters_applied': {
                    'min_score': min_score,
                    'classification': classification,
                    'source': source,
                    'limit': limit
                }
            })

        except Exception as e:
            self._send_json_response({
                'success': False,
                'error': str(e)
            }, 500)

    def _handle_scraped_jobs_stats(self):
        """Get statistics about scraped jobs"""
        try:
            conn = get_db()
            cursor = conn.cursor()

            # Get overall stats
            cursor.execute('''
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN match_score >= 85 THEN 1 END) as excellent,
                    COUNT(CASE WHEN match_score >= 75 AND match_score < 85 THEN 1 END) as high_fit,
                    COUNT(CASE WHEN match_score >= 65 AND match_score < 75 THEN 1 END) as medium_fit,
                    COUNT(CASE WHEN match_score >= 40 AND match_score < 65 THEN 1 END) as low_fit,
                    COUNT(CASE WHEN match_score < 40 THEN 1 END) as no_fit,
                    ROUND(AVG(match_score), 1) as avg_score,
                    MAX(scraped_at) as last_scrape,
                    COUNT(CASE WHEN imported_to_opportunities = 1 THEN 1 END) as imported_count
                FROM scraped_jobs
            ''')

            stats_row = cursor.fetchone()

            # Get source breakdown
            cursor.execute('''
                SELECT source, COUNT(*) as count, ROUND(AVG(match_score), 1) as avg_score
                FROM scraped_jobs
                GROUP BY source
                ORDER BY count DESC
            ''')

            sources = []
            for row in cursor.fetchall():
                sources.append({
                    'source': row[0],
                    'count': row[1],
                    'avg_score': row[2]
                })

            # Format response
            self._send_json_response({
                'success': True,
                'stats': {
                    'total_jobs': stats_row[0],
                    'excellent': stats_row[1],
                    'high_fit': stats_row[2],
                    'medium_fit': stats_row[3],
                    'low_fit': stats_row[4],
                    'no_fit': stats_row[5],
                    'avg_score': stats_row[6],
                    'last_scrape': stats_row[7],
                    'imported_count': stats_row[8]
                },
                'sources': sources
            })

        except Exception as e:
            self._send_json_response({
                'success': False,
                'error': str(e)
            }, 500)

    def log_message(self, format, *args):
        sys.stdout.write(f"[API] {self.address_string()} - {format%args}\n")

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

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
║     Sacred Work Endpoints:                             ║
║     GET  /api/sacred-work-stats                        ║
║     GET  /api/sacred-work-progress                     ║
║     GET  /api/recent-sacred-work                       ║
║     POST /api/add-sacred-work                          ║
║                                                        ║
║     Scraped Jobs Endpoints:          🔍 NEW            ║
║     GET  /api/scraped-jobs           🔍 NEW            ║
║     GET  /api/scraped-jobs/stats     🔍 NEW            ║
║                                                        ║
║     Press Ctrl+C to stop                               ║
╚════════════════════════════════════════════════════════╝
""")

    with ReusableTCPServer(("", PORT), APIHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n🛑 API server stopped")
            httpd.shutdown()
