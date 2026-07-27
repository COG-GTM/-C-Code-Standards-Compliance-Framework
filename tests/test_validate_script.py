"""
Behavioural tests for scripts/validate.sh.

The script is the entry point CI and developers use, so its documented exit
codes (0 clean, 1 formatting, 2 analysis, 3 both) and its --fix mode are
exercised end to end against throwaway projects.
"""

import pytest

from tests.conftest import (
    PROJECT_ROOT,
    requires_bash,
    requires_clang_format,
    requires_clang_tidy,
)

pytestmark = [requires_bash, requires_clang_format, requires_clang_tidy]

SCRIPT = "scripts/validate.sh"

COMPLIANT_SOURCE = """\
#include <stdio.h>

int add_numbers(int left, int right)
{
    return left + right;
}

int main(void)
{
    printf("%d\\n", add_numbers(1, 2));
    return 0;
}
"""

BADLY_FORMATTED_SOURCE = """\
#include <stdio.h>

int add_numbers(int left, int right) {
        return left+right;
}

int main(void) {
  printf("%d\\n", add_numbers(1, 2));
  return 0;
}
"""

# Unchecked malloc plus a leak: bugprone-unused-return-value and
# clang-analyzer-unix.Malloc are both promoted to errors by .clang-tidy.
CRITICAL_SOURCE = """\
#include <stdlib.h>
#include <string.h>

int main(void)
{
    char *buffer = malloc(64);
    strcpy(buffer, "leaked");
    return 0;
}
"""


@pytest.fixture
def workspace(c_workspace):
    return c_workspace


class TestExitCodes:
    """The exit code contract documented in the script header."""

    def test_clean_project_passes(self, workspace, run_script, covers):
        covers("file:scripts/validate.sh")
        workspace.write("clean.c", COMPLIANT_SOURCE)

        result = run_script(SCRIPT, ["."], cwd=workspace.path)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "All checks passed" in result.stdout

    def test_format_violation_returns_one(self, workspace, run_script, covers):
        covers("file:scripts/validate.sh", "rule:Rule 40")
        workspace.write("ugly.c", BADLY_FORMATTED_SOURCE)

        result = run_script(SCRIPT, ["."], cwd=workspace.path)

        assert result.returncode == 1, result.stdout + result.stderr
        assert "needs formatting" in result.stdout
        assert "Run with --fix to auto-format" in result.stdout

    def test_critical_analysis_violation_returns_two(self, workspace, run_script, covers):
        covers("file:scripts/validate.sh", "rule:Rule 23")
        workspace.write("leak.c", CRITICAL_SOURCE)

        result = run_script(SCRIPT, ["."], cwd=workspace.path)

        assert result.returncode == 2, result.stdout + result.stderr
        assert "critical issues" in result.stdout

    def test_format_and_analysis_violations_return_three(self, workspace, run_script, covers):
        covers("file:scripts/validate.sh")
        workspace.write("ugly.c", BADLY_FORMATTED_SOURCE)
        workspace.write("leak.c", CRITICAL_SOURCE)

        result = run_script(SCRIPT, ["."], cwd=workspace.path)

        assert result.returncode == 3, result.stdout + result.stderr
        assert "Validation failed (exit code: 3)" in result.stdout

    def test_empty_project_is_not_an_error(self, workspace, run_script):
        result = run_script(SCRIPT, ["."], cwd=workspace.path)

        assert result.returncode == 0
        assert "No C/C++ files found" in result.stdout


class TestArgumentHandling:
    """Directory and flag parsing."""

    def test_defaults_to_current_directory(self, workspace, run_script):
        workspace.write("clean.c", COMPLIANT_SOURCE)

        result = run_script(SCRIPT, [], cwd=workspace.path)

        assert result.returncode == 0
        assert "Target directory: ." in result.stdout

    def test_scans_the_requested_subdirectory_only(self, workspace, run_script):
        workspace.write("src/clean.c", COMPLIANT_SOURCE)
        workspace.write("legacy/ugly.c", BADLY_FORMATTED_SOURCE)

        result = run_script(SCRIPT, ["src"], cwd=workspace.path)

        assert result.returncode == 0, result.stdout
        assert "ugly.c" not in result.stdout

    def test_unknown_argument_falls_back_to_current_directory(self, workspace, run_script):
        workspace.write("clean.c", COMPLIANT_SOURCE)

        result = run_script(SCRIPT, ["does-not-exist"], cwd=workspace.path)

        assert result.returncode == 0
        assert "Target directory: ." in result.stdout

    def test_build_and_vendor_directories_are_skipped(self, workspace, run_script):
        workspace.write("clean.c", COMPLIANT_SOURCE)
        workspace.write("build/generated.c", BADLY_FORMATTED_SOURCE)
        workspace.write("third_party/lib.c", BADLY_FORMATTED_SOURCE)
        workspace.write("vendor/dep.c", BADLY_FORMATTED_SOURCE)

        result = run_script(SCRIPT, ["."], cwd=workspace.path)

        assert result.returncode == 0, result.stdout
        for excluded in ("generated.c", "lib.c", "dep.c"):
            assert excluded not in result.stdout

    def test_headers_are_formatted_but_not_analysed(self, workspace, run_script):
        workspace.write("api.h", "int add_numbers(int left, int right);\n")

        result = run_script(SCRIPT, ["."], cwd=workspace.path)

        assert result.returncode == 0, result.stdout
        assert "No source files to analyze (headers only)" in result.stdout


