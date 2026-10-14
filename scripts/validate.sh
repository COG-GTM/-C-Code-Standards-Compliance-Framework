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

# Resolve the style argument once instead of retrying every file: clang-format
# < 14 does not understand --style=file:<path> and falls back to discovery.
CF_STYLE_ARG="--style=file:$PROJECT_ROOT/.clang-format"
if ! clang-format "$CF_STYLE_ARG" --dump-config >/dev/null 2>&1; then
    CF_STYLE_ARG=""
fi

JOBS="${VALIDATE_JOBS:-$(nproc 2>/dev/null || getconf _NPROCESSORS_ONLN 2>/dev/null || echo 1)}"
if ! [[ "$JOBS" =~ ^[0-9]+$ ]] || [ "$JOBS" -lt 1 ]; then
    JOBS=1
fi
FORMAT_BATCH=$(( (FILE_COUNT + JOBS - 1) / JOBS ))
if [ "$FORMAT_BATCH" -gt 64 ]; then
    FORMAT_BATCH=64
elif [ "$FORMAT_BATCH" -lt 1 ]; then
    FORMAT_BATCH=1
fi

# Runs one clang-format process for a batch of files and emits a
# "PASS|FAIL<TAB>file" NUL-terminated record per file. If the batch fails,
# its files are re-run individually so each result stays per-file.
format_batch() {
    local mode_args=(--dry-run --Werror)
    if [ "$CF_FIX_MODE" = true ]; then
        mode_args=(-i)
    fi
    local style_args=()
    if [ -n "$CF_STYLE_ARG" ]; then
        style_args=("$CF_STYLE_ARG")
    fi

    local f status
    if clang-format "${mode_args[@]}" "${style_args[@]}" "$@" 2>/dev/null; then
        for f in "$@"; do
            printf 'PASS\t%s\0' "$f"
        done
        return 0
    fi
    [ "$#" -eq 1 ] && { printf 'FAIL\t%s\0' "$1"; return 0; }
    for f in "$@"; do
        status=FAIL
        if clang-format "${mode_args[@]}" "${style_args[@]}" "$f" 2>/dev/null; then
            status=PASS
        fi
        printf '%s\t%s\0' "$status" "$f"
    done
    return 0
}
export -f format_batch
export CF_STYLE_ARG
export CF_FIX_MODE="$FIX_MODE"

declare -A FORMAT_STATUS=()
while IFS=$'\t' read -r -d '' status file; do
    FORMAT_STATUS["$file"]="$status"
done < <(for file in $FILES; do printf '%s\0' "$file"; done | \
    xargs -0 -n "$FORMAT_BATCH" -P "$JOBS" bash -c 'format_batch "$@"' _)

for file in $FILES; do
    if $FIX_MODE; then
        if [ "${FORMAT_STATUS[$file]:-FAIL}" = PASS ]; then
            print_pass "Formatted: $file"
        else
            print_fail "Could not format: $file"
            FORMAT_ERRORS=$((FORMAT_ERRORS + 1))
        fi
    else
        if [ "${FORMAT_STATUS[$file]:-FAIL}" = PASS ]; then
            print_pass "$file"
        else
            print_fail "$file (needs formatting)"
            FORMAT_ERRORS=$((FORMAT_ERRORS + 1))
        fi
    fi
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
