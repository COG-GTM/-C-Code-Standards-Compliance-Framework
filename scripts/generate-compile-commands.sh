#!/bin/bash
# =============================================================================
# Generate compile_commands.json for clangd
# =============================================================================
# This script generates a compile_commands.json file that clangd uses for
# intelligent code analysis, completion, and navigation.
#
# Usage: ./scripts/generate-compile-commands.sh [directory]
#
# The script supports multiple build systems:
#   1. CMake (preferred) - if CMakeLists.txt exists
#   2. Bear - intercepts make/gcc commands
#   3. Manual generation - creates basic entries for all C/C++ files
#
# Arguments:
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

# Target directory
TARGET_DIR="${1:-.}"
cd "$TARGET_DIR"

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
    
    # Build include flags as JSON array elements (one quoted string per flag)
    INCLUDE_FLAGS='"-I.",
      "-I./include",
      "-I./src",'
    
    # Check for common include directories
    [ -d "inc" ] && INCLUDE_FLAGS="$INCLUDE_FLAGS
      \"-I./inc\","
    [ -d "includes" ] && INCLUDE_FLAGS="$INCLUDE_FLAGS
      \"-I./includes\","
    
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
      "-Wextra",
      $INCLUDE_FLAGS
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

# Try methods in order of preference
if [ -f CMakeLists.txt ]; then
    if generate_with_cmake; then
        exit 0
    fi
    print_warn "CMake generation failed, trying alternatives..."
fi

if generate_with_bear; then
    exit 0
fi

if generate_manually; then
    exit 0
fi

# Last resort: create template
create_template

echo ""
print_info "compile_commands.json is required for full clangd functionality"
print_info "For best results, use CMake with CMAKE_EXPORT_COMPILE_COMMANDS=ON"
print_info "Or install Bear: brew install bear (macOS) / apt install bear (Linux)"
echo ""
