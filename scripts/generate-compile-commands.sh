#!/bin/bash
# =============================================================================
# Generate compile_commands.json for clangd
# =============================================================================
# This script generates a compile_commands.json file that clangd uses for
# intelligent code analysis, completion, and navigation.
#
# Usage: ./scripts/generate-compile-commands.sh [--use-build] [directory]
#
# By default the script only scans the source tree and writes basic entries
# for every C/C++ file (no project code is executed).
#
# With --use-build it first tries the project's build system:
#   1. CMake - if CMakeLists.txt exists (runs `cmake` configure)
#   2. Bear  - if a Makefile exists (runs `make clean` and `bear -- make`)
# WARNING: CMakeLists.txt and Makefiles can run arbitrary commands. Only use
# --use-build on projects you trust.
#
# Arguments:
#   --use-build Run CMake / Bear (executes project build code)
#   directory   Target directory to scan (default: current directory)
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

# Find script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

usage() {
    echo "Usage: $0 [--use-build] [directory]"
    echo ""
    echo "  --use-build  Generate via CMake or Bear. This EXECUTES the project's"
    echo "               CMakeLists.txt / Makefile code; only use on trusted projects."
    echo "  directory    Target directory to scan (default: current directory)"
}

USE_BUILD=false
TARGET_DIR=""
while [ $# -gt 0 ]; do
    case "$1" in
        --use-build)
            USE_BUILD=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
        *)
            [ -n "$TARGET_DIR" ] && { usage >&2; exit 2; }
            TARGET_DIR="$1"
            ;;
    esac
    shift
