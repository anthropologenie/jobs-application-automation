#!/usr/bin/env python3
import re

# Read the current API server
with open('api-server.py', 'r') as f:
    content = f.read()

# The new endpoint code
new_endpoint = '''        elif self.path == '/api/add-question':
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
'''

# Find the location to insert (right after the add-opportunity else block)
pattern = r"(        else:\s+self\.send_response\(404\)\s+self\.send_header\('Content-Type', 'application/json'\)\s+self\.send_header\('Access-Control-Allow-Origin', '\*'\)\s+self\.end_headers\(\)\s+self\.wfile\.write\(json\.dumps\(\{\"error\": \"Not found\"\}\)\.encode\(\)\))"

# Check if endpoint already exists
if '/api/add-question' in content:
    print("✅ Endpoint already exists in api-server.py")
else:
    # Insert the new endpoint before the final else block
    content = re.sub(pattern, new_endpoint + r'\n\1', content)
    
    # Write back
    with open('api-server.py', 'w') as f:
        f.write(content)
    
    print("✅ Successfully injected /api/add-question endpoint!")
    print("🔄 Restart your API server for changes to take effect")
