# Java Code Standards Compliance Framework

> **Centralized Checkstyle, PMD, and SpotBugs configuration for safety-critical Java development with Windsurf AI.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Executive Summary (For Decision-Makers & Non-Java Developers)

### The Three Java Tools Explained

This framework uses **three related but different tools** from the Java static-analysis ecosystem, orchestrated by **Apache Maven**:

| Tool | Config File | What It Does | When It Runs |
|------|-------------|--------------|--------------|
| **Checkstyle** | `checkstyle.xml` | Makes code look consistent (spacing, braces, naming) | On save, or via Maven |
| **PMD + SpotBugs** | `pmd-ruleset.xml`, `spotbugs-exclude.xml` | Finds bugs and security issues | In CI/CD, or via Maven |
| **Java Language Server** | `pom.xml` | Powers IDE features (autocomplete, go-to-definition, real-time errors) | Continuously in your editor |

Think of them as **spell-check, grammar-check, and an intelligent writing assistant** for Java code:

| Tool | Analogy |
|------|---------|
| **Checkstyle** | Auto-formatting a Word doc to match a style guide |
| **PMD + SpotBugs** | Grammarly flagging unclear sentences or errors |
| **Java Language Server** | A smart assistant that highlights issues as you type and helps you navigate |

> **Tooling map (coming from C/C++):** `clang-format → Checkstyle`, `clang-tidy → PMD + SpotBugs`,
> `clangd (LSP) → the Java language server reading pom.xml`. There is no `compile_commands.json`
> in Java — **`pom.xml` is the project model** the language server reads directly.

#### How They Work Together

