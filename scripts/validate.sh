#!/bin/bash
# =============================================================================
# Code Standards Validation Script
# =============================================================================
# Usage: ./scripts/validate.sh [directory] [--fix]
#
# Arguments:
#   directory   Target directory to validate (default: current directory)
#   --fix       Apply automatic fixes (formatting only)
#
# Exit codes:
#   0 - All checks passed
#   1 - Format violations found (Critical for CI)
#   2 - clang-tidy violations found
#   3 - Both format and tidy violations found
#
# Examples:
#   ./scripts/validate.sh                    # Check current directory
#   ./scripts/validate.sh src/               # Check src/ directory
#   ./scripts/validate.sh src/ --fix         # Auto-fix formatting in src/
#   ./scripts/validate.sh --fix              # Auto-fix formatting in current dir
# =============================================================================

set -e

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# Colors for terminal output
RED='\033[0;31m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Find script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Parse arguments
TARGET_DIR="."
FIX_MODE=false

for arg in "$@"; do
    case $arg in
        --fix)
            FIX_MODE=true
            ;;
        *)
            if [[ -d "$arg" ]]; then
                TARGET_DIR="$arg"
            fi
            ;;
    esac
done

# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------

print_header() {
    echo ""
    echo -e "${BOLD}${BLUE}======================================================${NC}"
    echo -e "${BOLD}${BLUE}  $1${NC}"
    echo -e "${BOLD}${BLUE}======================================================${NC}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${BOLD}--- $1 ---${NC}"
    echo ""
}

print_pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
}

print_fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
}

print_warn() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
}

print_info() {
    echo -e "${BLUE}ℹ INFO${NC}: $1"
}

# Number of parallel jobs (defaults to CPU count, falls back to 4)
JOBS="$(nproc 2>/dev/null || echo 4)"

# Per-file clang-format worker (runs in parallel via xargs). Records failures
# by appending to $FORMAT_FAIL_FILE so the parent can tally them afterwards.
format_worker() {
    local file="$1"
    if [ "$FIX_MODE" = "true" ]; then
        # Apply formatting fixes
        if clang-format -i --style=file:"$PROJECT_ROOT/.clang-format" "$file" 2>/dev/null || \
           clang-format -i "$file" 2>/dev/null; then
            print_pass "Formatted: $file"
        else
            print_fail "Could not format: $file"
            echo "$file" >> "$FORMAT_FAIL_FILE"
        fi
    else
        # Check only (dry run)
        if clang-format --dry-run --Werror --style=file:"$PROJECT_ROOT/.clang-format" "$file" 2>/dev/null || \
           clang-format --dry-run --Werror "$file" 2>/dev/null; then
            print_pass "$file"
        else
            print_fail "$file (needs formatting)"
            echo "$file" >> "$FORMAT_FAIL_FILE"
        fi
    fi
}

# Per-file clang-tidy worker (runs in parallel via xargs). Records critical
# issues in $TIDY_ERROR_FILE and warnings in $TIDY_WARN_FILE.
tidy_worker() {
    local file="$1"
    local output
    output=$(clang-tidy \
        --config-file="$PROJECT_ROOT/.clang-tidy" \
        "$file" \
        -- \
        -I"$TARGET_DIR" \
        -I"$PROJECT_ROOT" \
        2>&1 || true)

    # Check for errors (Critical)
    if echo "$output" | grep -q "error:"; then
        print_fail "$file (critical issues)"
        # Show first few errors
        echo "$output" | grep "error:" | head -3 | while read -r line; do
            echo "    $line"
        done
        echo "$file" >> "$TIDY_ERROR_FILE"
    # Check for warnings (Major/Minor)
    elif echo "$output" | grep -q "warning:"; then
        print_warn "$file (warnings)"
        # Show first few warnings
        echo "$output" | grep "warning:" | head -3 | while read -r line; do
            echo "    $line"
        done
        echo "$file" >> "$TIDY_WARN_FILE"
    else
        print_pass "$file"
    fi
}

# -----------------------------------------------------------------------------
# Main Script
# -----------------------------------------------------------------------------

print_header "C/C++ Code Standards Validation"

echo "Configuration:"
echo "  Target directory: $TARGET_DIR"
echo "  Fix mode: $FIX_MODE"
echo "  Project root: $PROJECT_ROOT"

# Find C/C++ files
FILES=$(find "$TARGET_DIR" -type f \( \
    -name "*.c" -o \
    -name "*.cpp" -o \
    -name "*.cc" -o \
    -name "*.cxx" -o \
    -name "*.h" -o \
    -name "*.hpp" -o \
    -name "*.hxx" \
    \) \
    ! -path "*/build/*" \
    ! -path "*/.git/*" \
    ! -path "*/third_party/*" \
    ! -path "*/vendor/*" \
    2>/dev/null || true)