done
if [ $# -gt 0 ]; then
    [ -n "$TARGET_DIR" ] || [ $# -gt 1 ] && { usage >&2; exit 2; }
    TARGET_DIR="$1"
fi

TARGET_DIR="${TARGET_DIR:-.}"
cd -- "$TARGET_DIR"

print_header() {
    echo ""
    echo -e "${BOLD}${BLUE}======================================================${NC}"
    echo -e "${BOLD}${BLUE}  $1${NC}"
    echo -e "${BOLD}${BLUE}======================================================${NC}"
    echo ""
}

print_info() {
    echo -e "${BLUE}ℹ INFO${NC}: $1"
}

print_success() {
    echo -e "${GREEN}✓ SUCCESS${NC}: $1"
}

print_warn() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
}

print_error() {
    echo -e "${RED}✗ ERROR${NC}: $1"
}

# -----------------------------------------------------------------------------
# Method 1: CMake
# -----------------------------------------------------------------------------
generate_with_cmake() {
    print_info "CMakeLists.txt found, using CMake..."
    
    mkdir -p build
    cd build
    
    if cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON .. 2>/dev/null; then
        if [ -f compile_commands.json ]; then
            cp compile_commands.json ../
            cd ..
            print_success "Generated compile_commands.json using CMake"
            return 0
        fi
    fi
    
    cd ..
    return 1
}

# -----------------------------------------------------------------------------
# Method 2: Bear (intercept build commands)
# -----------------------------------------------------------------------------
generate_with_bear() {
    if ! command -v bear &> /dev/null; then
        return 1
    fi
    
    if [ ! -f Makefile ] && [ ! -f makefile ]; then
        return 1
    fi
    
    print_info "Makefile found and Bear available, using Bear..."
    
    # Clean first to ensure full rebuild
    make clean 2>/dev/null || true
    
    if bear -- make 2>/dev/null; then
        print_success "Generated compile_commands.json using Bear"
        return 0
    fi
    
    return 1
}

# -----------------------------------------------------------------------------
# Method 3: Manual generation
# -----------------------------------------------------------------------------
generate_manually() {
    print_info "Generating compile_commands.json manually..."
    
    # Find all C/C++ source files
    FILES=$(find . -type f \( \
        -name "*.c" -o \
        -name "*.cpp" -o \
        -name "*.cc" -o \
        -name "*.cxx" \
        \) \
        ! -path "*/build/*" \
        ! -path "*/.git/*" \
        ! -path "*/third_party/*" \
        ! -path "*/vendor/*" \
        2>/dev/null || true)
    
    if [ -z "$FILES" ]; then
        print_warn "No C/C++ source files found"
        return 1
    fi
    
    # Get absolute path of current directory
    CURRENT_DIR=$(pwd)
    
    # Determine compiler
    if command -v clang &> /dev/null; then
        COMPILER="clang"
    elif command -v gcc &> /dev/null; then
        COMPILER="gcc"
    else
        COMPILER="cc"
    fi
    
    # Build include flags
    INCLUDE_FLAGS="-I. -I./include -I./src"
    
    # Check for common include directories
    [ -d "inc" ] && INCLUDE_FLAGS="$INCLUDE_FLAGS -I./inc"
    [ -d "includes" ] && INCLUDE_FLAGS="$INCLUDE_FLAGS -I./includes"

    INCLUDE_JSON=""
    for flag in $INCLUDE_FLAGS; do
        INCLUDE_JSON="$INCLUDE_JSON
      \"$flag\","
    done
    
    # Start JSON array
    echo "[" > compile_commands.json
    
    FIRST=true
    for file in $FILES; do
        # Get absolute path
        ABS_FILE="$CURRENT_DIR/${file#./}"
        
        # Determine language standard
        if [[ "$file" == *.c ]]; then
            STD="-std=c17"
        else
            STD="-std=c++17"
        fi
        
        # Add comma separator (except for first entry)
        if [ "$FIRST" = true ]; then
            FIRST=false
        else
            echo "," >> compile_commands.json
        fi
        
        # Write entry
        cat >> compile_commands.json << EOF
  {
    "directory": "$CURRENT_DIR",
    "file": "$ABS_FILE",
    "arguments": [
      "$COMPILER",
      "-c",
      "$STD",
      "-Wall",
      "-Wextra",$INCLUDE_JSON
      "$ABS_FILE",
      "-o",
      "${ABS_FILE%.c*}.o"
    ]
  }
EOF
    done
    
    echo "" >> compile_commands.json
    echo "]" >> compile_commands.json
    
    FILE_COUNT=$(echo "$FILES" | wc -l | tr -d ' ')
    print_success "Generated compile_commands.json with $FILE_COUNT entries"
    return 0
}

# -----------------------------------------------------------------------------
# Method 4: Create minimal template
# -----------------------------------------------------------------------------
create_template() {
    print_info "Creating minimal compile_commands.json template..."
    
    CURRENT_DIR=$(pwd)
    
    cat > compile_commands.json << EOF
[
  {
    "directory": "$CURRENT_DIR",
    "file": "$CURRENT_DIR/src/main.c",
    "arguments": [
      "clang",
      "-c",
      "-std=c17",
      "-Wall",
      "-Wextra",
      "-I.",
      "-I./include",
      "-I./src",
      "$CURRENT_DIR/src/main.c",
      "-o",
      "$CURRENT_DIR/build/main.o"
    ]
  }
]
EOF
    
    print_success "Created template compile_commands.json"
    print_warn "Edit this file to match your project structure"
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
print_header "Generate compile_commands.json"

print_info "Working directory: $(pwd)"
print_info "Project root: $PROJECT_ROOT"

if [ "$USE_BUILD" = true ]; then
    print_warn "--use-build: running the project's CMake/Make code (only do this for trusted projects)"

    if [ -f CMakeLists.txt ]; then
        if generate_with_cmake; then
            exit 0
        fi
        print_warn "CMake generation failed, trying alternatives..."
    fi

    if generate_with_bear; then
        exit 0
    fi
elif [ -f CMakeLists.txt ] || [ -f Makefile ] || [ -f makefile ]; then
    print_info "Build files found but not executed; pass --use-build to use CMake/Bear (runs project code, trusted projects only)"
fi

if generate_manually; then
    exit 0
fi

# Last resort: create template
create_template

echo ""
print_info "compile_commands.json is required for full clangd functionality"
print_info "For best results on trusted projects, rerun with --use-build (CMake or Bear)"
print_info "Install Bear: brew install bear (macOS) / apt install bear (Linux)"
echo ""
