#!/bin/bash
# =============================================================================
# Code Standards Validation Script (Java / Maven)
# =============================================================================
# Usage: ./scripts/validate.sh [directory] [--fix]
#
# Arguments:
#   directory   Target directory to scan for Java sources (default: current dir).
#               Used to decide whether there is anything to check; the analyzers
#               themselves operate on the Maven module defined by pom.xml.
#   --fix       Apply safe auto-formatting if a formatter is configured in the
#               build (e.g. spotless:apply). If none is wired, prints a message
#               and skips.
#
# What it does:
#   1. Pins JDK 17 (SpotBugs crashes on newer JDKs such as JDK 26).
#   2. Runs the three analyzers in ONE Maven invocation:
#        compile + checkstyle:checkstyle + pmd:pmd + spotbugs:spotbugs
#      (one invocation so build-helper's examples/ source root is in effect).
#   3. Parses the generated XML reports:
#        target/checkstyle-result.xml, target/pmd.xml, target/spotbugsXml.xml
#   4. Classifies every finding into Critical / Major / Minor by consulting
#        rule-severity-mapping.yaml (maps each tool check / rule / bug pattern
#        to its severity tier).
#
# Exit codes:
#   0 - Clean: no Critical-tier findings (Major/Minor only warn).
#   1 - One or more Critical-tier findings (block merge).
#   2 - Analysis could not run (Maven failed and no reports were produced).
#
# Examples:
#   ./scripts/validate.sh                    # Check current directory
#   ./scripts/validate.sh examples/          # Gate on Java sources under examples/
#   ./scripts/validate.sh --fix              # Auto-format (if a formatter is wired)
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

# Find script directory and project root (the directory containing pom.xml)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

MAPPING_FILE="$PROJECT_ROOT/rule-severity-mapping.yaml"

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
# Output helpers
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
# JDK 17 pinning (SpotBugs crashes on JDK 26 with an FBClassReader/ASM error)
# -----------------------------------------------------------------------------

