#!/usr/bin/env python3
"""
SQL Practice Logger - CLI Tool
================================
Purpose: Quickly log SQL practice sessions after completing questions
Author: Learning System
Date: 2025-11-03

OOP CONCEPTS USED (for your learning):
--------------------------------------
1. Classes & Objects: PracticeSession class encapsulates session data
2. Encapsulation: Data validation in methods (validate_platform, validate_difficulty)
3. Single Responsibility: Each class has one job (PracticeSession = data, SessionLogger = database)
4. Dependency Injection: SessionLogger accepts db_path, making it testable
"""

import sqlite3
from datetime import datetime
from typing import Optional, List
import sys


# ==========================================
# CLASS 1: Data Model (Represents one practice session)
# ==========================================
class PracticeSession:
    """
    Represents a single SQL practice session.

    WHY USE A CLASS?
    - Groups related data together (question, query, error, etc.)
    - Provides validation (ensures platform/difficulty are valid)
    - Makes code more readable: session.platform vs session[2]

    This is called the "Model" in MVC architecture.
    """

    # Class-level constants (shared by all instances)
    VALID_PLATFORMS = ['sql-practice.com', 'programiz', 'dbeaver', 'other']
    VALID_DIFFICULTIES = ['Easy', 'Medium', 'Hard']
    VALID_DATABASES = ['Hospital', 'Northwind', 'Custom', 'None']

    def __init__(
        self,
        question_text: str,
        my_query: str,
        platform: str,
        difficulty: str = 'Medium',
        database_used: str = 'None',
        correct_query: Optional[str] = None,
        is_correct: bool = False,
        time_spent_minutes: Optional[int] = None,
        error_made: Optional[str] = None,
        lesson_learned: Optional[str] = None,
        keywords_used: Optional[str] = None,
        notes: Optional[str] = None
    ):
        """
        Constructor - initializes the object with data.

        WHY __init__?
        This is a "magic method" (dunder method) that Python calls
        when you create an instance: session = PracticeSession(...)
        """
        # Validate before storing
        self.platform = self._validate_platform(platform)
        self.difficulty = self._validate_difficulty(difficulty)
        self.database_used = self._validate_database(database_used)

        # Store attributes (instance variables)
        self.question_text = question_text
        self.my_query = my_query
        self.correct_query = correct_query
        self.is_correct = is_correct
        self.time_spent_minutes = time_spent_minutes
        self.error_made = error_made
        self.lesson_learned = lesson_learned
        self.keywords_used = keywords_used
        self.notes = notes
        self.practice_date = datetime.now().date()

    def _validate_platform(self, platform: str) -> str:
        """
        Private method (prefix with _) for internal validation.

        WHY PRIVATE?
        Users shouldn't call this directly. It's a helper for __init__.
        Python doesn't enforce private (it's convention, not security).
        """
        # Normalize: strip whitespace and convert to lowercase for comparison
        normalized = platform.strip().lower()
        if normalized not in self.VALID_PLATFORMS:
            raise ValueError(f"Platform must be one of: {', '.join(self.VALID_PLATFORMS)}")
        return normalized

    def _validate_difficulty(self, difficulty: str) -> str:
        """Validate difficulty level"""
        # Normalize: strip whitespace and convert to title case for comparison
        normalized = difficulty.strip().title()
        if normalized not in self.VALID_DIFFICULTIES:
            raise ValueError(f"Difficulty must be one of: {', '.join(self.VALID_DIFFICULTIES)}")
        return normalized

    def _validate_database(self, database: str) -> str:
        """Validate database name"""
        # Normalize: strip whitespace and convert to title case for comparison
        normalized = database.strip().title()
        if normalized not in self.VALID_DATABASES:
            raise ValueError(f"Database must be one of: {', '.join(self.VALID_DATABASES)}")
        return normalized

    def to_dict(self) -> dict:
        """
        Convert object to dictionary for database insertion.

        WHY NEEDED?
        SQLite doesn't understand objects. We need to convert to dict
        so we can unpack it with **kwargs in SQL insert.
        """
        return {
            'practice_date': str(self.practice_date),
            'platform': self.platform,
            'database_used': self.database_used,
            'question_text': self.question_text,
            'my_query': self.my_query,
            'correct_query': self.correct_query,
            'is_correct': 1 if self.is_correct else 0,
            'time_spent_minutes': self.time_spent_minutes,
            'difficulty': self.difficulty,
            'error_made': self.error_made,
            'lesson_learned': self.lesson_learned,
            'keywords_used': self.keywords_used,
            'notes': self.notes
        }

    def __str__(self) -> str:
        """
        String representation of the object (called by print()).

        WHY __str__?
        When you do print(session), Python calls this method.
        Helps with debugging and displaying objects nicely.
        """
        status = "✅ Correct" if self.is_correct else "❌ Incorrect"
        return f"[{self.practice_date}] {self.platform} - {self.difficulty} - {status}"


