#!/bin/bash

# ============================================================
# Master Test Runner - Job Application Tracker
# ============================================================
# Runs all test suites and generates comprehensive report
#
# Usage:
#   ./tests/run-all-tests.sh
#
# Features:
# - Runs all test scripts in sequence
# - Captures and aggregates results
# - Generates summary report with pass/fail breakdown
# - Saves detailed log to tests/last-test-run.log
# - Color-coded output for easy reading
# - Returns exit code 0 (all pass) or 1 (any fail)
# ============================================================

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Global counters
TOTAL_SUITES=0
PASSED_SUITES=0
FAILED_SUITES=0
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Array to track failed tests
declare -a FAILED_TEST_DETAILS

# Timestamp for report
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
LOG_FILE="tests/last-test-run.log"

# ============================================================
# Helper Functions
# ============================================================

print_header() {
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║                                                        ║"
    echo "║         🧪  MASTER TEST SUITE RUNNER                  ║"
    echo "║                                                        ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
    echo "Started: $TIMESTAMP"
    echo "Log file: $LOG_FILE"
    echo ""
}

print_section() {
    local title=$1
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${CYAN}${BOLD}$title${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

run_test_suite() {
    local test_name=$1
    local test_script=$2
    local suite_num=$3

    ((TOTAL_SUITES++))

    print_section "[$suite_num/$TOTAL_SUITES_COUNT] Running: $test_name"

    # Check if test script exists
    if [ ! -f "$test_script" ]; then
        echo -e "${RED}❌ ERROR: Test script not found: $test_script${NC}"
        ((FAILED_SUITES++))
        FAILED_TEST_DETAILS+=("$test_name: Script not found")
        return 1
    fi

    # Check if executable
    if [ ! -x "$test_script" ]; then
        echo -e "${YELLOW}⚠️  Warning: Making $test_script executable${NC}"
        chmod +x "$test_script"
    fi

    # Run the test and capture output
    local output_file=$(mktemp)
    local start_time=$(date +%s)

    if bash "$test_script" > "$output_file" 2>&1; then
        local exit_code=0
    else
        local exit_code=$?
    fi

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    # Display output
    cat "$output_file"

    # Parse results based on test script output patterns
    local passed=0
    local failed=0

    # Try to extract pass/fail counts from output
    if grep -q "PASSED:" "$output_file"; then
        passed=$(grep "PASSED:" "$output_file" | grep -o '[0-9]*' | head -1)
        failed=$(grep "FAILED:" "$output_file" | grep -o '[0-9]*' | head -1)
    elif grep -q "Passed:" "$output_file"; then
        passed=$(grep "Passed:" "$output_file" | grep -o '[0-9]*' | head -1)
        failed=$(grep "Failed:" "$output_file" | grep -o '[0-9]*' | head -1)
    elif grep -q "✅ PASS" "$output_file"; then
        passed=$(grep -c "✅ PASS" "$output_file")
        failed=$(grep -c "❌ FAIL" "$output_file")
    elif grep -q "ALL TESTS PASSED" "$output_file"; then
        passed=$(grep -o '[0-9]*/[0-9]*' "$output_file" | cut -d'/' -f1 | tail -1)
        failed=0
    fi

    # Default to exit code if we couldn't parse
    if [ -z "$passed" ] && [ -z "$failed" ]; then
        if [ $exit_code -eq 0 ]; then
            passed=1
            failed=0
        else
            passed=0
            failed=1
        fi
    fi

    # Update global counters
    TOTAL_TESTS=$((TOTAL_TESTS + passed + failed))
    PASSED_TESTS=$((PASSED_TESTS + passed))
    FAILED_TESTS=$((FAILED_TESTS + failed))

    # Summary for this suite
    echo ""
    if [ $failed -eq 0 ] && [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ SUITE PASSED${NC} - $test_name (${passed} tests passed in ${duration}s)"
        ((PASSED_SUITES++))
    else
        echo -e "${RED}❌ SUITE FAILED${NC} - $test_name (${passed} passed, ${failed} failed in ${duration}s)"
        ((FAILED_SUITES++))
        FAILED_TEST_DETAILS+=("$test_name: $failed test(s) failed")

        # Extract specific failed test names if available
        if grep -q "FAIL:" "$output_file"; then
            local failed_tests=$(grep "FAIL:" "$output_file" | head -5)
            FAILED_TEST_DETAILS+=("  └─ $failed_tests")
        fi
    fi

    # Append to log file
    echo "" >> "$LOG_FILE"
    echo "═══════════════════════════════════════════════════════" >> "$LOG_FILE"
    echo "Test Suite: $test_name" >> "$LOG_FILE"
    echo "Script: $test_script" >> "$LOG_FILE"
    echo "Duration: ${duration}s" >> "$LOG_FILE"
    echo "Result: Passed=$passed, Failed=$failed, Exit=$exit_code" >> "$LOG_FILE"
    echo "═══════════════════════════════════════════════════════" >> "$LOG_FILE"
    cat "$output_file" >> "$LOG_FILE"

    # Cleanup
    rm -f "$output_file"

    return $exit_code
}

print_summary() {
    local overall_pass_rate=0
    if [ $TOTAL_TESTS -gt 0 ]; then
        overall_pass_rate=$((PASSED_TESTS * 100 / TOTAL_TESTS))
    fi

    echo ""
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║                                                        ║"
    echo "║               📊  TEST SUMMARY REPORT                  ║"
    echo "║                                                        ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""

    # Suite-level summary
    echo -e "${BOLD}Test Suites:${NC}"
    echo "  Total Suites Run:    $TOTAL_SUITES"
    echo -e "  ${GREEN}Passed:${NC}              $PASSED_SUITES"
    echo -e "  ${RED}Failed:${NC}              $FAILED_SUITES"
    echo ""

    # Test-level summary
    echo -e "${BOLD}Individual Tests:${NC}"
    echo "  Total Tests:         $TOTAL_TESTS"
    echo -e "  ${GREEN}Passed:${NC}              $PASSED_TESTS"
    echo -e "  ${RED}Failed:${NC}              $FAILED_TESTS"
    echo ""

    # Pass rate
    echo -e "${BOLD}Overall Results:${NC}"
    if [ $overall_pass_rate -ge 90 ]; then
        echo -e "  Pass Rate:           ${GREEN}${overall_pass_rate}%${NC} ✨"
    elif [ $overall_pass_rate -ge 70 ]; then
        echo -e "  Pass Rate:           ${YELLOW}${overall_pass_rate}%${NC} ⚠️"
    else
        echo -e "  Pass Rate:           ${RED}${overall_pass_rate}%${NC} ❌"
    fi
    echo ""

    # Failed test details
    if [ $FAILED_SUITES -gt 0 ]; then
        echo -e "${RED}${BOLD}Failed Tests:${NC}"
        for detail in "${FAILED_TEST_DETAILS[@]}"; do
            echo -e "  ${RED}•${NC} $detail"
        done
        echo ""
    fi

    # Final verdict
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if [ $FAILED_SUITES -eq 0 ]; then
        echo -e "${GREEN}${BOLD}✅ ALL TEST SUITES PASSED!${NC}"
        echo ""
        echo "🎉 Your system is working perfectly!"
    else
        echo -e "${RED}${BOLD}❌ SOME TESTS FAILED${NC}"
        echo ""
        echo "📋 Recommendations:"
        echo "  1. Review failed test output above"
        echo "  2. Check detailed log: $LOG_FILE"
        echo "  3. Fix issues and re-run: ./tests/run-all-tests.sh"
        echo "  4. Run individual suite: ./tests/<test-name>.sh"
    fi
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

# ============================================================
# Main Test Execution
# ============================================================

# Initialize log file
{
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║         Test Run Log - Job Application Tracker        ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
    echo "Timestamp: $TIMESTAMP"
    echo "Command: $0 $@"
    echo "User: $(whoami)"
    echo "Working Directory: $(pwd)"
    echo ""
} > "$LOG_FILE"

# Print header
print_header

# Check if services are running
echo "🔍 Pre-flight checks..."
echo ""

# Check API server
if curl -s http://localhost:8081/api/metrics > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} API server running on port 8081"
else
    echo -e "  ${YELLOW}⚠️  Warning: API server not responding on port 8081${NC}"
    echo "     Some tests may fail. Start with: ./start-tracker.sh"
fi

# Check Dashboard
if curl -s http://localhost:8082 > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Dashboard running on port 8082"
else
    echo -e "  ${YELLOW}⚠️  Warning: Dashboard not responding on port 8082${NC}"
fi

# Check Database
if [ -f "data/jobs-tracker.db" ]; then
    echo -e "  ${GREEN}✓${NC} Database file exists"
else
    echo -e "  ${RED}✗${NC} Database file not found: data/jobs-tracker.db"
fi

echo ""
sleep 1

# Define test suites to run
# Note: We use a constant for total count before running
TOTAL_SUITES_COUNT=5

# ============================================================
# Run Test Suites
# ============================================================

# Test 1: Complete System Test
run_test_suite \
    "Complete System Test" \
    "tests/test-complete-system.sh" \
    1

# Test 2: Pipeline Features Test
run_test_suite \
    "Pipeline Features Test" \
    "tests/test-new-pipeline-features.sh" \
    2

# Test 3: Scraped Jobs API Test
run_test_suite \
    "Scraped Jobs API Test" \
    "tests/test-scraped-jobs-api.sh" \
    3

# Test 4: SQL Practice System Test
run_test_suite \
    "SQL Practice System Test" \
    "tests/test-sql-practice-system.sh" \
    4

# Test 5: System Validation Test
run_test_suite \
    "System Validation Test" \
    "tests/validate-system.sh" \
    5

# ============================================================
# Generate Summary Report
# ============================================================

print_summary

# Append summary to log file
{
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║                  SUMMARY REPORT                        ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
    echo "Test Suites: $PASSED_SUITES/$TOTAL_SUITES passed"
    echo "Individual Tests: $PASSED_TESTS/$TOTAL_TESTS passed"
    if [ $TOTAL_TESTS -gt 0 ]; then
        echo "Pass Rate: $((PASSED_TESTS * 100 / TOTAL_TESTS))%"
    fi
    echo ""
    if [ $FAILED_SUITES -gt 0 ]; then
        echo "Failed Suites:"
        for detail in "${FAILED_TEST_DETAILS[@]}"; do
            echo "  • $detail"
        done
    fi
    echo ""
    echo "Completed: $(date '+%Y-%m-%d %H:%M:%S')"
} >> "$LOG_FILE"

# Exit with appropriate code
if [ $FAILED_SUITES -eq 0 ]; then
    exit 0
else
    exit 1
fi
