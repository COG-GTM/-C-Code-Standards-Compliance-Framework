# clangd Setup Guide for Windsurf/VSCode

> **Complete guide to setting up clangd language server for intelligent C/C++ development.**

---

## What is clangd?

**clangd** is a language server that provides IDE features for C/C++:

| Feature | Description |
|---------|-------------|
| **Code Completion** | Intelligent suggestions based on context |
| **Go to Definition** | Jump to function/variable definitions |
| **Find References** | Find all usages of a symbol |
| **Diagnostics** | Real-time error and warning detection |
| **Hover Information** | Documentation on hover |
| **Code Formatting** | Auto-format using clang-format |
| **Inlay Hints** | Show parameter names and types inline |
| **Rename Symbol** | Safely rename across files |

Unlike Microsoft's C/C++ extension, clangd uses the **same compiler frontend as Clang**, giving you accurate diagnostics that match what you'll see at compile time.

---

## Quick Setup

### Step 1: Install clangd

**macOS (Homebrew):**
```bash
brew install llvm
# Add to PATH (add to ~/.zshrc or ~/.bash_profile)
export PATH="/opt/homebrew/opt/llvm/bin:$PATH"
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install clangd
# Or for a specific version (LLVM 16+ via https://apt.llvm.org):
sudo apt-get install clangd-20
```

**Windows:**
Download LLVM from https://releases.llvm.org/ and add to PATH.

**Verify installation:**
```bash
clangd --version
```

### Step 2: Copy Configuration Files

This framework includes pre-configured clangd settings:

```bash
# Already in your project (from this framework):
# .clangd           - clangd configuration
# .clang-format     - code formatting rules
# .clang-tidy       - static analysis rules
```

### Step 3: Generate compile_commands.json

clangd needs `compile_commands.json` to understand your project structure:

**Option A: Use the included script**
```bash
chmod +x scripts/generate-compile-commands.sh
./scripts/generate-compile-commands.sh
```

**Option B: CMake (recommended for CMake projects)**
```bash
mkdir build && cd build
cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON ..
cp compile_commands.json ../
```

**Option C: Bear (for Makefile projects)**
```bash
# Install Bear
brew install bear  # macOS
apt install bear   # Linux

# Generate compile_commands.json
bear -- make
```

**Option D: Manual creation**
Create `compile_commands.json` in your project root:
```json
[
  {
    "directory": "/path/to/your/project",
    "file": "/path/to/your/project/src/main.c",
    "arguments": ["clang", "-c", "-std=c17", "-I./include", "src/main.c"]
  }
]
```

### Step 4: Configure Windsurf/VSCode

**Option A: Copy the template**
```bash
mkdir -p .vscode
cp vscode-settings.json.template .vscode/settings.json
```

**Option B: Manual settings**

Add to your workspace settings (`.vscode/settings.json`):
```json
{
  "C_Cpp.intelliSenseEngine": "disabled",
  "clangd.arguments": [
    "--enable-config",
    "--background-index",
    "--clang-tidy",
    "--completion-style=detailed",
    "--header-insertion=iwyu"
  ],
  "[c]": {
    "editor.defaultFormatter": "llvm-vs-code-extensions.vscode-clangd",
    "editor.formatOnSave": true
  }
}
```

### Step 5: Install clangd Extension (if available)

In VSCode, install the **clangd** extension:
- Extension ID: `llvm-vs-code-extensions.vscode-clangd`

**Note for Windsurf:** If the clangd extension isn't available in the marketplace, clangd still works! The language server protocol works directly with the editor. Just ensure:
1. clangd is installed and in your PATH
2. The `.clangd` config file exists
3. `compile_commands.json` exists

