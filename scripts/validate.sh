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

# Run clang-format across all cores instead of one serial process per file.
# Each file is independent (check is read-only; -i edits distinct files), so
# results, per-file PASS/FAIL messages, and the FORMAT_ERRORS count are
# identical to the serial run - only scheduling changes.
FMT_NPROC=$(nproc 2>/dev/null || echo 4)
FMT_TMP=$(mktemp -d)
trap 'rm -rf "$FMT_TMP"' EXIT

idx=0
for file in $FILES; do
    echo "$idx $file"
    idx=$((idx + 1))
done > "$FMT_TMP/manifest"

format_one() {
    local idx="$1" file="$2"
    if $FIX_MODE; then
        # Apply formatting fixes
        if clang-format -i --style=file:"$PROJECT_ROOT/.clang-format" "$file" 2>/dev/null || \
           clang-format -i "$file" 2>/dev/null; then
            echo pass > "$FMT_TMP/$idx.st"
        else
            echo fail > "$FMT_TMP/$idx.st"
        fi
    else
        # Check only (dry run)
        if clang-format --dry-run --Werror --style=file:"$PROJECT_ROOT/.clang-format" "$file" 2>/dev/null || \
           clang-format --dry-run --Werror "$file" 2>/dev/null; then
            echo pass > "$FMT_TMP/$idx.st"
        else
            echo fail > "$FMT_TMP/$idx.st"
        fi
    fi
}
export -f format_one
export FIX_MODE PROJECT_ROOT FMT_TMP

xargs -P "$FMT_NPROC" -L1 bash -c 'format_one "$@"' _ < "$FMT_TMP/manifest"

# Emit per-file results serially, in the original order, so output and the
# FORMAT_ERRORS count match the serial run exactly.
idx=0
for file in $FILES; do
    if [ "$(cat "$FMT_TMP/$idx.st")" = pass ]; then
        if $FIX_MODE; then
            print_pass "Formatted: $file"
        else
            print_pass "$file"
        fi
    else
        if $FIX_MODE; then
            print_fail "Could not format: $file"
        else
            print_fail "$file (needs formatting)"
        fi
        FORMAT_ERRORS=$((FORMAT_ERRORS + 1))
    fi
    idx=$((idx + 1))
done

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
    for file in $SOURCE_FILES; do
        # Run clang-tidy
        OUTPUT=$(clang-tidy \
            --config-file="$PROJECT_ROOT/.clang-tidy" \
            "$file" \
            -- \
            -I"$TARGET_DIR" \
            -I"$PROJECT_ROOT" \
            2>&1 || true)

        # Check for errors (Critical)
        if echo "$OUTPUT" | grep -q "error:"; then
            print_fail "$file (critical issues)"
            # Show first few errors
            echo "$OUTPUT" | grep "error:" | head -3 | while read -r line; do
                echo "    $line"
            done
            TIDY_ERRORS=$((TIDY_ERRORS + 1))
        # Check for warnings (Major/Minor)
        elif echo "$OUTPUT" | grep -q "warning:"; then
            print_warn "$file (warnings)"
            # Show first few warnings
            echo "$OUTPUT" | grep "warning:" | head -3 | while read -r line; do
                echo "    $line"
            done
            TIDY_WARNINGS=$((TIDY_WARNINGS + 1))
        else
            print_pass "$file"
        fi
    done
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
