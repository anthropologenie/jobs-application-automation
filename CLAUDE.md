# Job Application Tracker & Learning System

## Project Overview
Personal job application tracker with integrated learning management system. Built to track interviews, analyze performance gaps, and generate personalized practice questions for SQL and Python mastery.

## Current Status
- **Database:** SQLite with 9 opportunities, 8 interview questions, 5 study topics
- **API:** Python HTTP server (port 8081) with 8 endpoints
- **Frontend:** HTML/JS learning dashboard
- **Weak Areas:** Data Warehouse (1.0/5), SQL dates (2.0/5), Python OOP (2.3/5)

## My Learning Goals
1. **SQL Mastery:** Window functions, complex joins, query optimization
2. **Python Proficiency:** Pytest, automation, ETL scripting
3. **Interview Prep:** Build confidence in explaining concepts clearly

## How Claude Code Should Help Me

### 1. Generate Personalized Practice Questions
- Analyze my `interview_questions` table
- Check `learning_gaps` view to see weak areas
- Generate 5 progressively harder SQL questions targeting my gaps
- Create Python coding challenges based on my interview performance

### 2. Code Review & Learning
- Review my SQL queries and explain optimization opportunities
- Suggest improvements to my Python code with explanations
- Help me understand WHY, not just WHAT - teach the logic

### 3. SWOT Analysis
- Query my database to analyze strengths/weaknesses
- Generate actionable study plan based on upcoming interviews
- Identify patterns in questions asked by companies

### 4. Build Practice Systems
- Create SQL quiz generator
- Build Python test automation suite
- Add features to learning dashboard

## Important Rules
- **Teach, don't just solve:** Always explain the reasoning
- **Use my actual data:** Query my database for context
- **Progressive difficulty:** Start with basics, build complexity
- **Real interview scenarios:** Base questions on actual interview patterns

## Database Schema Reference
Key tables:
- `interview_questions` - stores questions asked, my rating, difficulty
- `study_topics` - tracks what I'm learning with priorities
- `learning_gaps` - view showing my weak areas by topic
- `opportunities` - companies I'm interviewing with

## Commands I Can Use
- "Analyze my weak areas and generate 5 practice SQL questions"
- "Review my api-server.py and suggest improvements"
- "Create a SWOT analysis based on my interview data"
- "Generate a Python pytest suite for my database"
- "Build a SQL quiz system that adapts to my performance"

## Files to Focus On
- `data/jobs-tracker.db` - my interview and learning data
- `api-server.py` - backend API server
- `learning-dashboard.html` - frontend UI
- `test-complete-system.sh` - system validation script