Windsurf will automatically detect and use clangd for C/C++ files.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                     Your Editor (Windsurf/VSCode)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐    ┌─────────────────────┐                   │
│   │ Your C/C++  │    │  Language Server    │                   │
│   │ Source Code │◄──►│  Protocol (LSP)     │                   │
│   └─────────────┘    └──────────┬──────────┘                   │
│                                 │                               │
│                                 ▼                               │
│                      ┌──────────────────────┐                  │
│                      │       clangd         │                  │
│                      │  (language server)   │                  │
│                      └──────────┬───────────┘                  │
│                                 │                               │
│              ┌──────────────────┼──────────────────┐           │
│              │                  │                  │           │
│              ▼                  ▼                  ▼           │
│   ┌─────────────────┐  ┌──────────────┐  ┌──────────────┐     │
│   │ compile_        │  │   .clangd    │  │ .clang-tidy  │     │
│   │ commands.json   │  │   (config)   │  │ .clang-format│     │
│   └─────────────────┘  └──────────────┘  └──────────────┘     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Configuration Files Reference

### .clangd

Controls clangd behavior:

```yaml
CompileFlags:
  Add: [-std=c17, -Wall, -I./include]
  
Diagnostics:
  ClangTidy:
    Add: [bugprone-*, cert-*]
    
InlayHints:
  ParameterNames: Yes
  DeducedTypes: Yes
```

### compile_commands.json

Tells clangd how to compile each file:

```json
[
  {
    "directory": "/project",
    "file": "/project/src/main.c",
    "arguments": ["clang", "-c", "-std=c17", "-I./include", "src/main.c"]
  }
]
```

---

## Troubleshooting

### clangd not starting

1. Check if clangd is installed: `clangd --version`
2. Check PATH: `which clangd`
3. Check clangd logs: Command Palette → "clangd: Open logs"

### No IntelliSense / completions

1. Ensure `compile_commands.json` exists in project root
2. Check if file is in `compile_commands.json`
3. Restart clangd: Command Palette → "clangd: Restart language server"

### Incorrect errors/warnings

1. Regenerate `compile_commands.json`
2. Check include paths are correct
3. Ensure C standard matches your project (`-std=c17` vs `-std=c11`)

### Conflicts with Microsoft C/C++ extension

Add to settings:
```json
{
  "C_Cpp.intelliSenseEngine": "disabled",
  "C_Cpp.autocomplete": "disabled",
  "C_Cpp.errorSquiggles": "disabled"
}
```

### Missing system headers

Add system include paths to `.clangd`:
```yaml
CompileFlags:
  Add:
    - -isystem/usr/include
    - -isystem/usr/local/include
```

---

## Advanced Configuration

### Per-Directory Settings

In `.clangd`:
```yaml
If:
  PathMatch: tests/.*
CompileFlags:
  Add: [-DTEST_BUILD=1]

---

If:
  PathMatch: src/debug/.*
CompileFlags:
  Add: [-DDEBUG=1, -O0, -g]
```

### Custom Checks

Add project-specific clang-tidy checks:
```yaml
Diagnostics:
  ClangTidy:
    Add:
      - modernize-*
      - cppcoreguidelines-*
    Remove:
      - modernize-use-trailing-return-type
    CheckOptions:
      readability-identifier-naming.FunctionCase: camelCase
```

### Suppress Specific Warnings

```yaml
Diagnostics:
  Suppress:
    - unused-variable
    - pp_file_not_found
```

---

## Integration with This Framework

This framework is pre-configured to work with clangd:

| File | Purpose |
|------|---------|
| `.clangd` | clangd language server config |
| `.clang-format` | Code formatting rules |
| `.clang-tidy` | Static analysis rules |
| `scripts/generate-compile-commands.sh` | Generate compilation database |
| `vscode-settings.json.template` | VSCode/Windsurf settings template |

The configurations are aligned, so:
- **Diagnostics** shown in your editor match `clang-tidy` CI checks
- **Formatting** matches what `clang-format` produces
- **Severity** classification aligns with the framework's rules

---

## Resources

- [clangd Official Documentation](https://clangd.llvm.org/)
- [clangd Configuration Reference](https://clangd.llvm.org/config)
- [compile_commands.json Format](https://clang.llvm.org/docs/JSONCompilationDatabase.html)
- [clangd VSCode Extension](https://marketplace.visualstudio.com/items?itemName=llvm-vs-code-extensions.vscode-clangd)