```
┌─────────────────────────────────────────────────────────────────┐
│                     YOUR EDITOR (Windsurf/VSCode)               │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              Java Language Server (JDT.LS)                 │ │
│  │     (runs continuously, reads pom.xml, powers IDE)        │ │
│  │                                                           │ │
│  │  • Autocomplete suggestions                               │ │
│  │  • Go-to-definition (Ctrl/Cmd+Click)                      │ │
│  │  • Find all references                                    │ │
│  │  • Real-time error squiggles                              │ │
│  │  • Hover documentation                                    │ │
│  │  • Format on save (Checkstyle-aligned)                    │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│       ┌──────────────────────┼──────────────────────┐          │
│       ▼                      ▼                      ▼          │
│ ┌────────────┐      ┌─────────────────┐    ┌────────────────┐  │
│ │ Checkstyle │      │  PMD + SpotBugs │    │     pom.xml    │  │
│ │  (styling) │      │   (analysis)    │    │ (project model)│  │
│ └────────────┘      └─────────────────┘    └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

> **Key insight:** Maven is the single source of truth. The same `checkstyle.xml`,
> `pmd-ruleset.xml`, and `spotbugs-exclude.xml` that run in CI are surfaced live in your editor
> via the Checkstyle/PMD/SpotBugs VS Code extensions, while the language server reads `pom.xml`
> to understand your project — so what you see while typing matches what CI enforces.

These are **free, industry-standard tools**. The challenge? Between them they ship **hundreds of
checks** with no opinion on what's important.

### Why Not Just Use the Tools Directly?

| Without This Framework | With This Framework |
|------------------------|---------------------|
| Spend **4-8 hours** wiring up three Maven plugins | Copy a few files, **ready in minutes** |
| Every warning looks the same priority | Clear **Critical/Major/Minor** classification |
| Describe issues with jargon | Reference by **Rule ID** ("Rule 21 violation") |
| Write your own CI/CD integration | **Copy-paste** GitHub Actions example |
| Hope you didn't miss important security checks | **Pre-configured** with SEI CERT-inspired checks |
| AI assistant gives generic help | AI **enforces your rules** with fix suggestions |

### The Analogy

**Checkstyle + PMD + SpotBugs alone** = A blank spreadsheet app

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
| **Bugs caught** | Null dereference, injection, resource leaks, exposed internal state, insecure crypto |
| **Security standards** | SEI CERT Oracle Coding Standard for Java, CWE-mapped checks |
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
- [Java IDE Integration](#java-ide-integration)
- [Windsurf AI Integration](#windsurf-ai-integration)
- [Customization](#customization)
- [Requirements](#requirements)
- [FAQ](#faq)

---

## What Is This?

This framework provides a **complete, ready-to-use code standards enforcement system** for Java projects. It combines:

1. **Checkstyle** - Automatic style enforcement (formatting, naming, braces)
2. **PMD + SpotBugs** - Static analysis (bug detection, security checks)
3. **Severity Classification** - Triage issues as Critical, Major, or Minor
4. **Windsurf AI Rules** - Intelligent code review with fix suggestions

All three analyzers run through **Apache Maven** (`pom.xml`), so the same rules apply in your IDE,
on the command line, and in CI.

Instead of writing rules from scratch or relying on inconsistent natural language guidelines, this framework gives you **deterministic, tool-enforced standards** that work the same way every time.

---

## Why Use This Framework?

### The Problem

Teams often struggle with code standards because:

- **Natural language rules are ambiguous** - "Use good variable names" means different things to different people
- **Manual code review is inconsistent** - Reviewers catch different issues on different days
- **Setting up tools is time-consuming** - Checkstyle, PMD, and SpotBugs together expose hundreds of rules with complex configuration
- **No clear priority** - Which violations should block a merge vs. just warn?

### The Solution

This framework solves these problems by providing:

| Benefit | Description |
|---------|-------------|
| **Deterministic Enforcement** | Same code = same result, every time |
| **Pre-configured for Safety** | SEI CERT-inspired rules out of the box |
| **Severity Classification** | Clear Critical/Major/Minor triage |
| **AI-Assisted Review** | Windsurf explains violations and suggests fixes |
| **Drop-in Ready** | Copy configs + `pom.xml` plugins to your project and run |
| **CI/CD Ready** | Exit codes for pass/fail in pipelines |

### Key Benefits

- **Catch bugs before runtime** - Null dereference, injection, resource leaks, exposed internal state
- **Enforce security standards** - SEI CERT, CWE-mapped checks
- **Reduce code review time** - Automated checks handle style and common bugs
- **Onboard developers faster** - Clear, documented rules with examples
- **Demonstrate compliance** - Traceable rule numbers for audits

---

## When to Use This

### Use This Framework When:

- ✅ You're starting a new Java project and want standards from day one
- ✅ You're adding static analysis to an existing codebase
- ✅ You need safety-critical code standards (automotive, medical, aerospace, defense, fintech)
- ✅ You want consistent formatting across a team
- ✅ You're using Windsurf and want AI-assisted code review
- ✅ You need to demonstrate compliance with coding standards (SEI CERT, CWE)
- ✅ You want to catch common bugs before they reach production

### Consider Alternatives When:

- ❌ You're working in a language other than Java/JVM
- ❌ Your organization has existing, incompatible standards you must follow

---

## Where to Use This

### Supported Environments

| Environment | Support Level |
|-------------|---------------|
| **Linux** | Full support |
| **macOS** | Full support |
| **Windows** | Full support |
| **CI/CD Pipelines** | GitHub Actions, GitLab CI, Jenkins, etc. |
| **IDEs** | VSCode, IntelliJ IDEA, Eclipse, **Windsurf** (with the Java language server) |
| **Windsurf** | Full AI integration |

> **JDK requirement:** Use **JDK 17** to run the analysis. SpotBugs **crashes on newer JDKs**
> (e.g. JDK 26) with an `FBClassReader`/ASM error, so all Maven analysis goals must run on JDK 17.
> Checkstyle and PMD tolerate newer JDKs, but standardizing on 17 avoids surprises.

### Project Types

- Backend services and APIs
- Libraries and SDKs
- Safety-critical applications
- Security-sensitive code
- Any Java/JVM application

---

## Quick Start

### Prerequisites

Install **JDK 17** and **Apache Maven**:

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y openjdk-17-jdk maven
```

**macOS (Homebrew):**
```bash
brew install openjdk@17 maven
```

On these VMs JDK 17 lives at `/usr/lib/jvm/java-17-openjdk-amd64`. Because the default `java`/`mvn`
may be a newer JDK, always run Maven with `JAVA_HOME` pinned to 17:

```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
java -version   # should report 17.x
```

### Option A: Use as GitHub Template (New Projects)

1. Click **"Use this template"** button on GitHub
2. Clone your new repository
3. Start coding with standards already configured

### Option B: Add to Existing Project

```bash
# Clone this framework (into a clean directory name)
git clone https://github.com/COG-GTM/-C-Code-Standards-Compliance-Framework.git code-standards-framework

# Copy the analysis configs to your project
cp code-standards-framework/checkstyle.xml        /path/to/your/project/
cp code-standards-framework/pmd-ruleset.xml       /path/to/your/project/
cp code-standards-framework/spotbugs-exclude.xml  /path/to/your/project/

# Merge the Checkstyle/PMD/SpotBugs plugin <build> section from this repo's pom.xml
# into your project's pom.xml (see pom.xml for the exact plugin versions).

# (Optional) Copy Windsurf rules
mkdir -p /path/to/your/project/.windsurf/rules
cp code-standards-framework/windsurf/java-safety-critical-rules.md \
   /path/to/your/project/.windsurf/rules/
```

