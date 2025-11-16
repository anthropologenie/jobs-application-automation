#!/bin/bash
# View scraped jobs from database
# Usage: ./view_scraped_jobs.sh [limit]

DB_PATH="data/jobs-tracker.db"
LIMIT=${1:-10}

echo "========================================================================"
echo "📊 SCRAPED JOBS - TOP $LIMIT MATCHES"
echo "========================================================================"
echo ""

sqlite3 -column -header "$DB_PATH" << EOF
SELECT
    CAST(match_score AS INTEGER) || '%' as Score,
    classification as Type,
    company as Company,
    job_title as Role,
    location as Location
FROM scraped_jobs
ORDER BY match_score DESC
LIMIT $LIMIT;
EOF

echo ""
echo "========================================================================"
echo "📈 CLASSIFICATION SUMMARY"
echo "========================================================================"
echo ""

sqlite3 -column -header "$DB_PATH" << EOF
SELECT
    classification as Classification,
    COUNT(*) as Count,
    CAST(AVG(match_score) AS INTEGER) || '%' as AvgScore
FROM scraped_jobs
GROUP BY classification
ORDER BY
    CASE classification
        WHEN 'EXCELLENT' THEN 1
        WHEN 'HIGH_FIT' THEN 2
        WHEN 'MEDIUM_FIT' THEN 3
        WHEN 'LOW_FIT' THEN 4
        WHEN 'NO_FIT' THEN 5
    END;
EOF

echo ""
echo "========================================================================"
echo "🔍 FILTER OPTIONS"
echo "========================================================================"
echo ""
echo "View by classification:"
echo "  sqlite3 $DB_PATH \"SELECT * FROM scraped_jobs WHERE classification='LOW_FIT' ORDER BY match_score DESC;\""
echo ""
echo "View with matched skills:"
echo "  sqlite3 $DB_PATH \"SELECT company, job_title, match_score, matched_skills FROM scraped_jobs ORDER BY match_score DESC LIMIT 5;\""
echo ""
echo "Search by company:"
echo "  sqlite3 $DB_PATH \"SELECT * FROM scraped_jobs WHERE company LIKE '%Google%' ORDER BY match_score DESC;\""
echo ""
echo "Recent scrapes:"
echo "  sqlite3 $DB_PATH \"SELECT * FROM scraped_jobs ORDER BY scraped_at DESC LIMIT 10;\""
echo ""
