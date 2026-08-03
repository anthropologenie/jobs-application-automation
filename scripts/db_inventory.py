#!/usr/bin/env python3
"""
db_inventory.py

One-off, stdlib-only inventory script for the JobOps SQLite database.
Dumps schema (tables, views, indexes, triggers, column-level PRAGMA info),
row counts, full contents of prep-relevant tables, all pre-built views, and
basic distributions on interview_questions into a single timestamped
Markdown report.

This is a diagnostic utility, not a pipeline component. No dependencies
beyond the Python standard library. Safe to re-run at any time; each run
produces a new timestamped file rather than overwriting prior runs.

Scope note: this script answers "what exists in the database?" (structure
+ raw contents). It deliberately does NOT do analysis, scoring, or
recommendation — that belongs in a separate future utility (e.g.
corpus_profile.py) so this script keeps a single responsibility.

Usage:
    python scripts/db_inventory.py [path_to_db]

If no path is given, defaults to DEFAULT_DB_PATH below (repo-relative).
Works regardless of the current working directory the script is launched
from, since all paths are resolved relative to this file's location.
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

DEFAULT_DB_PATH = REPO_ROOT / "data" / "jobs-tracker.db"
OUTPUT_DIR = REPO_ROOT / "docs" / "inventory"

# Tables whose full contents are relevant to interview/study prep planning.
# Everything else only gets a row count + schema, not a full dump, to keep
# the report focused and short.
PREP_RELEVANT_TABLES = [
    "interview_questions",
    "sql_practice_sessions",
    "study_topics",
    "learning_sessions",
]

# Every view currently defined in the database, per the earlier schema scan.
VIEWS_TO_DUMP = [
    "learning_gaps",
    "study_priority",
    "common_practice_mistakes",
    "sql_keyword_mastery",
    "practice_progress_by_difficulty",
    "weekly_practice_summary",
    "todays_agenda",
    "active_pipeline",
    "sacred_work_progress",
    "sacred_work_stats",
]

INVENTORY_SCRIPT_VERSION = "1.1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_all_table_names(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name;"
    )
    return [row[0] for row in cur.fetchall()]


def get_all_view_names(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'view' ORDER BY name;"
    )
    return [row[0] for row in cur.fetchall()]


def rows_to_markdown_table(cur: sqlite3.Cursor, rows: list[tuple]) -> str:
    if not rows:
        return "_No rows returned._\n"
    headers = [desc[0] for desc in cur.description]
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        cells = []
        for val in row:
            if val is None:
                cells.append("")
            else:
                cell = str(val).replace("|", "\\|").replace("\n", " ")
                cells.append(cell)
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def section(title: str, level: int = 2) -> str:
    return f"\n{'#' * level} {title}\n"


def safe_query(conn: sqlite3.Connection, query: str):
    try:
        cur = conn.execute(query)
        rows = cur.fetchall()
        return cur, rows, None
    except sqlite3.Error as e:
        return None, [], str(e)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH

    if not db_path.exists():
        print(f"Database file not found: {db_path}")
        print("Pass the correct path as an argument: python scripts/db_inventory.py path/to/jobops.db")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    run_start = datetime.now()
    timestamp = run_start.strftime("%Y%m%d_%H%M%S")
    report_lines: list[str] = []

    table_names = get_all_table_names(conn)
    view_names = get_all_view_names(conn)

    # --- Inventory Summary (top of report) ---
    report_lines.append("# JobOps Database Inventory\n")
    report_lines.append(section("Inventory Summary"))
    report_lines.append(
        f"- **Generated:** {run_start.isoformat(timespec='seconds')}\n"
        f"- **Database:** `{db_path}`\n"
        f"- **Inventory script version:** {INVENTORY_SCRIPT_VERSION}\n"
        f"- **Python version:** {sys.version.split()[0]}\n"
        f"- **Tables found:** {len(table_names)}\n"
        f"- **Views found:** {len(view_names)}\n"
    )
    report_lines.append(
        "\nOne-off diagnostic inventory. Not a pipeline artifact, not tied to any "
        "milestone. Answers *what exists*, not *what it means* — analysis and "
        "scoring belong in a separate future utility. Regenerate by re-running "
        "`db_inventory.py`; each run produces a new timestamped file rather than "
        "overwriting prior snapshots.\n"
    )

    # 1. Schema — Tables (CREATE statement + PRAGMA column info)
    report_lines.append(section("1. Schema — Tables"))
    cur, rows, err = safe_query(
        conn,
        "SELECT name, sql FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name;",
    )
    if err:
        report_lines.append(f"Error: {err}\n")
    else:
        for name, sql in rows:
            report_lines.append(f"\n**`{name}`**\n```sql\n{sql}\n```\n")
            pragma_cur, pragma_rows, pragma_err = safe_query(
                conn, f"PRAGMA table_info(\"{name}\");"
            )
            if pragma_err:
                report_lines.append(f"PRAGMA error: {pragma_err}\n")
            else:
                report_lines.append("Columns (`PRAGMA table_info`):\n\n")
                report_lines.append(rows_to_markdown_table(pragma_cur, pragma_rows))

    # 2. Schema — Views
    report_lines.append(section("2. Schema — Views"))
    cur, rows, err = safe_query(
        conn, "SELECT name, sql FROM sqlite_master WHERE type='view' ORDER BY name;"
    )
    if err:
        report_lines.append(f"Error: {err}\n")
    else:
        for name, sql in rows:
            report_lines.append(f"\n**`{name}`**\n```sql\n{sql}\n```\n")

    # 3. Schema — Indexes
    report_lines.append(section("3. Schema — Indexes"))
    cur, rows, err = safe_query(
        conn,
        "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' ORDER BY tbl_name, name;",
    )
    if err:
        report_lines.append(f"Error: {err}\n")
    else:
        report_lines.append(rows_to_markdown_table(cur, rows))

    # 4. Schema — Triggers
    report_lines.append(section("4. Schema — Triggers"))
    cur, rows, err = safe_query(
        conn,
        "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='trigger' ORDER BY tbl_name, name;",
    )
    if err:
        report_lines.append(f"Error: {err}\n")
    else:
        for name, tbl_name, sql in rows:
            report_lines.append(f"\n**`{name}`** (on `{tbl_name}`)\n```sql\n{sql}\n```\n")

    # 5. Row counts for every table
    report_lines.append(section("5. Row Counts (All Tables)"))
    count_rows = []
    for t in table_names:
        cur, rows, err = safe_query(conn, f"SELECT COUNT(*) FROM \"{t}\";")
        count_rows.append((t, f"ERROR: {err}" if err else rows[0][0]))
    report_lines.append("| Table | Row Count |\n|---|---|\n")
    for t, c in count_rows:
        report_lines.append(f"| {t} | {c} |\n")

    # 6. Full contents of prep-relevant tables
    report_lines.append(section("6. Full Contents — Prep-Relevant Tables"))
    for t in PREP_RELEVANT_TABLES:
        report_lines.append(section(f"`{t}`", level=3))
        if t not in table_names:
            report_lines.append(f"_Table `{t}` not found in this database._\n")
            continue
        cur, rows, err = safe_query(conn, f"SELECT * FROM \"{t}\" ORDER BY rowid;")
        report_lines.append(
            rows_to_markdown_table(cur, rows) if not err else f"Error: {err}\n"
        )

    # 7. Every pre-built view, dumped as-is
    report_lines.append(section("7. View Contents (As-Is, No Interpretation)"))
    for v in VIEWS_TO_DUMP:
        report_lines.append(section(f"`{v}`", level=3))
        if v not in view_names:
            report_lines.append(f"_View `{v}` not found in this database._\n")
            continue
        cur, rows, err = safe_query(conn, f"SELECT * FROM \"{v}\";")
        report_lines.append(
            rows_to_markdown_table(cur, rows) if not err else f"Error: {err}\n"
        )

    unexpected_views = [v for v in view_names if v not in VIEWS_TO_DUMP]
    if unexpected_views:
        report_lines.append(section("7a. Views Found But Not In Expected List", level=3))
        report_lines.append(
            "_These views exist in the database but weren't in this script's "
            "VIEWS_TO_DUMP list — schema may have changed since this script was written._\n\n"
        )
        for v in unexpected_views:
            report_lines.append(f"- `{v}`\n")

    # 8. Distributions on interview_questions
    report_lines.append(section("8. Distributions — `interview_questions`"))
    if "interview_questions" in table_names:
        report_lines.append(section("By Category", level=3))
        cur, rows, err = safe_query(
            conn,
            "SELECT category, COUNT(*) AS n FROM interview_questions "
            "GROUP BY category ORDER BY n DESC;",
        )
        report_lines.append(rows_to_markdown_table(cur, rows) if not err else f"Error: {err}\n")

        report_lines.append(section("By Category + Subcategory", level=3))
        cur, rows, err = safe_query(
            conn,
            "SELECT category, subcategory, COUNT(*) AS n FROM interview_questions "
            "GROUP BY category, subcategory ORDER BY n DESC;",
        )
        report_lines.append(rows_to_markdown_table(cur, rows) if not err else f"Error: {err}\n")

        report_lines.append(section("By Difficulty", level=3))
        cur, rows, err = safe_query(
            conn,
            "SELECT difficulty, COUNT(*) AS n FROM interview_questions "
            "GROUP BY difficulty ORDER BY n DESC;",
        )
        report_lines.append(rows_to_markdown_table(cur, rows) if not err else f"Error: {err}\n")

        report_lines.append(section("Answer Field Completeness", level=3))
        cur, rows, err = safe_query(
            conn,
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN your_answer IS NOT NULL AND TRIM(your_answer) != '' THEN 1 ELSE 0 END) AS has_your_answer, "
            "SUM(CASE WHEN correct_answer IS NOT NULL AND TRIM(correct_answer) != '' THEN 1 ELSE 0 END) AS has_correct_answer "
            "FROM interview_questions;",
        )
        report_lines.append(rows_to_markdown_table(cur, rows) if not err else f"Error: {err}\n")
    else:
        report_lines.append("_Table `interview_questions` not found._\n")

    conn.close()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"db_inventory_{timestamp}.md"
    output_path.write_text("".join(report_lines), encoding="utf-8")

    run_end = datetime.now()
    duration = (run_end - run_start).total_seconds()

    print("=" * 44)
    print("JobOps Database Inventory")
    print("=" * 44)
    print(f"\nDatabase\n--------\n{db_path}")
    print(f"\nTables\n------\n{len(table_names)}")
    print(f"\nViews\n-----\n{len(view_names)}")
    print(f"\nDuration\n--------\n{duration:.2f}s")
    print(f"\nReport\n------\n{output_path}")
    print("\nStatus\n------\nSUCCESS")


if __name__ == "__main__":
    main()