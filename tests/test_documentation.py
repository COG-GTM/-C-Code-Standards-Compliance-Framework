"""
Documentation tests.

The rule set is only enforceable if every rule is documented consistently
across the reference docs, the README and the Windsurf ruleset that the AI
assistant reads.
"""

import re

import pytest

from tests import framework_coverage as fc
from tests.conftest import DOCS_DIR, PROJECT_ROOT

MAPPING = fc.load_severity_mapping()
RULES = list(fc.iter_rules(MAPPING))
RULE_IDS = [rule["rule_id"] for _, rule in RULES]

README = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
RULE_REFERENCE = (DOCS_DIR / "rule-reference.md").read_text(encoding="utf-8")
CLANGD_SETUP = (DOCS_DIR / "clangd-setup.md").read_text(encoding="utf-8")
WINDSURF_RULES = (
    PROJECT_ROOT / "windsurf" / "c-safety-critical-rules.md"
).read_text(encoding="utf-8")

# Rule 45 and Rule 46 are style-only rules that the Windsurf ruleset
# deliberately leaves to clang-tidy rather than to the AI assistant.
WINDSURF_OMISSIONS = {"Rule 45", "Rule 46"}


class TestRuleReference:
    """docs/rule-reference.md is the canonical rule documentation."""

    @pytest.mark.parametrize("rule_id", RULE_IDS)
    def test_rule_has_a_section(self, rule_id, covers):
        covers(f"rule:{rule_id}", "file:docs/rule-reference.md")
        assert re.search(rf"^### {rule_id}: ", RULE_REFERENCE, re.M), \
            f"{rule_id} has no section in docs/rule-reference.md"

    @pytest.mark.parametrize("param", RULES, ids=lambda p: p[1]["rule_id"].replace(" ", ""))
    def test_documented_severity_matches_the_mapping(self, param, covers):
        severity, rule = param
        covers(f"rule:{rule['rule_id']}", "file:docs/rule-reference.md")

        section = section_for(RULE_REFERENCE, rule["rule_id"])
        emoji = {"critical": "🔴", "major": "🟡", "minor": "🟢"}[severity]
        assert emoji in section, \
            f"{rule['rule_id']} is {severity} in the mapping but not in the docs"
        assert severity.capitalize() in section

    @pytest.mark.parametrize("param", RULES, ids=lambda p: p[1]["rule_id"].replace(" ", ""))
    def test_documented_checks_come_from_the_mapping(self, param, covers):
        severity, rule = param
        covers(f"rule:{rule['rule_id']}", "file:docs/rule-reference.md")

        section = section_for(RULE_REFERENCE, rule["rule_id"])
        documented = set(re.findall(r"`([a-z][a-z0-9-]+(?:\.[A-Za-z0-9_.*]+)*)`", section))
        documented = {name for name in documented if "-" in name or "." in name}
        mapped = set(rule.get("checks", []))

        # Documentation may list a subset (or a wildcard family) of the checks.
        unknown = {
            name for name in documented
            if name not in mapped
            and not any(check.startswith(name.rstrip("*")) for check in mapped)
            and not name.startswith(("clang-format", ".clang"))
        }
        assert not unknown, \
            f"{rule['rule_id']} documents checks that are not mapped: {unknown}"

    def test_severity_ranges_are_explained(self, covers):
        covers("file:docs/rule-reference.md")
        assert "Critical (Rule 20-29)" in RULE_REFERENCE
        assert "Major (Rule 30-39)" in RULE_REFERENCE
        assert "Minor (Rule 40-49)" in RULE_REFERENCE

    def test_suppression_syntax_matches_the_mapping(self, severity_mapping, covers):
        covers("file:docs/rule-reference.md", "file:rule-severity-mapping.yaml")
        suppression = severity_mapping["suppression"]
        for snippet in (
            suppression["single_line"], suppression["block_start"],
            suppression["block_end"], suppression["file_level"],
        ):
            token = snippet.split("(")[0].replace("// ", "")
            assert token in RULE_REFERENCE, \
                f"{token} suppression syntax is undocumented"

    def test_no_undocumented_rule_sections(self):
        documented = set(re.findall(r"^### (Rule \d+):", RULE_REFERENCE, re.M))
        assert documented <= set(RULE_IDS), \
            f"Documented rules missing from the mapping: {documented - set(RULE_IDS)}"


