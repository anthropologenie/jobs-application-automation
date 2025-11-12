#!/bin/bash
# Quick script to view your weekly SQL practice summary

clear
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "          📚 YOUR SQL PRACTICE SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

sqlite3 data/jobs-tracker.db < queries/weekly-practice-summary.sql

echo ""
echo "🔗 View dashboard: http://localhost:8081 (after starting api-server.py)"
echo "📝 Log practice: ./log-sql-practice.py"