### Verify Installation

```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# Style check (Checkstyle)
mvn checkstyle:check

# Static analysis (PMD + SpotBugs)
mvn pmd:check
mvn spotbugs:check

# Run everything that is bound to the build (compile + all three analyzers + tests)
mvn verify

# Or use the validation script (wraps the Maven goals)
./scripts/validate.sh src/
```

---

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       Your Java Project                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐   ┌────────────────┐   ┌──────────────────┐   │
│   │ checkstyle  │   │ pmd-ruleset    │   │ windsurf/        │   │
│   │ .xml        │   │ .xml + spotbugs│   │ rules.md         │   │
│   │             │   │ -exclude.xml   │   │                  │   │
│   └──────┬──────┘   └───────┬────────┘   └────────┬─────────┘   │
│          │                  │                     │             │
│          ▼                  ▼                     ▼             │
│   ┌─────────────┐   ┌────────────────┐   ┌──────────────────┐   │
│   │ Checkstyle  │   │ PMD + SpotBugs │   │ Windsurf AI      │   │
│   │ (style)     │   │ (analysis)     │   │ (review)         │   │
│   └──────┬──────┘   └───────┬────────┘   └────────┬─────────┘   │
│          │                  │                     │             │
│          │       (all orchestrated by Maven / pom.xml)         │
│          ▼                  ▼                     ▼             │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                  Consistent, Safe Code                   │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Workflow

1. **Developer writes code** in their IDE (Java language server gives live diagnostics)
2. **Pre-commit hook** (optional) runs `mvn checkstyle:check`
3. **Developer commits** code to branch
4. **CI pipeline** runs Checkstyle, PMD, and SpotBugs on JDK 17
5. **Windsurf** (if used) provides AI-assisted review
6. **Issues classified** as Critical (block), Major (review), Minor (warn)
7. **Developer fixes** issues based on severity
8. **Code merges** when all Critical issues resolved

---

## Severity Classification

Issues are classified into three severity levels for effective triage:

| Severity | Icon | Action | Blocks Merge? | Examples |
|----------|------|--------|---------------|----------|
| **Critical** | 🔴 | Must fix immediately | Yes | Null dereference, injection, resource leaks, exposed internal state, unchecked return values |
| **Major** | 🟡 | Requires review | Recommended | Narrowing conversions, confusing methods, thread safety |
| **Minor** | 🟢 | Fix when convenient | No | Formatting, naming conventions, style preferences |

### Why Severity Matters

- **Critical issues** are potential crashes, security vulnerabilities, or data corruption
- **Major issues** may cause bugs in edge cases or reduce maintainability
- **Minor issues** affect readability but not functionality

See `rule-severity-mapping.yaml` for the complete mapping of Checkstyle/PMD/SpotBugs checks to severity levels.

---

## Rule Reference

### Critical Rules (Block Merge)

| Rule ID | Name | Description |
|---------|------|-------------|
| Rule 20 | Check Return Values | All return values from status/value-producing methods must be checked |
| Rule 21 | Injection | Use parameterized APIs; never concatenate untrusted input into SQL/commands |
| Rule 22 | Null Dereference | Validate references before dereferencing |
| Rule 23 | Resource Leaks | Close all `AutoCloseable` resources (try-with-resources) |
| Rule 24 | Leaked Internal References | Defensively copy mutable internal state; don't expose it |
| Rule 25 | Dead Stores / Unwritten Fields | No dead local stores or fields that are read but never written |
| Rule 26 | Security | Avoid insecure APIs (`java.util.Random`, MD5, DES, hard-coded keys) |

### Major Rules (Requires Review)

| Rule ID | Name | Description |
|---------|------|-------------|
| Rule 30 | Narrowing Conversions | Promote to the wide type before arithmetic; check before casting down |
| Rule 31 | Confusing Methods | Group overloads; avoid misleading/confusing method names |
| Rule 32 | Redundant Code | Remove duplicate branches and repeated conditions |
| Rule 33 | Infinite Loops | Ensure every loop/recursion can terminate |
| Rule 34 | Thread Safety | Synchronize shared state consistently; avoid broken double-checked locking |
| Rule 35 | Performance | Avoid needless allocation; use `StringBuilder`, hoist objects out of loops |

### Minor Rules (Style)

