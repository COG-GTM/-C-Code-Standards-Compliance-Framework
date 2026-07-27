"""
Coverage instrumentation for the compliance framework test suite.

This framework ships configuration files and shell scripts rather than an
importable library, so ordinary statement coverage tools have nothing to
attach to. Two coverage dimensions are tracked instead:

1. **Shell line coverage** - shell scripts are executed through a tracing
   wrapper (``BASH_XTRACEFD`` plus a ``PS4`` prefix carrying ``$LINENO``), so
   every line the script actually executes is recorded.
2. **Artifact coverage** - rules, clang-tidy checks and configuration/doc
   files that tests explicitly assert on. Tests declare what they cover with
   the ``covers`` fixture (see ``conftest.py``); a declaration only counts
   when the declaring test passes.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SHELL_SCRIPTS = (
    "scripts/validate.sh",
    "scripts/generate-compile-commands.sh",
)

TRACKED_FILES = (
    ".clang-format",
    ".clang-tidy",
    ".clangd",
    "rule-severity-mapping.yaml",
    "vscode-settings.json.template",
    "README.md",
    "docs/rule-reference.md",
    "docs/clangd-setup.md",
    "windsurf/c-safety-critical-rules.md",
    "examples/compliant.c",
    "examples/violations.c",
    "scripts/validate.sh",
    "scripts/generate-compile-commands.sh",
)


# =============================================================================
# Severity mapping helpers
# =============================================================================

def load_severity_mapping():
    """Parse rule-severity-mapping.yaml."""
    path = PROJECT_ROOT / "rule-severity-mapping.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def iter_rules(mapping):
    """Yield (severity_name, rule) pairs for every rule in the mapping."""
    for severity, level in mapping["severity_levels"].items():
        for rule in level.get("rules", []):
            yield severity, rule


def all_rule_ids(mapping):
    return [rule["rule_id"] for _, rule in iter_rules(mapping)]


def all_checks(mapping):
    """Every clang-tidy check referenced by the mapping, de-duplicated."""
    checks = []
    for _, rule in iter_rules(mapping):
        for check in rule.get("checks", []):
            if check not in checks:
                checks.append(check)
    return checks


def parse_jsonc(text):
    """Parse JSON with ``//`` comments, the dialect VS Code settings use."""
    cleaned = []
    for line in text.splitlines():
        in_string = False
        escaped = False
        for index, char in enumerate(line):
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
            elif char == '"':
                in_string = not in_string
            elif char == "/" and not in_string and line[index:index + 2] == "//":
                line = line[:index]
                break
        cleaned.append(line)
    return json.loads("\n".join(cleaned))


# =============================================================================
# Shell line coverage
# =============================================================================

TRACE_PREFIX = "+COVLINE:"

_STRUCTURAL_TOKENS = {
    "fi", "done", "else", "esac", "do", "then", "{", "}", ";;", ")", "))",
    "fi;", "EOF", "'", '"',
}

_CONTINUATION_ENDINGS = ("\\", "|", "&&", "||", ",")