class TestWindsurfRules:
    """The ruleset consumed by the Windsurf/Cascade AI assistant."""

    @pytest.mark.parametrize("rule_id", RULE_IDS)
    def test_rule_is_available_to_the_assistant(self, rule_id, covers):
        covers(f"rule:{rule_id}", "file:windsurf/c-safety-critical-rules.md")
        present = re.search(rf"^### {rule_id}: ", WINDSURF_RULES, re.M) is not None

        if rule_id in WINDSURF_OMISSIONS:
            assert not present, \
                f"{rule_id} is now in the Windsurf ruleset - update WINDSURF_OMISSIONS"
        else:
            assert present, f"{rule_id} is missing from the Windsurf ruleset"

    def test_every_critical_and_major_rule_is_present(self, covers):
        covers("file:windsurf/c-safety-critical-rules.md")
        required = [
            rule["rule_id"] for severity, rule in RULES if severity in {"critical", "major"}
        ]
        missing = [r for r in required if f"### {r}:" not in WINDSURF_RULES]
        assert not missing, f"Windsurf ruleset must cover {missing}"

    def test_severity_levels_are_explained_with_actions(self, severity_mapping, covers):
        covers("file:windsurf/c-safety-critical-rules.md")
        assert "## Severity Levels" in WINDSURF_RULES
        for severity in severity_mapping["severity_levels"]:
            assert severity.capitalize() in WINDSURF_RULES

    def test_each_rule_shows_a_violation_and_a_fix(self):
        sections = re.findall(r"^### (Rule \d+):.*?(?=^### |\Z)", WINDSURF_RULES, re.M | re.S)
        blocks = re.split(r"^### Rule \d+: ", WINDSURF_RULES, flags=re.M)[1:]
        assert sections, "Windsurf ruleset must document rules"

        for rule_id, block in zip(sections, blocks):
            assert "VIOLATION" in block, f"{rule_id} needs a violation example"
            assert "```" in block, f"{rule_id} needs a code sample"

    def test_validation_commands_reference_the_script(self, covers):
        covers("file:windsurf/c-safety-critical-rules.md", "file:scripts/validate.sh")
        assert "./scripts/validate.sh" in WINDSURF_RULES
        assert "clang-format" in WINDSURF_RULES
        assert "clang-tidy" in WINDSURF_RULES

    def test_suppression_guidance_is_present(self, covers):
        covers("file:windsurf/c-safety-critical-rules.md")
        for token in ("NOLINT", "NOLINTBEGIN", "NOLINTEND", "NOLINTFILE"):
            assert token in WINDSURF_RULES, f"{token} must be documented for the assistant"


class TestReadme:
    """README.md is the entry point for new adopters."""

    def test_has_quick_start_and_severity_overview(self, covers):
        covers("file:README.md")
        assert "Quick Start" in README
        for severity in ("Critical", "Major", "Minor"):
            assert severity in README

    def test_links_to_every_shipped_config(self, covers):
        covers("file:README.md")
        for artifact in (
            ".clang-format", ".clang-tidy", ".clangd",
            "rule-severity-mapping.yaml", "scripts/validate.sh",
        ):
            assert artifact in README, f"README must mention {artifact}"

    def test_documents_the_validate_exit_codes(self, covers):
        covers("file:README.md", "file:scripts/validate.sh")
        script = (PROJECT_ROOT / "scripts" / "validate.sh").read_text(encoding="utf-8")
        documented_codes = set(re.findall(r"^#\s+(\d) - ", script, re.M))
        assert documented_codes == {"0", "1", "2", "3"}, \
            "validate.sh must document all four exit codes"

    def test_relative_links_resolve(self, covers):
        covers("file:README.md")
        links = re.findall(r"\]\((?!https?://|#)([^)]+)\)", README)
        missing = [
            link for link in links
            if not (PROJECT_ROOT / link.split("#")[0]).exists()
        ]
        assert not missing, f"Broken relative links in README: {missing}"


class TestClangdSetupGuide:
    """docs/clangd-setup.md keeps editor setup reproducible."""

    def test_explains_the_compilation_database(self, covers):
        covers("file:docs/clangd-setup.md", "file:scripts/generate-compile-commands.sh")
        assert "compile_commands.json" in CLANGD_SETUP
        assert "generate-compile-commands.sh" in CLANGD_SETUP

    def test_points_at_the_shipped_editor_template(self, covers):
        covers("file:docs/clangd-setup.md", "file:vscode-settings.json.template")
        assert "vscode-settings.json.template" in CLANGD_SETUP

    def test_covers_installation_and_troubleshooting(self, covers):
        covers("file:docs/clangd-setup.md")
        lowered = CLANGD_SETUP.lower()
        assert "install" in lowered
        assert "troubleshoot" in lowered

    def test_relative_links_resolve(self):
        links = re.findall(r"\]\((?!https?://|#)([^)]+)\)", CLANGD_SETUP)
        missing = [
            link for link in links
            if not (DOCS_DIR / link.split("#")[0]).exists()
            and not (PROJECT_ROOT / link.split("#")[0]).exists()
        ]
        assert not missing, f"Broken relative links in clangd-setup.md: {missing}"


def section_for(document, rule_id):
    """Return the markdown section body for a rule heading."""
    match = re.search(rf"^### {rule_id}:.*?(?=^### |\Z)", document, re.M | re.S)
    assert match, f"{rule_id} has no section"
    return match.group(0)