if [ -z "$FILES" ]; then
    print_warn "No C/C++ files found in $TARGET_DIR"
    exit 0
fi

FILE_COUNT=$(echo "$FILES" | wc -l | tr -d ' ')
print_info "Found $FILE_COUNT file(s) to check"

# Track errors
FORMAT_ERRORS=0
TIDY_ERRORS=0
TIDY_WARNINGS=0

# =============================================================================
# STEP 1: Format Check (clang-format)
# =============================================================================

print_section "clang-format check"

FORMAT_FAIL_FILE=$(mktemp)
export -f format_worker print_pass print_fail
export PROJECT_ROOT FIX_MODE FORMAT_FAIL_FILE RED YELLOW GREEN BLUE BOLD NC
printf '%s\n' $FILES | xargs -P "$JOBS" -I{} bash -c 'format_worker "$@"' _ {} || true
FORMAT_ERRORS=$(wc -l < "$FORMAT_FAIL_FILE" | tr -d ' ')
rm -f "$FORMAT_FAIL_FILE"

if [ $FORMAT_ERRORS -eq 0 ]; then
    echo ""
    print_pass "All files properly formatted"
else
    echo ""
    print_fail "$FORMAT_ERRORS file(s) have formatting issues"
    if ! $FIX_MODE; then
        echo "  Run with --fix to auto-format"
    fi
fi

# =============================================================================
# STEP 2: Static Analysis (clang-tidy)
# =============================================================================

print_section "clang-tidy analysis"

# Only analyze source files (not headers)
SOURCE_FILES=$(echo "$FILES" | grep -E '\.(c|cpp|cc|cxx)$' || true)

if [ -z "$SOURCE_FILES" ]; then
    print_info "No source files to analyze (headers only)"
else
    TIDY_ERROR_FILE=$(mktemp)
    TIDY_WARN_FILE=$(mktemp)
    export -f tidy_worker print_pass print_fail print_warn
    export PROJECT_ROOT TARGET_DIR TIDY_ERROR_FILE TIDY_WARN_FILE RED YELLOW GREEN BLUE BOLD NC
    printf '%s\n' $SOURCE_FILES | xargs -P "$JOBS" -I{} bash -c 'tidy_worker "$@"' _ {} || true
    TIDY_ERRORS=$(wc -l < "$TIDY_ERROR_FILE" | tr -d ' ')
    TIDY_WARNINGS=$(wc -l < "$TIDY_WARN_FILE" | tr -d ' ')
    rm -f "$TIDY_ERROR_FILE" "$TIDY_WARN_FILE"
fi

if [ $TIDY_ERRORS -eq 0 ] && [ $TIDY_WARNINGS -eq 0 ]; then
    echo ""
    print_pass "No issues found"
elif [ $TIDY_ERRORS -eq 0 ]; then
    echo ""
    print_warn "$TIDY_WARNINGS file(s) have warnings (review recommended)"
else
    echo ""
    print_fail "$TIDY_ERRORS file(s) have critical issues"
    if [ $TIDY_WARNINGS -gt 0 ]; then
        print_warn "$TIDY_WARNINGS file(s) have additional warnings"
    fi
fi

# =============================================================================
# SUMMARY
# =============================================================================

print_header "Summary"

TOTAL_ISSUES=$((FORMAT_ERRORS + TIDY_ERRORS))
EXIT_CODE=0

# Format results
if [ $FORMAT_ERRORS -gt 0 ]; then
    echo -e "${RED}Format:   $FORMAT_ERRORS file(s) need formatting${NC}"
    EXIT_CODE=1
else
    echo -e "${GREEN}Format:   OK${NC}"
fi

# clang-tidy results
if [ $TIDY_ERRORS -gt 0 ]; then
    echo -e "${RED}Analysis: $TIDY_ERRORS file(s) have critical issues${NC}"
    if [ $EXIT_CODE -eq 0 ]; then
        EXIT_CODE=2
    else
        EXIT_CODE=3
    fi
elif [ $TIDY_WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}Analysis: $TIDY_WARNINGS file(s) have warnings${NC}"
else
    echo -e "${GREEN}Analysis: OK${NC}"
fi

# Overall status
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}${BOLD}✓ All checks passed!${NC}"
else
    echo -e "${RED}${BOLD}✗ Validation failed (exit code: $EXIT_CODE)${NC}"
fi

echo ""
exit $EXIT_CODE
