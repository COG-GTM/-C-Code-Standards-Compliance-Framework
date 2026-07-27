"""
Tests for the reference example files.

examples/compliant.c is the "golden" file every consuming project is pointed
at, and examples/violations.c is the detection fixture, so both are checked
against the real tooling rather than by string matching alone.
"""

import re
import subprocess

import pytest

from tests import framework_coverage as fc
from tests.conftest import (
    EXAMPLES_DIR,
    PROJECT_ROOT,
    clang_tidy_output,
    requires_clang_format,
    requires_clang_tidy,
)

MAPPING = fc.load_severity_mapping()

COMPLIANT = EXAMPLES_DIR / "compliant.c"
VIOLATIONS = EXAMPLES_DIR / "violations.c"

COMPLIANT_TEXT = COMPLIANT.read_text(encoding="utf-8")
VIOLATIONS_TEXT = VIOLATIONS.read_text(encoding="utf-8")

# Rules the violations file advertises in its own summary output.
ADVERTISED_VIOLATIONS = re.findall(r"- (Rule \d+):", VIOLATIONS_TEXT)

# Known gaps in examples/compliant.c, pinned so that they cannot grow
# silently and so that fixing them makes the guarding test fail loudly.
#
# compliant.c logs diagnostics with fprintf(stderr, ...) without checking the
# return value, which cert-err33-c reports as an error under this config.
COMPLIANT_KNOWN_ERROR_CHECKS = {"cert-err33-c", "bugprone-unused-return-value"}

# compliant.c hand-aligns declarations and enum initialisers, which
# clang-format re-flows. The example is readable but not byte-identical to
# what the shipped .clang-format produces.
COMPLIANT_IS_CLANG_FORMAT_CLEAN = False


def strip_whitespace(text):
    """Reduce source to its token stream so only structural edits show up."""
    return re.sub(r"\s+", "", text)