_FUNCTION_HEADER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*\(\)\s*\{?$")
_HEREDOC_START = re.compile(r"<<-?\s*[\"']?([A-Za-z_][A-Za-z0-9_]*)[\"']?")


def executable_lines(script_path):
    """
    Best-effort set of line numbers in a shell script that can be executed.

    Blank lines, comments, here-doc bodies, structural keywords, function
    headers and continuation lines are excluded. Lines that turn out to be
    executed anyway are folded back in by :meth:`ShellCoverage.report`, so the
    metric never exceeds 100%.
    """
    lines = script_path.read_text(encoding="utf-8").splitlines()
    candidates = set()
    heredoc_terminator = None
    previous = ""

    for number, raw in enumerate(lines, start=1):
        stripped = raw.strip()

        if heredoc_terminator is not None:
            if stripped == heredoc_terminator:
                heredoc_terminator = None
            previous = ""
            continue

        heredoc = _HEREDOC_START.search(stripped)
        if heredoc:
            heredoc_terminator = heredoc.group(1)

        is_continuation = previous.endswith(_CONTINUATION_ENDINGS)
        previous = stripped.split("#")[0].strip() if not stripped.startswith("#") else ""

        if not stripped or stripped.startswith("#"):
            continue
        if stripped in _STRUCTURAL_TOKENS or is_continuation:
            continue
        if _FUNCTION_HEADER.match(stripped):
            continue
        is_block_opener = (
            stripped.startswith(("case ", "for ", "while ", "if ", "elif "))
            and stripped.endswith(("in", "do", "then"))
        )
        if is_block_opener:
            # The condition itself is traced; keep it.
            candidates.add(number)
            continue

        candidates.add(number)

    return candidates


@dataclass
class ShellCoverage:
    """Accumulates executed shell script lines across the test session."""

    executed: dict = field(default_factory=dict)

    def record_trace(self, trace_text):
        for line in trace_text.splitlines():
            marker = line.find(TRACE_PREFIX)
            if marker == -1:
                continue
            payload = line[marker + len(TRACE_PREFIX):]
            source, _, rest = payload.partition(":")
            lineno, _, _ = rest.partition(":")
            if not lineno.isdigit():
                continue
            name = _relative_script_name(source)
            if name is None:
                continue
            self.executed.setdefault(name, set()).add(int(lineno))

    def report(self):
        """Return {script: {"covered": int, "total": int, "percent": float}}."""
        result = {}
        for script in SHELL_SCRIPTS:
            path = PROJECT_ROOT / script
            if not path.exists():
                continue
            executed = self.executed.get(script, set())
            total_lines = executable_lines(path) | executed
            covered = len(executed & total_lines)
            total = len(total_lines)
            result[script] = {
                "covered": covered,
                "total": total,
                "percent": (100.0 * covered / total) if total else 0.0,
            }
        return result

    def total_percent(self):
        report = self.report()
        covered = sum(item["covered"] for item in report.values())
        total = sum(item["total"] for item in report.values())
        return (100.0 * covered / total) if total else 0.0


def _relative_script_name(source):
    """Map a traced BASH_SOURCE path back to a repo-relative script name."""
    normalized = source.replace("\\", "/").lower()
    for script in SHELL_SCRIPTS:
        if normalized.endswith(script.lower()):
            return script
    return None


def find_bash():
    """Locate a bash suitable for running the framework's scripts."""
    if sys.platform == "win32":
        # Prefer Git Bash: the System32 bash.exe shim launches WSL, which does
        # not share the Windows PATH (and therefore not clang-format).
        for candidate in (
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files\Git\usr\bin\bash.exe",
        ):
            if Path(candidate).exists():
                return candidate
        return None
    return shutil.which("bash")


def to_bash_path(path):
    """Convert a filesystem path to a form bash understands."""
    text = str(path)
    if sys.platform == "win32" and re.match(r"^[A-Za-z]:[\\/]", text):
        drive, rest = text[0].lower(), text[2:].replace("\\", "/")
        return f"/{drive}{rest}"
    return text


_WRAPPER = """#!/bin/bash
exec 9>>"$COVLINE_TRACE"
export BASH_XTRACEFD=9
export PS4='+COVLINE:${BASH_SOURCE}:${LINENO}:'
set -x
source "$COVLINE_SCRIPT" "$@"
"""


def run_script(script, args=(), cwd=None, coverage=None, env=None, timeout=300):
    """
    Run a framework shell script, recording executed lines when *coverage* is
    provided. Returns the :class:`subprocess.CompletedProcess`.
    """
    bash = find_bash()
    if bash is None:
        raise RuntimeError("bash is not available")

    script_path = PROJECT_ROOT / script
    workdir = tempfile.mkdtemp(prefix="shellcov-")
    wrapper_path = Path(workdir) / "wrapper.sh"
    wrapper_path.write_text(_WRAPPER, encoding="utf-8", newline="\n")
    trace_path = Path(workdir) / "trace.log"
    trace_path.write_text("", encoding="utf-8")

    child_env = dict(os.environ)
    child_env.update(env or {})
    child_env["COVLINE_TRACE"] = to_bash_path(trace_path)
    child_env["COVLINE_SCRIPT"] = to_bash_path(script_path)

    try:
        completed = subprocess.run(
            [bash, to_bash_path(wrapper_path), *[str(a) for a in args]],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=child_env,
            timeout=timeout,
        )
        if coverage is not None:
            coverage.record_trace(trace_path.read_text(encoding="utf-8", errors="replace"))
        return completed
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# =============================================================================
# Artifact coverage
# =============================================================================

@dataclass
class ArtifactCoverage:
    """Tracks which framework artifacts the passing tests assert on."""

    inventory: dict
    covered: set = field(default_factory=set)

    @classmethod
    def build(cls):
        mapping = load_severity_mapping()
        inventory = {
            "rule": [f"rule:{rule_id}" for rule_id in all_rule_ids(mapping)],
            "check": [f"check:{check}" for check in all_checks(mapping)],
            "file": [f"file:{name}" for name in TRACKED_FILES],
        }
        return cls(inventory=inventory)

    def add(self, artifact_ids):
        self.covered.update(artifact_ids)

    def report(self):
        result = {}
        for kind, items in self.inventory.items():
            covered = [item for item in items if item in self.covered]
            result[kind] = {
                "covered": len(covered),
                "total": len(items),
                "percent": (100.0 * len(covered) / len(items)) if items else 0.0,
                "missing": sorted(item for item in items if item not in self.covered),
            }
        return result

    def total_percent(self):
        report = self.report()
        covered = sum(item["covered"] for item in report.values())
        total = sum(item["total"] for item in report.values())
        return (100.0 * covered / total) if total else 0.0

    def unknown_declarations(self):
        """Declared artifacts that are not part of the inventory (typos)."""
        known = {item for items in self.inventory.values() for item in items}
        return sorted(self.covered - known)


def write_summary(path, shell_coverage, artifact_coverage, extra=None):
    payload = {
        "shell_line_coverage": shell_coverage.report(),
        "shell_line_coverage_percent": round(shell_coverage.total_percent(), 2),
        "artifact_coverage": artifact_coverage.report(),
        "artifact_coverage_percent": round(artifact_coverage.total_percent(), 2),
    }
    payload.update(extra or {})
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