| Rule ID | Name | Description |
|---------|------|-------------|
| Rule 40 | Brace Style | Consistent end-of-line (K&R) brace placement |
| Rule 41 | Naming | Java naming conventions (camelCase / UPPER_SNAKE / UpperCamelCase) |
| Rule 42 | Braces | Always use braces around blocks |
| Rule 43 | Boolean | Simplify boolean expressions |
| Rule 44 | Else After Return | Remove unnecessary else after return (advisory) |
| Rule 45 | Avoid Returning Null | Return empty collections/arrays instead of `null` |
| Rule 46 | Unused Members | Remove unused parameters, fields, and locals |

See [docs/rule-reference.md](docs/rule-reference.md) for detailed examples of each rule.

---

## Repository Contents

```
.
├── README.md                      # This documentation
├── pom.xml                        # Maven build + Checkstyle/PMD/SpotBugs plugins
├── checkstyle.xml                 # Checkstyle configuration (style/naming/braces)
├── pmd-ruleset.xml                # PMD ruleset (bug/design/dead-code)
├── spotbugs-exclude.xml           # SpotBugs exclusion filter
├── rule-severity-mapping.yaml     # Severity classification
├── vscode-settings.json.template  # VSCode/Windsurf settings template
│
├── windsurf/
│   └── java-safety-critical-rules.md # Windsurf AI rules
│
├── examples/
│   ├── Compliant.java             # Code that passes all checks
│   └── Violations.java            # Code with intentional violations (for testing)
│
├── scripts/
│   └── validate.sh                # Validation wrapper script (runs the Maven goals)
│
├── src/
│   └── test/java/com/example/standards/
│       └── ComplianceTest.java    # JUnit tests for the configs
│
└── docs/
    ├── rule-reference.md          # Detailed rule documentation
    └── java-ide-setup.md          # Java language server / IDE setup guide
```

> Maven coordinates: groupId `com.example`, artifactId `code-standards-compliance`, version `1.0.0`.

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
  analysis:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '17'        # SpotBugs requires JDK 17 (crashes on newer JDKs)
          cache: maven

      - name: Checkstyle
        run: mvn -B checkstyle:check

      - name: PMD
        run: mvn -B pmd:check

      - name: SpotBugs
        run: mvn -B spotbugs:check

      # Or run everything bound to the build in one shot:
      # - name: Verify
      #   run: mvn -B verify
```

### GitLab CI

Create `.gitlab-ci.yml`:

```yaml
code-standards:
  image: maven:3.9-eclipse-temurin-17   # pins JDK 17 for SpotBugs
  script:
    - mvn -B checkstyle:check
    - mvn -B pmd:check
    - mvn -B spotbugs:check
```

### Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Run Checkstyle on staged Java files before commit

STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.java$')

if [ -n "$STAGED_FILES" ]; then
    echo "Running Checkstyle on staged Java files..."
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 mvn -q checkstyle:check || exit 1
fi
```

---

## Java IDE Integration

This framework works with the **Java language server** (Eclipse JDT.LS, used by VS Code's
"Extension Pack for Java" / Red Hat "Language Support for Java") for intelligent Java development
in Windsurf, VSCode, and other editors.

### What You Need (3 Things)

| Component | What It Is | Where to Get It |
|-----------|-----------|-----------------|
| **1. JDK 17** | Compiles and runs the analysis | Install on your computer (see Quick Start) |
| **2. Extension Pack for Java** | Connects your editor to the Java language server | Install from Windsurf/VSCode marketplace |
| **3. This framework** | Pre-configured `pom.xml` + rule configs | You're looking at it! |

### How It Works

The Java language server reads your **`pom.xml`** to understand the project's classpath, source
roots, and dependencies — exactly the role `compile_commands.json` played for clangd in C/C++.
Once it has imported the Maven project, you get autocomplete, go-to-definition, find-references,
and live diagnostics. The Checkstyle, PMD, and SpotBugs VS Code extensions surface the *same*
`checkstyle.xml` / `pmd-ruleset.xml` / `spotbugs-exclude.xml` findings inline as you type.

### Quick Setup

```bash
# In your project directory
mkdir -p .vscode
cp vscode-settings.json.template .vscode/settings.json
```

This configures Windsurf/VSCode to:
- Import the Maven project via the Java language server
- Format on save using Java conventions
- Show Checkstyle / PMD / SpotBugs diagnostics in real-time

See **[docs/java-ide-setup.md](docs/java-ide-setup.md)** for the full setup guide and troubleshooting.

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
   cp windsurf/java-safety-critical-rules.md .windsurf/rules/
   ```

2. Open your project in Windsurf
3. Cascade will automatically enforce the rules

### Example Interaction

```
User: Review this method

Cascade: I found 2 issues:

