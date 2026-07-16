# C/C++ Code Standards Compliance Framework

> **Centralized clang-format and clang-tidy configuration for safety-critical C/C++ development with Windsurf AI.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Executive Summary (For Decision-Makers & Non-C Developers)

### The Three Clang Tools Explained

This framework uses **three related but different tools** from the LLVM/Clang project:

| Tool | Config File | What It Does | When It Runs |
|------|-------------|--------------|--------------|
| **clang-format** | `.clang-format` | Makes code look consistent (spacing, braces) | On save, or manually |
| **clang-tidy** | `.clang-tidy` | Finds bugs and security issues | In CI/CD, or manually |
| **clangd** | `.clangd` | Powers IDE features (autocomplete, go-to-definition, real-time errors) | Continuously in your editor |

Think of them as **spell-check, grammar-check, and an intelligent writing assistant** for C/C++ code:

| Tool | Analogy |
|------|---------|
| **clang-format** | Auto-formatting a Word doc to match a style guide |
| **clang-tidy** | Grammarly flagging unclear sentences or errors |
| **clangd** | A smart assistant that highlights issues as you type and helps you navigate |

#### How They Work Together

```
┌─────────────────────────────────────────────────────────────────┐
│                     YOUR EDITOR (Windsurf/VSCode)               │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                      clangd                                │ │
│  │         (runs continuously, powers IDE features)          │ │
│  │                                                           │ │
│  │  • Autocomplete suggestions                               │ │
│  │  • Go-to-definition (Cmd+Click)                          │ │
│  │  • Find all references                                    │ │
│  │  • Real-time error squiggles (uses clang-tidy checks!)   │ │
│  │  • Hover documentation                                    │ │
│  │  • Format on save (uses clang-format!)                   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│              ┌───────────────┴───────────────┐                 │
│              ▼                               ▼                 │
│       ┌─────────────┐                 ┌─────────────┐         │
│       │.clang-format│                 │ .clang-tidy │         │
│       │  (styling)  │                 │  (analysis) │         │
│       └─────────────┘                 └─────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

> **Key insight:** clangd **incorporates** both clang-format and clang-tidy! When you see real-time warnings in your editor, those come from clang-tidy rules. When you format on save, that uses clang-format. The `.clangd` file customizes how these run in your IDE.

These are **free, industry-standard tools**. The challenge? They come with **300+ configuration options** and no opinion on what's correct.

### Why Not Just Use the Tools Directly?

| Without This Framework | With This Framework |
|------------------------|---------------------|
| Spend **4-8 hours** researching 300+ options | Copy 2 files, **ready in 5 minutes** |
| Every warning looks the same priority | Clear **Critical/Major/Minor** classification |
| Describe issues with jargon | Reference by **Rule ID** ("Rule 21 violation") |
| Write your own CI/CD integration | **Copy-paste** GitHub Actions example |
| Hope you didn't miss important security checks | **Pre-configured** with CERT security standards |
| AI assistant gives generic help | AI **enforces your rules** with fix suggestions |

### The Analogy

**clang-format + clang-tidy alone** = A blank spreadsheet app

**This framework** = A pre-built accounting template with:
- ✅ Columns already labeled
- ✅ Formulas already set up  
- ✅ Color-coding for "over budget" (red) vs "on track" (green)
- ✅ Instructions for auditors
- ✅ One-click "Generate Report" button

You *could* build all that yourself. But why would you?

### Bottom Line

| Metric | Value |
|--------|-------|
| **Setup time saved** | 4-8 hours per project |
| **Bugs caught** | Null dereference, buffer overflow, memory leaks, use-after-free |
| **Security standards** | CERT C, MISRA-inspired checks |
| **AI integration** | Windsurf Cascade enforces rules automatically |
| **Cost** | Free (MIT License) |

---

## Table of Contents

- [What Is This?](#what-is-this)
- [Why Use This Framework?](#why-use-this-framework)
- [When to Use This](#when-to-use-this)
- [Where to Use This](#where-to-use-this)
- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Severity Classification](#severity-classification)
- [Rule Reference](#rule-reference)
- [Repository Contents](#repository-contents)
- [CI/CD Integration](#cicd-integration)
- [clangd IDE Integration](#clangd-ide-integration)
- [Windsurf AI Integration](#windsurf-ai-integration)
- [Customization](#customization)
- [Requirements](#requirements)
- [FAQ](#faq)

---

## What Is This?

This framework provides a **complete, ready-to-use code standards enforcement system** for C and C++ projects. It combines:

1. **clang-format** - Automatic code formatting (consistent style)
2. **clang-tidy** - Static analysis (bug detection, security checks)
3. **Severity Classification** - Triage issues as Critical, Major, or Minor
4. **Windsurf AI Rules** - Intelligent code review with fix suggestions

Instead of writing rules from scratch or relying on inconsistent natural language guidelines, this framework gives you **deterministic, tool-enforced standards** that work the same way every time.

---

## Why Use This Framework?

### The Problem

Teams often struggle with code standards because:

- **Natural language rules are ambiguous** - "Use good variable names" means different things to different people
- **Manual code review is inconsistent** - Reviewers catch different issues on different days
- **Setting up tools is time-consuming** - clang-tidy has 300+ checks with complex configuration
- **No clear priority** - Which violations should block a merge vs. just warn?

### The Solution

This framework solves these problems by providing:

| Benefit | Description |
|---------|-------------|
| **Deterministic Enforcement** | Same code = same result, every time |
| **Pre-configured for Safety** | CERT, MISRA-inspired rules out of the box |
| **Severity Classification** | Clear Critical/Major/Minor triage |
| **AI-Assisted Review** | Windsurf explains violations and suggests fixes |
| **Drop-in Ready** | Copy configs to your project and run |
| **CI/CD Ready** | Exit codes for pass/fail in pipelines |

### Key Benefits

- **Catch bugs before runtime** - Null dereference, buffer overflow, use-after-free
- **Enforce security standards** - CERT C, security-focused checks
- **Reduce code review time** - Automated checks handle style and common bugs
- **Onboard developers faster** - Clear, documented rules with examples
- **Demonstrate compliance** - Traceable rule numbers for audits

---

## When to Use This

### Use This Framework When:

- ✅ You're starting a new C/C++ project and want standards from day one
- ✅ You're adding static analysis to an existing codebase
- ✅ You need safety-critical code standards (automotive, medical, aerospace, defense)
- ✅ You want consistent formatting across a team
- ✅ You're using Windsurf and want AI-assisted code review
- ✅ You need to demonstrate compliance with coding standards (CERT, MISRA-inspired)
- ✅ You want to catch common bugs before they reach production

### Consider Alternatives When:

- ❌ You're working in a language other than C/C++
- ❌ Your organization has existing, incompatible standards you must follow
- ❌ You need formal MISRA certification (this is MISRA-inspired, not certified)

---

## Where to Use This

### Supported Environments

| Environment | Support Level |
|-------------|---------------|
| **Linux** | Full support |
| **macOS** | Full support |
| **Windows** | Full support (with LLVM/clang installed) |
| **CI/CD Pipelines** | GitHub Actions, GitLab CI, Jenkins, etc. |
| **IDEs** | VSCode, CLion, Vim, **Windsurf** (with clangd integration) |
| **Windsurf** | Full AI integration |

### Project Types

- Embedded systems
- Operating systems / kernel development
- Safety-critical applications
- Security-sensitive code
- Any C/C++ application

---

## Quick Start

### Option A: Use as GitHub Template (New Projects)

1. Click **"Use this template"** button on GitHub
2. Clone your new repository
3. Start coding with standards already configured

### Option B: Add to Existing Project

```bash
# Clone this framework
git clone https://github.com/COG-GTM/-C-C-Code-Standards-Compliance-Framework.git