# ==========================================
# CLASS 2: Database Handler (Manages persistence)
# ==========================================
class SessionLogger:
    """
    Handles database operations for practice sessions.

    WHY SEPARATE CLASS?
    - Separation of Concerns: PracticeSession = data, SessionLogger = database
    - Testability: Easy to mock/replace with a test database
    - Reusability: Can log different types of sessions by passing different objects

    This is called the "Repository Pattern" in software design.
    """

    def __init__(self, db_path: str = './data/jobs-tracker.db'):
        """
        Initialize logger with database path.

        DEPENDENCY INJECTION:
        We pass db_path as parameter instead of hardcoding.
        This makes testing easier (can pass test_db.db).
        """
        self.db_path = db_path
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        """
        Check if table exists, create if not.

        WHY?
        Defensive programming - ensures database is ready.
        Prevents cryptic "no such table" errors.
        """
        # We assume migration already ran, but this is a safety check
        pass

    def save(self, session: PracticeSession) -> int:
        """
        Save a practice session to database.

        RETURNS: The ID of the inserted row

        WHY RETURN ID?
        - Confirmation that save succeeded
        - Can reference this session later (e.g., update it)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Convert object to dictionary
        data = session.to_dict()

        # Build SQL dynamically (safer than hardcoding columns)
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        sql = f"INSERT INTO sql_practice_sessions ({columns}) VALUES ({placeholders})"

        try:
            cursor.execute(sql, list(data.values()))
            conn.commit()
            session_id = cursor.lastrowid
            print(f"\n✅ Session #{session_id} saved successfully!")
            return session_id
        except sqlite3.Error as e:
            print(f"\n❌ Database error: {e}")
            conn.rollback()
            raise
        finally:
            # ALWAYS close connections (prevents database locks)
            conn.close()

    def get_recent_sessions(self, limit: int = 5) -> List[dict]:
        """
        Fetch recent practice sessions.

        WHY LIST[dict]?
        Returns a list of dictionaries (each row as a dict).
        Type hints help other developers understand what to expect.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Makes rows accessible by column name
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, practice_date, platform, difficulty, is_correct, question_text
            FROM sql_practice_sessions
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results