detect_jdk17() {
    local candidates=(
        "/usr/lib/jvm/java-17-openjdk-amd64"
        "/usr/lib/jvm/java-1.17.0-openjdk-amd64"
        "/usr/lib/jvm/temurin-17-jdk-amd64"
        "/usr/lib/jvm/openjdk-17"
    )
    local c d
    for c in "${candidates[@]}"; do
        if [ -x "$c/bin/java" ]; then
            echo "$c"
            return 0
        fi
    done
    if [ -d /usr/lib/jvm ]; then
        for d in /usr/lib/jvm/*17*; do
            if [ -x "$d/bin/java" ]; then
                echo "$d"
                return 0
            fi
        done
    fi
    return 1
}

pin_jdk17() {
    local jdk17
    jdk17="$(detect_jdk17 || true)"
    if [ -n "$jdk17" ]; then
        export JAVA_HOME="$jdk17"
        export PATH="$JAVA_HOME/bin:$PATH"
        print_info "Using JDK 17: $JAVA_HOME"
    elif java -version 2>&1 | grep -qE 'version "(1\.)?17'; then
        print_info "Using JDK 17 from PATH: $(command -v java)"
    else
        print_warn "Could not locate a JDK 17 install."
        print_warn "Set JAVA_HOME to a JDK 17 (e.g. install temurin-17/openjdk-17)."
    fi
    print_warn "SpotBugs requires JDK 17 — it crashes on newer JDKs (e.g. JDK 26)."
}

# -----------------------------------------------------------------------------
# Severity mapping: build a "Tool:Check -> tier" lookup from the YAML mapping
# -----------------------------------------------------------------------------

declare -A TIER_OF

load_severity_mapping() {
    if [ ! -f "$MAPPING_FILE" ]; then
        print_warn "Missing $MAPPING_FILE; findings cannot be classified by tier."
        return 0
    fi

    local tier tool name
    while IFS='|' read -r tier tool name; do
        [ -z "$tier" ] && continue
        TIER_OF["$tool:$name"]="$tier"
    done < <(awk '
        /^[[:space:]][[:space:]]critical:/ { tier="critical"; next }
        /^[[:space:]][[:space:]]major:/    { tier="major";    next }
        /^[[:space:]][[:space:]]minor:/    { tier="minor";    next }
        /-[[:space:]]*"(SpotBugs|PMD|Checkstyle):/ {
            line = $0
            sub(/^[^"]*"/, "", line)   # drop up to and including the opening quote
            sub(/".*$/, "", line)      # drop the closing quote and anything after
            split(line, a, ":")
            tool = a[1]
            rest = a[2]
            sub(/^[[:space:]]+/, "", rest)   # trim leading space
            sub(/[[:space:](].*$/, "", rest) # keep only the first token (the check id)
            if (tier != "" && rest != "") {
                print tier "|" tool "|" rest
            }
        }
    ' "$MAPPING_FILE")
}

# Resolve a "Tool" + "check name" to a tier; echoes critical/major/minor or
# "unclassified" when the check is not present in the mapping.
tier_for() {
    local key="$1:$2"
    if [ -n "${TIER_OF[$key]:-}" ]; then
        echo "${TIER_OF[$key]}"
    else
        echo "unclassified"
    fi
}

# -----------------------------------------------------------------------------
# Report extraction helpers (one check identifier per line)
# -----------------------------------------------------------------------------

# Checkstyle: source="...naming.MethodNameCheck" -> MethodName
checkstyle_checks() {
    local report="$1"
    [ -f "$report" ] || return 0
    grep -oE 'source="[^"]+"' "$report" \
        | sed -E 's/^source="//; s/"$//; s/.*\.//; s/Check$//' || true
}

# PMD: rule="CloseResource" -> CloseResource
pmd_checks() {
    local report="$1"
    [ -f "$report" ] || return 0
    grep -oE 'rule="[^"]+"' "$report" \
        | sed -E 's/^rule="//; s/"$//' || true
}

# SpotBugs: <BugInstance ... type='EI_EXPOSE_REP' ...> -> EI_EXPOSE_REP
# The spotbugs-maven-plugin serializer emits single-quoted attributes; accept
# double quotes too so other SpotBugs configurations are handled robustly.
spotbugs_checks() {
    local report="$1"
    [ -f "$report" ] || return 0
    grep -oE "<BugInstance[^>]*>" "$report" \
        | grep -oE "type=['\"][^'\"]*['\"]" \
        | sed -E "s/^type=['\"]//; s/['\"]\$//" || true
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

print_header "Java Code Standards Validation"

pin_jdk17

echo ""
echo "Configuration:"
echo "  Target directory: $TARGET_DIR"
echo "  Fix mode:         $FIX_MODE"
echo "  Project root:     $PROJECT_ROOT"
echo "  Severity mapping: $MAPPING_FILE"

# Find Java files to decide whether there is anything to check.
JAVA_FILES=$(find "$TARGET_DIR" -type f -name "*.java" \
    ! -path "*/target/*" \
    ! -path "*/.git/*" \
    ! -path "*/build/*" \
    2>/dev/null || true)

if [ -z "$JAVA_FILES" ]; then
    print_warn "No Java files found in $TARGET_DIR"
    exit 0
fi

FILE_COUNT=$(echo "$JAVA_FILES" | wc -l | tr -d ' ')
print_info "Found $FILE_COUNT Java file(s) under $TARGET_DIR"

load_severity_mapping
print_info "Loaded ${#TIER_OF[@]} check->severity mappings"

# ---------------------------------------------------------------------------
# --fix mode: apply a formatter if one is configured, otherwise skip
# ---------------------------------------------------------------------------
if $FIX_MODE; then
    print_section "Auto-fix (formatting)"
    if grep -qi "spotless" "$PROJECT_ROOT/pom.xml" 2>/dev/null; then
        print_info "Spotless detected; running 'mvn spotless:apply'..."
        if ( cd "$PROJECT_ROOT" && mvn -B -ntp spotless:apply ); then
            print_pass "Applied Spotless formatting"
        else
            print_fail "Spotless formatting failed"
        fi
    elif grep -qi "formatter-maven-plugin" "$PROJECT_ROOT/pom.xml" 2>/dev/null; then
        print_info "formatter-maven-plugin detected; running 'mvn formatter:format'..."
        if ( cd "$PROJECT_ROOT" && mvn -B -ntp formatter:format ); then
            print_pass "Applied formatter-maven-plugin formatting"
        else
            print_fail "Formatter run failed"
        fi
    else
        print_info "No auto-formatter is wired into the build (no Spotless / formatter plugin)."
        print_info "Skipping --fix; Checkstyle reports formatting/brace issues for manual fixes."
    fi
fi

# ---------------------------------------------------------------------------
# Run the analyzers (one Maven invocation so examples/ is on the source path)
# ---------------------------------------------------------------------------
print_section "Running analyzers (Checkstyle + PMD + SpotBugs via Maven)"

CHECKSTYLE_REPORT="$PROJECT_ROOT/target/checkstyle-result.xml"
PMD_REPORT="$PROJECT_ROOT/target/pmd.xml"
SPOTBUGS_REPORT="$PROJECT_ROOT/target/spotbugsXml.xml"

MVN_RC=0
(
    cd "$PROJECT_ROOT" && \
    mvn -B -ntp clean compile \
        checkstyle:checkstyle \
        pmd:pmd \
        com.github.spotbugs:spotbugs-maven-plugin:spotbugs
) || MVN_RC=$?

if [ "$MVN_RC" -ne 0 ]; then
    print_warn "Maven exited with code $MVN_RC; will classify whatever reports exist."
fi

if [ ! -f "$CHECKSTYLE_REPORT" ] && [ ! -f "$PMD_REPORT" ] && [ ! -f "$SPOTBUGS_REPORT" ]; then
    print_fail "No analysis reports were produced — cannot validate."
    exit 2
fi

if [ -f "$CHECKSTYLE_REPORT" ]; then print_pass "Checkstyle report: $CHECKSTYLE_REPORT"; else print_warn "Missing $CHECKSTYLE_REPORT"; fi
if [ -f "$PMD_REPORT" ];        then print_pass "PMD report:        $PMD_REPORT";        else print_warn "Missing $PMD_REPORT"; fi
if [ -f "$SPOTBUGS_REPORT" ];   then print_pass "SpotBugs report:   $SPOTBUGS_REPORT";   else print_warn "Missing $SPOTBUGS_REPORT"; fi

# ---------------------------------------------------------------------------
# Classify findings by severity tier
# ---------------------------------------------------------------------------
print_section "Classifying findings by severity"

CRITICAL_COUNT=0
MAJOR_COUNT=0
MINOR_COUNT=0
UNCLASSIFIED_COUNT=0

# Samples to print per tier (avoid flooding the console)
declare -a CRITICAL_SAMPLES=()
declare -a MAJOR_SAMPLES=()
declare -a MINOR_SAMPLES=()
declare -a UNCLASSIFIED_SAMPLES=()

record_finding() {
    local tool="$1" name="$2" tier
    [ -z "$name" ] && return 0
    tier="$(tier_for "$tool" "$name")"
    case "$tier" in
        critical)
            CRITICAL_COUNT=$((CRITICAL_COUNT + 1))
            [ "${#CRITICAL_SAMPLES[@]}" -lt 10 ] && CRITICAL_SAMPLES+=("$tool: $name")
            ;;
        major)
            MAJOR_COUNT=$((MAJOR_COUNT + 1))
            [ "${#MAJOR_SAMPLES[@]}" -lt 10 ] && MAJOR_SAMPLES+=("$tool: $name")
            ;;
        minor)
            MINOR_COUNT=$((MINOR_COUNT + 1))
            [ "${#MINOR_SAMPLES[@]}" -lt 10 ] && MINOR_SAMPLES+=("$tool: $name")
            ;;
        *)
            UNCLASSIFIED_COUNT=$((UNCLASSIFIED_COUNT + 1))
            [ "${#UNCLASSIFIED_SAMPLES[@]}" -lt 10 ] && UNCLASSIFIED_SAMPLES+=("$tool: $name")
            ;;
    esac
}

while IFS= read -r name; do
    record_finding "Checkstyle" "$name"
done < <(checkstyle_checks "$CHECKSTYLE_REPORT")

while IFS= read -r name; do
    record_finding "PMD" "$name"
done < <(pmd_checks "$PMD_REPORT")

while IFS= read -r name; do
    record_finding "SpotBugs" "$name"
done < <(spotbugs_checks "$SPOTBUGS_REPORT")

print_tier_samples() {
    local label="$1"; shift
    local samples=("$@")
    if [ "${#samples[@]}" -gt 0 ]; then
        echo "  $label findings:"
        local s
        for s in "${samples[@]}"; do
            echo "    - $s"
        done
    fi
}

if [ "$CRITICAL_COUNT" -gt 0 ]; then
    print_fail "$CRITICAL_COUNT Critical finding(s)"
    print_tier_samples "Critical" "${CRITICAL_SAMPLES[@]}"
else
    print_pass "No Critical findings"
fi

if [ "$MAJOR_COUNT" -gt 0 ]; then
    print_warn "$MAJOR_COUNT Major finding(s) (review recommended)"
    print_tier_samples "Major" "${MAJOR_SAMPLES[@]}"
else
    print_pass "No Major findings"
fi

if [ "$MINOR_COUNT" -gt 0 ]; then
    print_warn "$MINOR_COUNT Minor finding(s) (style/maintainability)"
    print_tier_samples "Minor" "${MINOR_SAMPLES[@]}"
else
    print_pass "No Minor findings"
fi

if [ "$UNCLASSIFIED_COUNT" -gt 0 ]; then
    print_info "$UNCLASSIFIED_COUNT finding(s) not mapped to a tier (treated as warnings)"
    print_tier_samples "Unmapped" "${UNCLASSIFIED_SAMPLES[@]}"
fi

# ---------------------------------------------------------------------------
# Summary + exit code
# ---------------------------------------------------------------------------
print_header "Summary"

if [ "$CRITICAL_COUNT" -gt 0 ]; then
    echo -e "${RED}Critical: $CRITICAL_COUNT (blocks merge)${NC}"
else
    echo -e "${GREEN}Critical: 0${NC}"
fi

if [ "$MAJOR_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}Major:    $MAJOR_COUNT (review)${NC}"
else
    echo -e "${GREEN}Major:    0${NC}"
fi

if [ "$MINOR_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}Minor:    $MINOR_COUNT (warn)${NC}"
else
    echo -e "${GREEN}Minor:    0${NC}"
fi

if [ "$UNCLASSIFIED_COUNT" -gt 0 ]; then
    echo -e "${BLUE}Unmapped: $UNCLASSIFIED_COUNT (warn)${NC}"
fi

echo ""
if [ "$CRITICAL_COUNT" -gt 0 ]; then
    echo -e "${RED}${BOLD}✗ Validation failed: Critical findings present (exit code: 1)${NC}"
    echo ""
    exit 1
fi

echo -e "${GREEN}${BOLD}✓ All checks passed — no Critical findings!${NC}"
echo ""
exit 0
