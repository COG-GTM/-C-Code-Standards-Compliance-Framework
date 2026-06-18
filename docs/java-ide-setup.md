# Java Language Server Setup Guide for Windsurf/VSCode

> **Complete guide to setting up the Java language server for intelligent Java development.**

---

## What is the Java Language Server?

The **Java language server** — Eclipse **JDT Language Server (JDT.LS)**, packaged by Red Hat as
**"Language Support for Java"** and bundled in the VS Code **"Extension Pack for Java"** — provides
IDE features for Java:

| Feature | Description |
|---------|-------------|
| **Code Completion** | Intelligent suggestions based on context |
| **Go to Definition** | Jump to class/method/field definitions |
| **Find References** | Find all usages of a symbol |
| **Diagnostics** | Real-time error and warning detection |
| **Hover Information** | Javadoc and type info on hover |
| **Code Formatting** | Auto-format using a Java formatter profile |
| **Inlay Hints** | Show parameter names and inferred types inline |
| **Rename Symbol** | Safely rename across files |

The language server compiles your code with the same `javac` semantics your build uses, so its
diagnostics match what you'll see at compile time.

> **Coming from C/C++:** this is the Java equivalent of **clangd**. Where clangd needed a
> `compile_commands.json` to learn how each file is compiled, the Java language server reads your
> **`pom.xml`** (the Maven project model) to learn the classpath, source roots, and dependencies.
> There is no `compile_commands.json` in Java.

---

## Quick Setup

### Step 1: Install JDK 17

The analysis tools in this framework run on **JDK 17**. SpotBugs crashes on newer JDKs
(e.g. JDK 26) with an `FBClassReader`/ASM error, so standardize on 17.

**macOS (Homebrew):**
```bash
brew install openjdk@17
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y openjdk-17-jdk maven
```