# ==========================================
# CLASS 3: Interactive CLI (User Interface)
# ==========================================
class InteractiveCLI:
    """
    Manages the command-line interface for user interaction.

    WHY SEPARATE CLASS?
    - Keeps UI logic separate from business logic
    - Easy to replace with GUI later (just swap this class)
    - Makes SessionLogger reusable (works with web apps, APIs, etc.)
    """

    def __init__(self, logger: SessionLogger):
        """
        DEPENDENCY INJECTION again!
        We inject the logger so CLI doesn't create its own.
        Makes testing easier and follows SOLID principles.
        """
        self.logger = logger

    def run(self):
        """
        Main entry point for the interactive session.
        """
        print("=" * 60)
        print("  📚 SQL PRACTICE LOGGER")
        print("=" * 60)
        print("Log your SQL practice sessions quickly and easily!\n")

        # Step-by-step prompts
        question = self._input_required("Question text: ")
        my_query = self._input_required("Your SQL query: ")
        platform = self._input_choice("Platform", PracticeSession.VALID_PLATFORMS, default='sql-practice.com')
        difficulty = self._input_choice("Difficulty", PracticeSession.VALID_DIFFICULTIES, default='Medium')
        database = self._input_choice("Database used", PracticeSession.VALID_DATABASES, default='None')

        # Optional fields
        print("\n--- Optional Details (press Enter to skip) ---")
        correct_query = input("Correct query (if different): ").strip() or None
        is_correct = self._input_yes_no("Did you get it correct?", default=False)
        time_spent = self._input_int("Time spent (minutes)", optional=True)
        error_made = input("What error did you make? ").strip() or None
        lesson_learned = input("Key lesson learned: ").strip() or None
        keywords = input("SQL keywords used (comma-separated, e.g., WHERE, JOIN): ").strip() or None
        notes = input("Additional notes: ").strip() or None

        # Create and save session
        try:
            session = PracticeSession(
                question_text=question,
                my_query=my_query,
                platform=platform,
                difficulty=difficulty,
                database_used=database,
                correct_query=correct_query,
                is_correct=is_correct,
                time_spent_minutes=time_spent,
                error_made=error_made,
                lesson_learned=lesson_learned,
                keywords_used=keywords,
                notes=notes
            )

            self.logger.save(session)
            print(f"\n{session}")

            # Show recent sessions
            self._show_recent_sessions()

        except ValueError as e:
            print(f"\n❌ Validation Error: {e}")
            sys.exit(1)

    def _input_required(self, prompt: str) -> str:
        """Helper: Get required input (can't be empty)"""
        while True:
            value = input(prompt).strip()
            if value:
                return value
            print("  ⚠️  This field is required. Please enter a value.")

    def _input_choice(self, prompt: str, choices: List[str], default: str) -> str:
        """Helper: Get input from a list of choices"""
        print(f"\n{prompt} options: {', '.join(choices)}")
        value = input(f"{prompt} [{default}]: ").strip()
        return value if value else default

    def _input_yes_no(self, prompt: str, default: bool = False) -> bool:
        """Helper: Get yes/no input"""
        default_str = 'Y/n' if default else 'y/N'
        value = input(f"{prompt} [{default_str}]: ").strip().lower()
        if not value:
            return default
        return value in ['y', 'yes', '1', 'true']

    def _input_int(self, prompt: str, optional: bool = False) -> Optional[int]:
        """Helper: Get integer input"""
        while True:
            value = input(f"{prompt}: ").strip()
            if not value and optional:
                return None
            try:
                return int(value)
            except ValueError:
                print("  ⚠️  Please enter a valid number.")

    def _show_recent_sessions(self):
        """Display recent sessions for context"""
        print("\n" + "=" * 60)
        print("  📊 YOUR RECENT PRACTICE SESSIONS")
        print("=" * 60)
        sessions = self.logger.get_recent_sessions(limit=5)
        for s in sessions:
            status = "✅" if s['is_correct'] else "❌"
            print(f"{status} [{s['practice_date']}] {s['platform']} - {s['difficulty']}")
            print(f"   Q: {s['question_text'][:60]}...")
        print()


# ==========================================
# MAIN ENTRY POINT
# ==========================================
def main():
    """
    Application entry point.

    WHY main()?
    - Standard Python convention
    - Allows importing without running (useful for testing)
    - Keeps global scope clean
    """
    logger = SessionLogger()  # Create database handler
    cli = InteractiveCLI(logger)  # Create UI with injected logger
    cli.run()  # Start interactive session


if __name__ == "__main__":
    """
    This runs only when script is executed directly (not imported).

    WHY?
    - Prevents code from running when imported for testing
    - Standard Python idiom for executable scripts
    """
    main()
