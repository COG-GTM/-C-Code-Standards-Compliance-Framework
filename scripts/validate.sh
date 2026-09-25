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

# Parallelism for the per-file tool invocations
JOBS=$(nproc 2>/dev/null || echo 4)
print_info "Using $JOBS parallel job(s)"

# Track errors
FORMAT_ERRORS=0
TIDY_ERRORS=0
TIDY_WARNINGS=0

# =============================================================================
# STEP 1: Format Check (clang-format)
# =============================================================================

print_section "clang-format check"

# Resolve the style argument once: whether clang-format accepts the project
# style file does not vary per file.
CF_STYLE=""
PROBE_FILE=$(printf '%s\n' "$FILES" | head -n 1)
if clang-format --style=file:"$PROJECT_ROOT/.clang-format" \
       --output-replacements-xml "$PROBE_FILE" >/dev/null 2>&1; then
    CF_STYLE="--style=file:$PROJECT_ROOT/.clang-format"
else
    print_warn "Could not use $PROJECT_ROOT/.clang-format, falling back to default style"
fi
export CF_STYLE

if $FIX_MODE; then
    # Apply formatting fixes in batches (clang-format -i accepts many files),
    # falling back to per-file runs within a failing batch so the offending
    # file is still reported.
    FORMAT_RESULTS=$(printf '%s\n' "$FILES" | xargs -n 32 -P "$JOBS" sh -c '
        if clang-format -i ${CF_STYLE:+"$CF_STYLE"} "$@" 2>/dev/null; then
            for f in "$@"; do printf "PASS\t%s\n" "$f"; done
        else
            for f in "$@"; do
                if clang-format -i ${CF_STYLE:+"$CF_STYLE"} "$f" 2>/dev/null; then
                    printf "PASS\t%s\n" "$f"
                else
                    printf "FAIL\t%s\n" "$f"
                fi
            done
        fi' _ || true)
else
    # Check only (dry run), one file per process but spread across all cores
    FORMAT_RESULTS=$(printf '%s\n' "$FILES" | xargs -P "$JOBS" -I {} sh -c '
        if clang-format --dry-run --Werror ${CF_STYLE:+"$CF_STYLE"} "$1" 2>/dev/null; then
            printf "PASS\t%s\n" "$1"
        else
            printf "FAIL\t%s\n" "$1"
        fi' _ {} || true)
fi

while IFS=$'\t' read -r status file; do
    [ -n "$file" ] || continue
    if [ "$status" = "PASS" ]; then
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
done < <(printf '%s\n' "$FORMAT_RESULTS" | sort -t$'\t' -k2)

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
    # Run clang-tidy across all cores; each worker stores its verdict and the
    # excerpt of diagnostics in a numbered file so the report stays ordered.
    TIDY_TMP=$(mktemp -d)
    trap 'rm -rf "$TIDY_TMP"' EXIT

    export TIDY_TMP
    export CT_CONFIG="$PROJECT_ROOT/.clang-tidy"
    export CT_TARGET_DIR="$TARGET_DIR"
    export CT_PROJECT_ROOT="$PROJECT_ROOT"

    printf '%s\n' "$SOURCE_FILES" | nl -b a -w 1 -s ' ' | \
        xargs -P "$JOBS" -I {} sh -c '
            idx=${1%% *}
            file=${1#* }
            output=$(clang-tidy \
                --config-file="$CT_CONFIG" \
                "$file" \
                -- \
                -I"$CT_TARGET_DIR" \
                -I"$CT_PROJECT_ROOT" \
                2>&1 || true)
            if printf "%s\n" "$output" | grep -q "error:"; then
                { echo FAIL
                  printf "%s\n" "$output" | grep "error:" | head -3 | sed "s/^/    /"
                } > "$TIDY_TMP/$idx"
            elif printf "%s\n" "$output" | grep -q "warning:"; then
                { echo WARN
                  printf "%s\n" "$output" | grep "warning:" | head -3 | sed "s/^/    /"
                } > "$TIDY_TMP/$idx"
            else
                echo PASS > "$TIDY_TMP/$idx"
            fi' _ {} || true

    mapfile -t TIDY_FILES <<< "$SOURCE_FILES"
    for i in "${!TIDY_FILES[@]}"; do
        file="${TIDY_FILES[$i]}"
        result_file="$TIDY_TMP/$((i + 1))"
        [ -f "$result_file" ] || continue
        status=$(head -n 1 "$result_file")
        if [ "$status" = "FAIL" ]; then
            print_fail "$file (critical issues)"
            tail -n +2 "$result_file"
            TIDY_ERRORS=$((TIDY_ERRORS + 1))
        elif [ "$status" = "WARN" ]; then
            print_warn "$file (warnings)"
            tail -n +2 "$result_file"
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