**Windows:**
Install [Eclipse Temurin 17](https://adoptium.net/temurin/releases/?version=17) and add it to PATH.

**Pin JAVA_HOME to 17** (the VM's default `java` may be newer):
```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
java -version   # should report 17.x
```

If that path is absent, locate a JDK 17 with `ls /usr/lib/jvm`, `update-java-alternatives -l`,
or install `temurin-17` / `openjdk-17`, then point `JAVA_HOME` at it.

### Step 2: Install the Extension Pack for Java

In Windsurf/VSCode, install the **Extension Pack for Java**:
- Extension ID: `vscjava.vscode-java-pack`

This bundles Red Hat's **Language Support for Java** (`redhat.java`, the JDT.LS front-end),
the debugger, the Maven helper, and the test runner. Optionally add the analysis extensions so
their findings appear inline:

| Extension | ID | Surfaces |
|-----------|----|----------|
| Checkstyle for Java | `shengchen.vscode-checkstyle` | `checkstyle.xml` violations |
| PMD (any maintained PMD extension) | — | `pmd-ruleset.xml` violations |
| SpotBugs (via SpotBugs/SonarLint-style extension) | — | SpotBugs bug patterns |

> **Note for Windsurf:** if a specific marketplace extension isn't available, the language server
> still works — JDT.LS speaks the Language Server Protocol directly. Just ensure JDK 17 is on PATH
> and the project has a valid `pom.xml`.

### Step 3: Open the Project (pom.xml is the project model)

There is **no separate database to generate** (unlike `compile_commands.json` for clangd). Simply
open the project folder. The language server detects `pom.xml`, imports the Maven project, resolves
dependencies, and indexes your sources:

```bash
# this framework already ships a pom.xml at the repo root
code .   # or open the folder in Windsurf
```

Watch the status bar for "Importing Maven project…". When it finishes, autocomplete and navigation
are ready. If you change `pom.xml`, run **"Java: Reload Projects"** from the Command Palette.

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
  "java.configuration.updateBuildConfiguration": "automatic",
  "java.format.settings.profile": "GoogleStyle",
  "[java]": {
    "editor.formatOnSave": true,
    "editor.tabSize": 4,
    "editor.insertSpaces": true
  },
  "java.checkstyle.configuration": "${workspaceFolder}/checkstyle.xml",
  "java.checkstyle.version": "10.12.7"
}
```

### Step 5: Point the IDE at JDK 17

Tell the language server which JDK to use for the project (and for running the analysis):

```json
{
  "java.configuration.runtimes": [
    {
      "name": "JavaSE-17",
      "path": "/usr/lib/jvm/java-17-openjdk-amd64",
      "default": true
    }
  ]
}
```

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                     Your Editor (Windsurf/VSCode)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐    ┌─────────────────────┐                   │
│   │  Your Java  │    │  Language Server    │                   │
│   │ Source Code │◄──►│  Protocol (LSP)     │                   │
│   └─────────────┘    └──────────┬──────────┘                   │
│                                 │                               │
│                                 ▼                               │
│                      ┌──────────────────────┐                  │
│                      │  Java Language Server │                 │
│                      │  (Eclipse JDT.LS)     │                 │
│                      └──────────┬───────────┘                  │
│                                 │                               │
│              ┌──────────────────┼──────────────────┐           │
│              │                  │                  │           │
│              ▼                  ▼                  ▼           │
│   ┌─────────────────┐  ┌──────────────┐  ┌──────────────┐     │
│   │    pom.xml      │  │ checkstyle   │  │ pmd-ruleset  │     │
│   │ (project model) │  │ .xml         │  │ .xml +       │     │
│   │                 │  │              │  │ spotbugs     │     │
│   └─────────────────┘  └──────────────┘  └──────────────┘     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

The language server reads `pom.xml` for the classpath/sources; the Checkstyle/PMD/SpotBugs
extensions read the rule configs and overlay their findings on the same editor.

---

## Configuration Files Reference

### pom.xml

The Maven project model. The language server reads it to resolve the classpath, source directories,
the `maven.compiler.release` level, and dependencies — the role `compile_commands.json` played for
clangd. The same file declares the Checkstyle/PMD/SpotBugs plugins so the command line, CI, and IDE
all agree.

### checkstyle.xml

Drives style/naming/brace diagnostics. Point the Checkstyle extension at it:
```json
{
  "java.checkstyle.configuration": "${workspaceFolder}/checkstyle.xml",
  "java.checkstyle.version": "10.12.7"
}
```

### pmd-ruleset.xml / spotbugs-exclude.xml

Drive the PMD and SpotBugs analysis (PMD 6 ruleset syntax; SpotBugs exclusion filter). Run them
through Maven so the IDE and CI report identical findings:
```bash
JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 mvn pmd:check spotbugs:check
```

---

## Troubleshooting

### Language server not starting

1. Check the JDK: `java -version` (must be 17 for analysis)
2. Command Palette → **"Java: Open All Log Files"** to inspect the JDT.LS log
3. Command Palette → **"Java: Clean Java Language Server Workspace"** to rebuild the index

### No IntelliSense / completions

1. Ensure a valid `pom.xml` exists at the project root
2. Wait for "Importing Maven project…" to finish in the status bar
3. Command Palette → **"Java: Reload Projects"**

### Incorrect errors/warnings

1. Reload projects after editing `pom.xml`
2. Confirm `java.configuration.runtimes` points at JDK 17
3. Verify dependencies resolved (no red entries under **Maven** in the Explorer)

### SpotBugs fails or crashes

SpotBugs **must run on JDK 17**. On a newer JDK it throws an `FBClassReader`/ASM error. Run:
```bash
JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 mvn spotbugs:check
```

### Checkstyle/PMD diagnostics not appearing

1. Confirm the Checkstyle/PMD extension is installed and enabled
2. Confirm `java.checkstyle.configuration` points at `checkstyle.xml`
3. Reload the window (Command Palette → **"Developer: Reload Window"**)

---

## Advanced Configuration

### Per-project formatter profile

Export an Eclipse formatter profile and reference it:
```json
{
  "java.format.settings.url": "${workspaceFolder}/eclipse-formatter.xml",
  "java.format.settings.profile": "Framework"
}
```

### Organize imports on save

```json
{
  "editor.codeActionsOnSave": {
    "source.organizeImports": "explicit"
  }
}
```

### Null analysis

```json
{
  "java.compile.nullAnalysis.mode": "automatic"
}
```

---

## Integration with This Framework

This framework is pre-configured to work with the Java language server:

| File | Purpose |
|------|---------|
| `pom.xml` | Maven project model + Checkstyle/PMD/SpotBugs plugins |
| `checkstyle.xml` | Style/naming/brace rules |
| `pmd-ruleset.xml` | PMD bug/design rules |
| `spotbugs-exclude.xml` | SpotBugs exclusion filter |
| `vscode-settings.json.template` | VSCode/Windsurf settings template |

The configurations are aligned, so:
- **Diagnostics** shown in your editor match the Maven Checkstyle/PMD/SpotBugs CI checks
- **Formatting** matches the project's Java style profile
- **Severity** classification aligns with the framework's rules

---

## Resources

- [Language Support for Java (Red Hat)](https://marketplace.visualstudio.com/items?itemName=redhat.java)
- [Extension Pack for Java](https://marketplace.visualstudio.com/items?itemName=vscjava.vscode-java-pack)
- [Eclipse JDT Language Server](https://github.com/eclipse-jdtls/eclipse.jdt.ls)
- [Checkstyle for Java (VS Code)](https://marketplace.visualstudio.com/items?itemName=shengchen.vscode-checkstyle)
- [SpotBugs Documentation](https://spotbugs.readthedocs.io/)
- [PMD Documentation](https://docs.pmd-code.org/)
