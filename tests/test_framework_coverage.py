"""
Tests for the coverage collector in tests/framework_coverage.py.

The collector decides whether the suite is honest about what it exercises, so
its parsers and accounting are tested directly.
"""

import json

import pytest

from tests import framework_coverage as fc


class TestExecutableLines:
    """Static estimate of which shell lines can be executed."""

    def test_skips_comments_and_blank_lines(self, tmp_path):
        script = tmp_path / "sample.sh"
        script.write_text(
            "#!/bin/bash\n"
            "\n"
            "# a comment\n"
            "echo hello\n",
            encoding="utf-8",
        )
        assert fc.executable_lines(script) == {4}

    def test_skips_structural_keywords_and_function_headers(self, tmp_path):
        script = tmp_path / "sample.sh"
        script.write_text(
            "run()\n"
            "{\n"
            "    if [ -n \"$1\" ]; then\n"
            "        echo yes\n"
            "    else\n"
            "        echo no\n"
            "    fi\n"
            "}\n",
            encoding="utf-8",
        )
        assert fc.executable_lines(script) == {3, 4, 6}

    def test_skips_heredoc_bodies(self, tmp_path):
        script = tmp_path / "sample.sh"
        script.write_text(
            "cat > out.json << EOF\n"
            "{\n"
            '  "key": "value"\n'
            "}\n"
            "EOF\n"
            "echo done\n",
            encoding="utf-8",
        )
        assert fc.executable_lines(script) == {1, 6}

    def test_joins_backslash_continuations(self, tmp_path):
        script = tmp_path / "sample.sh"
        script.write_text(
            "find . \\\n"
            "    -name '*.c' \\\n"
            "    -print\n"
            "echo done\n",
            encoding="utf-8",
        )
        assert fc.executable_lines(script) == {1, 4}


class TestShellCoverage:
    """Accounting over traced line numbers."""

    def test_unexecuted_script_reports_zero(self):
        coverage = fc.ShellCoverage()
        report = coverage.report()
        assert set(report) == set(fc.SHELL_SCRIPTS)
        assert all(item["covered"] == 0 for item in report.values())
        assert coverage.total_percent() == 0.0

    def test_records_traced_lines(self):
        coverage = fc.ShellCoverage()
        coverage.record_trace(
            "+COVLINE:/c/repo/scripts/validate.sh:10:echo hi\n"
            "+COVLINE:/c/repo/scripts/validate.sh:11:echo ho\n"
        )
        assert coverage.executed["scripts/validate.sh"] == {10, 11}

    def test_ignores_untracked_and_malformed_trace_lines(self):
        coverage = fc.ShellCoverage()
        coverage.record_trace(
            "+ echo not-a-trace-marker\n"
            "+COVLINE:/tmp/other.sh:3:echo hi\n"
            "+COVLINE:/c/repo/scripts/validate.sh:notanumber:echo hi\n"
        )
        assert coverage.executed == {}

    def test_percentage_never_exceeds_one_hundred(self):
        coverage = fc.ShellCoverage()
        # Line 1 is the shebang: never "executable", but fold it in anyway.
        coverage.record_trace("+COVLINE:/c/repo/scripts/validate.sh:1:x\n")
        assert 0 < coverage.report()["scripts/validate.sh"]["percent"] <= 100


class TestArtifactCoverage:
    """Declaration-based coverage of rules, checks and shipped files."""

    def test_inventory_matches_the_mapping(self):
        artifacts = fc.ArtifactCoverage.build()
        mapping = fc.load_severity_mapping()
        assert artifacts.inventory["rule"] == [
            f"rule:{rule_id}" for rule_id in fc.all_rule_ids(mapping)
        ]
        assert artifacts.inventory["check"] == [
            f"check:{check}" for check in fc.all_checks(mapping)
        ]

    def test_declarations_increase_coverage(self):
        artifacts = fc.ArtifactCoverage.build()
        before = artifacts.report()["file"]["covered"]
        artifacts.add(["file:README.md"])
        assert artifacts.report()["file"]["covered"] == before + 1

    def test_unknown_declarations_are_flagged(self):
        artifacts = fc.ArtifactCoverage.build()
        artifacts.add(["rule:Rule 999", "file:README.md"])
        assert list(artifacts.unknown_declarations()) == ["rule:Rule 999"]

    def test_missing_artifacts_are_listed(self):
        artifacts = fc.ArtifactCoverage.build()
        report = artifacts.report()
        assert "file:README.md" in report["file"]["missing"]
        assert report["file"]["percent"] == 0.0


class TestSummaryArtifact:
    """The JSON summary consumed by CI."""

    def test_summary_contains_both_metrics(self, tmp_path):
        shell = fc.ShellCoverage()
        artifacts = fc.ArtifactCoverage.build()
        artifacts.add(["file:README.md"])

        target = tmp_path / "summary.json"
        payload = fc.write_summary(target, shell, artifacts, extra={"tests": 1})

        written = json.loads(target.read_text(encoding="utf-8"))
        assert written == payload
        assert payload["tests"] == 1
        assert payload["artifact_coverage"]["file"]["covered"] == 1
        assert payload["shell_line_coverage_percent"] == 0.0


class TestMappingHelpers:
    """Loaders shared by the rest of the suite."""

    def test_iter_rules_yields_severity_and_rule(self, severity_mapping):
        pairs = list(fc.iter_rules(severity_mapping))
        assert pairs, "Mapping must contain rules"
        assert {severity for severity, _ in pairs} == set(severity_mapping["severity_levels"])
        assert all("rule_id" in rule for _, rule in pairs)

    def test_checks_are_deduplicated(self, severity_mapping):
        checks = fc.all_checks(severity_mapping)
        assert len(checks) == len(set(checks))


class TestJsoncParser:
    """VS Code settings use JSON with comments."""

    def test_strips_line_comments(self):
        assert fc.parse_jsonc('{\n  // comment\n  "a": 1\n}') == {"a": 1}

    def test_strips_trailing_comments(self):
        assert fc.parse_jsonc('{"a": 1 // why\n}') == {"a": 1}

    def test_preserves_double_slashes_inside_strings(self):
        assert fc.parse_jsonc('{"url": "https://example.com"}') == {
            "url": "https://example.com"
        }

    def test_preserves_escaped_quotes(self):
        assert fc.parse_jsonc(r'{"quote": "a \" // b"}') == {"quote": 'a " // b'}

    def test_rejects_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            fc.parse_jsonc("{not json}")