# Copy configs to your project
cp -C-Code-Standards-Compliance-Framework/.clang-format /path/to/your/project/
cp -C-Code-Standards-Compliance-Framework/.clang-tidy /path/to/your/project/

# (Optional) Copy Windsurf rules
mkdir -p /path/to/your/project/.windsurf/rules
cp -C-Code-Standards-Compliance-Framework/windsurf/c-safety-critical-rules.md \
   /path/to/your/project/.windsurf/rules/
```

### Option C: One-Line Install (curl)

```bash
# Run from your project root
curl -sL https://raw.githubusercontent.com/COG-GTM/-C-C-Code-Standards-Compliance-Framework/main/.clang-format -o .clang-format && \
curl -sL https://raw.githubusercontent.com/COG-GTM/-C-C-Code-Standards-Compliance-Framework/main/.clang-tidy -o .clang-tidy
```

### Verify Installation

```bash
# Check formatting (reports violations)
clang-format --dry-run --Werror src/*.c

# Run static analysis
clang-tidy src/*.c -- -I./include

# Or use the validation script
./scripts/validate.sh src/
```

---

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Your C/C++ Project                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐    ┌─────────────┐    ┌──────────────────┐   │
│   │ .clang-     │    │ .clang-tidy │    │ windsurf/        │   │
│   │ format      │    │             │    │ rules.md         │   │
│   └──────┬──────┘    └──────┬──────┘    └────────┬─────────┘   │
│          │                  │                     │             │
│          ▼                  ▼                     ▼             │
│   ┌─────────────┐    ┌─────────────┐    ┌──────────────────┐   │
│   │ clang-      │    │ clang-tidy  │    │ Windsurf AI      │   │
│   │ format      │    │ (analysis)  │    │ (review)         │   │
│   │ (style)     │    │             │    │                  │   │
│   └──────┬──────┘    └──────┬──────┘    └────────┬─────────┘   │
│          │                  │                     │             │
│          ▼                  ▼                     ▼             │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                  Consistent, Safe Code                   │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Workflow

1. **Developer writes code** in their IDE
2. **Pre-commit hook** (optional) runs clang-format
3. **Developer commits** code to branch
4. **CI pipeline** runs clang-format and clang-tidy
5. **Windsurf** (if used) provides AI-assisted review
6. **Issues classified** as Critical (block), Major (review), Minor (warn)
7. **Developer fixes** issues based on severity
8. **Code merges** when all Critical issues resolved

---

## Severity Classification

Issues are classified into three severity levels for effective triage:

| Severity | Icon | Action | Blocks Merge? | Examples |
|----------|------|--------|---------------|----------|
| **Critical** | 🔴 | Must fix immediately | Yes | Null dereference, buffer overflow, use-after-free, unchecked return values |
| **Major** | 🟡 | Requires review | Recommended | Narrowing conversions, missing error handling, thread safety |
| **Minor** | 🟢 | Fix when convenient | No | Formatting, naming conventions, style preferences |

### Why Severity Matters

- **Critical issues** are potential crashes, security vulnerabilities, or data corruption
- **Major issues** may cause bugs in edge cases or reduce maintainability
- **Minor issues** affect readability but not functionality

See `rule-severity-mapping.yaml` for the complete mapping of clang-tidy checks to severity levels.

---

## Rule Reference

### Critical Rules (Block Merge)

| Rule ID | Name | Description |
|---------|------|-------------|
| Rule 20 | Check Return Values | All return values from fallible functions must be checked |
| Rule 21 | Buffer Overflow | Use bounded string functions, validate array indices |
| Rule 22 | Null Dereference | Validate all pointers before use |
| Rule 23 | Resource Leaks | Free all allocated memory, close all handles |
| Rule 24 | Use-After-Free | Never access memory after freeing |
| Rule 25 | Uninitialized | Initialize all variables before use |
| Rule 26 | Security | Avoid insecure APIs (rand, strcpy, etc.) |

### Major Rules (Requires Review)

| Rule ID | Name | Description |
|---------|------|-------------|
| Rule 30 | Narrowing Conversions | Check overflow before casting to smaller types |
| Rule 31 | Parameter Names | Declaration and definition names must match |
| Rule 32 | Redundant Code | Remove duplicate or unreachable code |
| Rule 33 | Infinite Loops | Avoid loops that cannot terminate |
| Rule 34 | Thread Safety | Use thread-safe functions in multi-threaded code |
| Rule 35 | Performance | Avoid unnecessary copies and allocations |

### Minor Rules (Style)

| Rule ID | Name | Description |
|---------|------|-------------|
| Rule 40 | Brace Style | Consistent Allman brace placement |
| Rule 41 | Naming | Consistent naming conventions |
| Rule 42 | Braces | Always use braces around blocks |
| Rule 43 | Boolean | Simplify boolean expressions |
| Rule 44 | Else After Return | Remove unnecessary else after return |
| Rule 45 | Nullptr | Use nullptr instead of NULL (C++) |
| Rule 46 | Unused Parameters | Remove or annotate unused parameters |

See `docs/rule-reference.md` for detailed examples of each rule.

---

## Repository Contents

```
.
├── README.md                      # This documentation
├── .clang-format                  # Code formatting configuration
├── .clang-tidy                    # Static analysis configuration
├── .clangd                        # clangd language server configuration
├── rule-severity-mapping.yaml     # Severity classification
├── vscode-settings.json.template  # VSCode/Windsurf settings template
│
├── windsurf/
│   └── c-safety-critical-rules.md # Windsurf AI rules
│
├── examples/
│   ├── compliant.c                # Code that passes all checks
│   └── violations.c               # Code with intentional violations (for testing)
│
├── scripts/
│   ├── validate.sh                # Validation wrapper script
│   └── generate-compile-commands.sh # Generate compile_commands.json for clangd
│
├── tests/
│   ├── __init__.py
│   └── test_compliance.py         # Automated tests for configs
│
└── docs/
    ├── rule-reference.md          # Detailed rule documentation
    └── clangd-setup.md            # clangd setup guide
```

---

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/code-standards.yml`:

```yaml
name: Code Standards

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install clang tools
        run: |
          sudo apt-get update
          sudo apt-get install -y clang-format clang-tidy

      - name: Check formatting
        run: |
          find src -name "*.c" -o -name "*.h" | xargs clang-format --dry-run --Werror

      - name: Run clang-tidy
        run: |
          find src -name "*.c" | xargs clang-tidy -- -I./include
```

### GitLab CI

Create `.gitlab-ci.yml`:

```yaml
code-standards:
  image: ubuntu:22.04
  before_script:
    - apt-get update && apt-get install -y clang-format clang-tidy
  script:
    - find src -name "*.c" -o -name "*.h" | xargs clang-format --dry-run --Werror
    - find src -name "*.c" | xargs clang-tidy -- -I./include
```

### Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Auto-format staged C files before commit

STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(c|cpp|h|hpp)$')

if [ -n "$STAGED_FILES" ]; then
    echo "Formatting staged C/C++ files..."
    echo "$STAGED_FILES" | xargs clang-format -i
    echo "$STAGED_FILES" | xargs git add
fi
```

---

## clangd IDE Integration

This framework includes full **clangd** language server support for intelligent C/C++ development in Windsurf, VSCode, and other editors.

### What You Need (3 Things)

To get full IDE intelligence for C/C++, you need **three components**:

| Component | What It Is | Where to Get It |
|-----------|-----------|-----------------|
| **1. clangd (program)** | The "brain" that analyzes your code | Install on your computer (see below) |
| **2. clangd extension** | Connects your editor to clangd | Install from Windsurf/VSCode marketplace |
| **3. This framework** | Pre-configured settings | You're looking at it! |

### Step 1: Install clangd on Your Computer

**macOS (Homebrew):**
```bash
brew install llvm

# Add to your shell profile (~/.zshrc or ~/.bash_profile)
echo 'export PATH="/opt/homebrew/opt/llvm/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Verify it works
clangd --version
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
# LLVM 16+ packages are published at https://apt.llvm.org (add the repo first):
sudo apt-get install clangd-19  # or just 'clangd'

# Verify
clangd --version
```

**Windows:**
1. Download LLVM from https://releases.llvm.org/
2. Run the installer
3. Check "Add LLVM to PATH" during installation
4. Open new terminal and run `clangd --version`

### Step 2: Install the clangd Extension in Windsurf

1. Open Windsurf
2. Go to Extensions (Cmd+Shift+X on Mac, Ctrl+Shift+X on Windows/Linux)
3. Search for **"clangd"**
4. Install the one by **llvm-vs-code-extensions** (has 4.6M downloads)
5. **Important:** If prompted, disable Microsoft's C/C++ IntelliSense (it conflicts with clangd)

### Step 3: Use This Framework in Your Project

**Option A: Clone and copy configs to your existing project**
```bash
# Clone this framework
git clone https://github.com/COG-GTM/-C-Code-Standards-Compliance-Framework.git

# Copy the config files to your project
cp -C-Code-Standards-Compliance-Framework/.clang-format /path/to/your/project/
cp -C-Code-Standards-Compliance-Framework/.clang-tidy /path/to/your/project/
cp -C-Code-Standards-Compliance-Framework/.clangd /path/to/your/project/

# Copy the scripts
cp -r -C-Code-Standards-Compliance-Framework/scripts /path/to/your/project/

# Generate compile_commands.json (required for clangd to work fully)
cd /path/to/your/project
./scripts/generate-compile-commands.sh
```

**Option B: Use this repo as a template (new projects)**
1. Click "Use this template" on GitHub
2. Clone your new repo
3. Run `./scripts/generate-compile-commands.sh`
4. Start coding!

### Step 4: Configure Your Editor Settings

```bash
# In your project directory
mkdir -p .vscode
cp vscode-settings.json.template .vscode/settings.json
```

This configures Windsurf/VSCode to:
- Use clangd instead of Microsoft's C++ IntelliSense
- Format on save using our `.clang-format`
- Show clang-tidy warnings in real-time

### Verify Everything Works

After setup, you should see:
- ✅ **Autocomplete** when you type (e.g., type `mal` and see `malloc` suggested)
- ✅ **Go to Definition** works (Cmd+Click on a function name)
- ✅ **Real-time errors** appear as red squiggles
- ✅ **Hover info** shows function signatures and docs

If something isn't working, see **[docs/clangd-setup.md](docs/clangd-setup.md)** for troubleshooting.

### Files Included for clangd

| File | Purpose |
|------|---------|
| `.clangd` | Tells clangd which checks to run, include paths, etc. |
| `scripts/generate-compile-commands.sh` | Creates `compile_commands.json` (clangd needs this to understand your project) |
| `vscode-settings.json.template` | Editor settings to enable clangd and disable conflicting extensions |
| `docs/clangd-setup.md` | Detailed setup guide with troubleshooting |

---

## Windsurf AI Integration

When using Windsurf with these rules, the AI assistant (Cascade) will:

1. **Detect violations** in your code as you write
2. **Classify by severity** (Critical, Major, Minor)
3. **Report with rule numbers** (e.g., "Rule 20 violation: unchecked return value")
4. **Explain why** the rule matters
5. **Suggest fixes** with compliant code patterns

### Setup

1. Copy rules to your project:
   ```bash
   mkdir -p .windsurf/rules
   cp windsurf/c-safety-critical-rules.md .windsurf/rules/
   ```

2. Open your project in Windsurf
3. Cascade will automatically enforce the rules

### Example Interaction

```
User: Review this function

Cascade: I found 2 issues:

🔴 **Critical - Rule 20 violation**: Return value of `fopen` is not checked.
   Line 5: `FILE *f = fopen("data.txt", "r");`
   
   Fix: Add null check before using the file handle.

🟡 **Major - Rule 30 violation**: Narrowing conversion from `size_t` to `int`.
   Line 12: `int count = bytes_read;`
   
   Fix: Check for overflow or use appropriate type.
```

---

## Customization

### Adjusting Severity

Edit `rule-severity-mapping.yaml` to change which checks are Critical, Major, or Minor.

### Adding/Removing Checks

Edit `.clang-tidy`:

```yaml
Checks: >
  bugprone-*,
  cert-*,
  -bugprone-easily-swappable-parameters,  # Disable this check
  misc-my-custom-check,                    # Add this check
```

### Project-Specific Options

Add to `.clang-tidy`:

```yaml
CheckOptions:
  - key: readability-identifier-naming.FunctionCase
    value: camelCase  # Or lower_case, CamelCase, etc.
```

### Suppressing Warnings

```c
// Single line
malloc(size);  // NOLINT(clang-analyzer-unix.Malloc)

// Block
// NOLINTBEGIN(bugprone-unused-return-value)
legacy_function_call();
// NOLINTEND(bugprone-unused-return-value)

// Whole file (add at top)
// NOLINTFILE(check-name)
```

---

## Requirements

### Required Tools

| Tool | Minimum Version | Purpose |
|------|-----------------|---------|
| clang-format | 14.0+ | Code formatting |
| clang-tidy | 14.0+ | Static analysis |

### Optional Tools

| Tool | Purpose |
|------|---------|
| Python 3.8+ | Running tests |
| pytest | Test framework |
| PyYAML | Parsing severity mapping |

### Installation

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y clang-format clang-tidy
```

**macOS (Homebrew):**
```bash
brew install llvm
export PATH="/opt/homebrew/opt/llvm/bin:$PATH"
```

**Windows:**
Download LLVM from https://releases.llvm.org/ and add to PATH.

---

## FAQ

### Q: Does this replace manual code review?

**A:** No. This automates the mechanical parts of code review (formatting, common bugs) so human reviewers can focus on architecture, logic, and domain-specific concerns.

### Q: Is this MISRA certified?

**A:** No. This is MISRA-inspired but not formally certified. For formal MISRA compliance, use a certified tool like Polyspace or PC-lint.

### Q: Can I use this with CMake?

**A:** Yes. Add to your `CMakeLists.txt`:
```cmake
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
```
Then run clang-tidy with `--config-file=.clang-tidy -p build/`.

### Q: How do I set up clangd for IDE integration?

**A:** This framework includes full clangd support:
1. Generate `compile_commands.json`: `./scripts/generate-compile-commands.sh`
2. Copy VSCode settings: `mkdir -p .vscode && cp vscode-settings.json.template .vscode/settings.json`
3. See `docs/clangd-setup.md` for detailed instructions

### Q: How do I handle legacy code with many violations?

**A:** Options:
1. Fix violations incrementally (start with Critical only)
2. Use `// NOLINT` to suppress known violations in legacy files
3. Use `.clang-tidy` `HeaderFilterRegex` to only check new code

### Q: Can I contribute new rules?

**A:** Yes! Open a pull request with:
1. Rule description
2. Example compliant and non-compliant code
3. Mapping to clang-tidy check (if applicable)

---

## License

MIT License - Free for use in any project, commercial or open source.

---

## Support

- **Issues:** https://github.com/COG-GTM/-C-C-Code-Standards-Compliance-Framework/issues
- **Discussions:** https://github.com/COG-GTM/-C-C-Code-Standards-Compliance-Framework/discussions

---

**Made with ❤️ for safer C/C++ code**