class TestFixMode:
    """--fix rewrites files in place instead of reporting failures."""

    def test_fix_mode_formats_the_file(self, workspace, run_script, covers):
        covers("file:scripts/validate.sh", "rule:Rule 40")
        workspace.write("ugly.c", BADLY_FORMATTED_SOURCE)

        result = run_script(SCRIPT, [".", "--fix"], cwd=workspace.path)

        assert "Fix mode: true" in result.stdout
        assert "Formatted: ./ugly.c" in result.stdout

        formatted = workspace.read("ugly.c")
        assert "int add_numbers(int left, int right)\n{" in formatted, \
            "--fix must apply Allman braces"
        assert "return left + right;" in formatted

    def test_fix_mode_is_idempotent(self, workspace, run_script):
        workspace.write("ugly.c", BADLY_FORMATTED_SOURCE)

        run_script(SCRIPT, [".", "--fix"], cwd=workspace.path)
        once = workspace.read("ugly.c")
        run_script(SCRIPT, [".", "--fix"], cwd=workspace.path)

        assert workspace.read("ugly.c") == once

    def test_fixed_project_then_passes_validation(self, workspace, run_script):
        workspace.write("ugly.c", BADLY_FORMATTED_SOURCE)

        run_script(SCRIPT, [".", "--fix"], cwd=workspace.path)
        result = run_script(SCRIPT, ["."], cwd=workspace.path)

        assert result.returncode == 0, result.stdout

    def test_fix_flag_order_does_not_matter(self, workspace, run_script):
        workspace.write("src/ugly.c", BADLY_FORMATTED_SOURCE)

        result = run_script(SCRIPT, ["--fix", "src"], cwd=workspace.path)

        assert "Fix mode: true" in result.stdout
        assert "Target directory: src" in result.stdout


class TestReporting:
    """Human readable output used by developers and CI logs."""

    def test_reports_the_number_of_files_found(self, workspace, run_script):
        workspace.write("a.c", COMPLIANT_SOURCE)
        workspace.write("b.c", COMPLIANT_SOURCE)

        result = run_script(SCRIPT, ["."], cwd=workspace.path)

        assert "Found 2 file(s) to check" in result.stdout

    def test_warnings_do_not_fail_the_run(self, workspace, run_script, covers):
        covers("file:scripts/validate.sh", "rule:Rule 46")
        # An unused parameter is a Minor rule: warn, but do not block.
        workspace.write(
            "warn.c",
            "int add_numbers(int left, int unused_right)\n"
            "{\n"
            "    return left;\n"
            "}\n",
        )

        result = run_script(SCRIPT, ["."], cwd=workspace.path)

        assert result.returncode == 0, result.stdout
        assert "warnings" in result.stdout

    def test_summary_lists_both_stages(self, workspace, run_script):
        workspace.write("clean.c", COMPLIANT_SOURCE)

        result = run_script(SCRIPT, ["."], cwd=workspace.path)

        assert "clang-format check" in result.stdout
        assert "clang-tidy analysis" in result.stdout
        assert "Format:   OK" in result.stdout
        assert "Analysis:" in result.stdout

    def test_uses_the_framework_config_not_llvm_defaults(self, workspace, run_script):
        # LLVM defaults would accept K&R braces; the framework config must not.
        (workspace.path / ".clang-format").unlink()
        workspace.write("ugly.c", BADLY_FORMATTED_SOURCE)

        result = run_script(SCRIPT, ["."], cwd=workspace.path)

        assert result.returncode == 1, (
            "validate.sh must fall back to the framework .clang-format at "
            f"{PROJECT_ROOT} when the project has none"
        )