🔴 **Critical - Rule 23 violation**: InputStream is not closed on all paths.
   Line 5: `InputStream in = Files.newInputStream(path);`

   Fix: Wrap it in a try-with-resources block.

🟡 **Major - Rule 30 violation**: Multiplication overflows in int before widening to long.
   Line 12: `long nanos = 1_000_000 * seconds;`

   Fix: Use a long literal: `1_000_000L * seconds`.
```

---

## Customization

### Adjusting Severity

Edit `rule-severity-mapping.yaml` to change which checks are Critical, Major, or Minor.

### Adding/Removing Checks

- **Checkstyle:** add/remove `<module>` entries in `checkstyle.xml`.
- **PMD:** add/remove `<rule>` references in `pmd-ruleset.xml` (PMD 6 ruleset syntax).
- **SpotBugs:** add `<Match>` entries in `spotbugs-exclude.xml` to exclude patterns.

### Suppressing Warnings

```java
// Checkstyle (with SuppressWarningsFilter enabled)
@SuppressWarnings("checkstyle:MethodName")
void Legacy_Name() { }

// PMD
@SuppressWarnings("PMD.UnusedFormalParameter")  // or: someCall(); // NOPMD - reason

// SpotBugs (from com.github.spotbugs:spotbugs-annotations)
@SuppressFBWarnings(value = "EI_EXPOSE_REP", justification = "array is caller-owned")
```

**Always add a comment explaining why a suppression is necessary.**

---

## Requirements

### Required Tools

| Tool | Minimum Version | Purpose |
|------|-----------------|---------|
| JDK | **17** (required for SpotBugs) | Compile + run analysis |
| Apache Maven | 3.9+ | Build + plugin orchestration |

### Pinned Tool Versions (configured in `pom.xml`)

| Plugin / Tool | Version |
|---------------|---------|
| maven-checkstyle-plugin | 3.3.1 (Checkstyle 10.12.7) |
| maven-pmd-plugin | 3.21.2 (PMD 6.55.0) |
| spotbugs-maven-plugin | 4.8.3.1 (SpotBugs 4.8.3) |
| maven-surefire-plugin | 3.2.5 |
| JUnit Jupiter | 5.10.2 |

### Installation

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y openjdk-17-jdk maven
```

**macOS (Homebrew):**
```bash
brew install openjdk@17 maven
```

**Windows:**
Install [Eclipse Temurin 17](https://adoptium.net/temurin/releases/?version=17) and
[Apache Maven](https://maven.apache.org/download.cgi), then add both to your PATH.

---

## FAQ

### Q: Does this replace manual code review?

**A:** No. This automates the mechanical parts of code review (formatting, common bugs) so human reviewers can focus on architecture, logic, and domain-specific concerns.

### Q: Why must I use JDK 17?

**A:** SpotBugs 4.8.3 crashes on newer JDKs (e.g. JDK 26) with an `FBClassReader`/ASM bytecode error.
Checkstyle and PMD work on newer JDKs, but to keep one consistent toolchain, run *all* analysis on
JDK 17: `JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 mvn ...`. In GitHub Actions, use
`actions/setup-java@v4` with `java-version: '17'` (distribution `temurin`). Note that your *project*
can still target a newer runtime; this constraint only applies to running the analysis tools.

### Q: Is this MISRA / formally certified?

**A:** No. This is inspired by the SEI CERT Oracle Coding Standard for Java but is not a formally
certified tool. For formal certification, use an accredited commercial analyzer.

### Q: How do I set up IDE integration?

**A:** Install the "Extension Pack for Java", open the project so the language server imports
`pom.xml`, and copy `vscode-settings.json.template` to `.vscode/settings.json`. See
`docs/java-ide-setup.md` for details.

### Q: How do I handle legacy code with many violations?

**A:** Options:
1. Fix violations incrementally (start with Critical only)
2. Use `@SuppressWarnings`/`@SuppressFBWarnings`/`// NOPMD` to suppress known violations in legacy files
3. Scope the plugins to only new modules/packages until the backlog is cleared

### Q: Can I contribute new rules?

**A:** Yes! Open a pull request with:
1. Rule description
2. Example compliant and non-compliant code
3. Mapping to a Checkstyle/PMD/SpotBugs check (if applicable)

---

## License

MIT License - Free for use in any project, commercial or open source.

---

## Support

- **Issues:** https://github.com/COG-GTM/-C-Code-Standards-Compliance-Framework/issues
- **Discussions:** https://github.com/COG-GTM/-C-Code-Standards-Compliance-Framework/discussions

---

**Made with ❤️ for safer Java code**