class TestCompliantExample:
    """examples/compliant.c must actually satisfy the standard."""

    def test_uses_allman_braces(self, covers):
        covers("file:examples/compliant.c", "rule:Rule 40")
        # A brace opening on the same line as a control statement or function
        # signature would be K&R style.
        offenders = [
            line
            for line in COMPLIANT_TEXT.splitlines()
            if re.search(r"^\s*(if|for|while|switch|else)\b.*\{\s*$", line)
            or re.search(r"^\w[\w \*]+\([^;]*\)\s*\{\s*$", line)
        ]
        assert not offenders, f"Non-Allman braces: {offenders}"

    def test_uses_spaces_not_tabs(self, covers):
        covers("file:examples/compliant.c", "rule:Rule 40")
        assert "\t" not in COMPLIANT_TEXT

    def test_respects_the_column_limit(self, clang_format_config, covers):
        covers("file:examples/compliant.c")
        limit = clang_format_config["ColumnLimit"]
        too_long = [
            (number, line)
            for number, line in enumerate(COMPLIANT_TEXT.splitlines(), start=1)
            if len(line) > limit
        ]
        assert not too_long, f"Lines exceeding {limit} columns: {too_long}"

    def test_constants_and_types_follow_rule_41(self, covers):
        covers("file:examples/compliant.c", "rule:Rule 41")
        macros = re.findall(r"^#define\s+([A-Za-z_][A-Za-z0-9_]*)", COMPLIANT_TEXT, re.M)
        assert macros, "compliant.c should demonstrate constants"
        assert all(name.isupper() for name in macros), f"Macros must be UPPER_CASE: {macros}"

        types = re.findall(r"^\}\s*([A-Za-z_][A-Za-z0-9_]*);", COMPLIANT_TEXT, re.M)
        assert types, "compliant.c should demonstrate typedefs"
        assert all(name[0].isupper() for name in types), f"Types must be CamelCase: {types}"

    def test_functions_follow_rule_41(self, covers):
        covers("file:examples/compliant.c", "rule:Rule 41")
        definitions = re.findall(r"^[a-zA-Z_][\w \*]*?\b(\w+)\([^;]*\)\s*$", COMPLIANT_TEXT, re.M)
        bad = [name for name in definitions if name != name.lower()]
        assert not bad, f"Function names must be lower_case: {bad}"

    def test_every_malloc_has_a_matching_free(self, covers):
        covers("file:examples/compliant.c", "rule:Rule 23")
        allocations = len(re.findall(r"\b(malloc|calloc|realloc)\s*\(", COMPLIANT_TEXT))
        releases = len(re.findall(r"\bfree\s*\(", COMPLIANT_TEXT))
        assert allocations > 0, "compliant.c should demonstrate allocation"
        assert releases >= allocations, "Every allocation needs a matching free"

    def test_pointers_are_nulled_after_free(self, covers):
        covers("file:examples/compliant.c", "rule:Rule 24")
        assert re.search(r"free\([^)]+\);\s*\n\s*\w+\s*=\s*NULL;", COMPLIANT_TEXT), \
            "compliant.c must demonstrate NULLing pointers after free"

    def test_documents_the_rules_it_demonstrates(self, covers):
        covers("file:examples/compliant.c")
        referenced = set(re.findall(r"Rule \d+", COMPLIANT_TEXT))
        assert len(referenced) >= 8, \
            f"compliant.c should annotate the rules it demonstrates, found {referenced}"

    def test_has_a_main_entry_point(self, covers):
        covers("file:examples/compliant.c")
        assert re.search(r"^int main\(void\)$", COMPLIANT_TEXT, re.M)

    @requires_clang_format
    def test_clang_format_cleanliness_matches_expectation(self, covers):
        covers("file:examples/compliant.c", "file:.clang-format", "rule:Rule 40")
        completed = subprocess.run(
            ["clang-format", "--dry-run", "--Werror",
             f"--style=file:{PROJECT_ROOT / '.clang-format'}", str(COMPLIANT)],
            capture_output=True,
            text=True,
        )
        is_clean = completed.returncode == 0
        assert is_clean == COMPLIANT_IS_CLANG_FORMAT_CLEAN, (
            "compliant.c is now clang-format clean - flip "
            "COMPLIANT_IS_CLANG_FORMAT_CLEAN to True"
            if is_clean else
            "compliant.c drifted further from .clang-format:\n" + completed.stderr
        )

    @requires_clang_format
    def test_clang_format_differences_are_whitespace_only(self, covers):
        covers("file:examples/compliant.c", "file:.clang-format")
        completed = subprocess.run(
            ["clang-format", f"--style=file:{PROJECT_ROOT / '.clang-format'}",
             str(COMPLIANT)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert strip_whitespace(completed.stdout) == strip_whitespace(COMPLIANT_TEXT), (
            "clang-format wants to restructure compliant.c, not merely adjust "
            "its whitespace"
        )

    @requires_clang_tidy
    def test_only_known_error_level_checks_fire(self, covers):
        covers("file:examples/compliant.c", "file:.clang-tidy", "rule:Rule 20")
        output = clang_tidy_output(COMPLIANT)
        firing = {
            check
            for line in output.splitlines() if " error: " in line
            for check in re.findall(r"[\[,]([a-z][a-z0-9-]+(?:\.[A-Za-z0-9_.]+)*)[,\]]", line)
            if check != "-warnings-as-errors"
        }
        unexpected = firing - COMPLIANT_KNOWN_ERROR_CHECKS
        assert not unexpected, (
            f"compliant.c triggers unexpected error-level checks: {sorted(unexpected)}"
        )

    @requires_clang_tidy
    def test_no_memory_safety_diagnostics(self, covers):
        covers("file:examples/compliant.c", "rule:Rule 23", "rule:Rule 24")
        output = clang_tidy_output(COMPLIANT)
        for check in (
            "clang-analyzer-unix.Malloc",
            "clang-analyzer-core.NullDereference",
            "bugprone-double-free",
        ):
            assert check not in output, \
                f"compliant.c must not trigger {check}"


class TestViolationsExample:
    """examples/violations.c is the detection fixture for the rule set."""

    def test_warns_that_it_is_intentionally_broken(self, covers):
        covers("file:examples/violations.c")
        header = VIOLATIONS_TEXT[:600]
        assert "WARNING" in header
        assert "DO NOT use this code in production" in header

    @pytest.mark.parametrize("rule_id", sorted(set(ADVERTISED_VIOLATIONS)))
    def test_advertised_rule_has_a_violating_function(self, rule_id, covers):
        covers("file:examples/violations.c", f"rule:{rule_id}")
        number = rule_id.split()[1]
        assert re.search(rf"rule_{number}_violation|Rule {number} VIOLATION", VIOLATIONS_TEXT), \
            f"{rule_id} is advertised but has no violating function"

    @pytest.mark.parametrize("rule_id", sorted(set(ADVERTISED_VIOLATIONS)))
    def test_advertised_rule_exists_in_the_mapping(self, rule_id, covers):
        covers("file:examples/violations.c", f"rule:{rule_id}")
        assert rule_id in fc.all_rule_ids(MAPPING), \
            f"{rule_id} is demonstrated but missing from rule-severity-mapping.yaml"

    def test_every_violating_function_names_its_expected_checks(self, covers):
        covers("file:examples/violations.c")
        blocks = re.findall(
            r"/\*\*(.*?)\*/\s*\n[^\n]*rule_(\d+)_violation", VIOLATIONS_TEXT, re.S
        )
        assert blocks, "Violating functions must be documented"

        undocumented = [
            number for comment, number in blocks
            if "Expected clang-tidy warnings" not in comment
            and "clang-format issue" not in comment
        ]
        assert not undocumented, \
            f"Functions without expected-warning documentation: {undocumented}"

    def test_covers_every_critical_rule(self, covers):
        covers("file:examples/violations.c")
        critical_ids = [
            rule["rule_id"]
            for severity, rule in fc.iter_rules(MAPPING)
            if severity == "critical"
        ]
        missing = [
            rule_id for rule_id in critical_ids
            if f"{rule_id} VIOLATION" not in VIOLATIONS_TEXT
        ]
        assert not missing, f"violations.c must demonstrate every critical rule, missing {missing}"

    @requires_clang_tidy
    def test_clang_tidy_reports_errors_for_critical_violations(self, covers):
        covers("file:examples/violations.c", "file:.clang-tidy")
        output = clang_tidy_output(VIOLATIONS)
        assert " error: " in output, \
            "Critical violations must be reported as errors, not warnings"

    @requires_clang_tidy
    @pytest.mark.parametrize(
        "check",
        [
            "bugprone-unused-return-value",
            "clang-analyzer-unix.Malloc",
            "readability-braces-around-statements",
            "readability-else-after-return",
            "misc-unused-parameters",
        ],
    )
    def test_expected_check_fires(self, check, covers):
        covers("file:examples/violations.c", f"check:{check}")
        output = clang_tidy_output(VIOLATIONS)
        assert check in output, f"{check} should fire on violations.c"

    @requires_clang_format
    def test_is_not_formatted(self, covers):
        covers("file:examples/violations.c", "rule:Rule 40")
        completed = subprocess.run(
            ["clang-format", "--dry-run", "--Werror",
             f"--style=file:{PROJECT_ROOT / '.clang-format'}", str(VIOLATIONS)],
            capture_output=True,
            text=True,
        )
        assert completed.returncode != 0, \
            "violations.c is expected to contain the Rule 40 brace-style violation"
