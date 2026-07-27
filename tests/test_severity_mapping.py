"""
Severity mapping tests.

rule-severity-mapping.yaml is the contract between the clang tooling, the
Windsurf rules and CI/CD triage, so every rule is validated individually
rather than only spot-checking the critical level.
"""

import re

import pytest

from tests import framework_coverage as fc

MAPPING = fc.load_severity_mapping()
RULES = list(fc.iter_rules(MAPPING))
CHECKS = fc.all_checks(MAPPING)

RULE_IDS = [rule["rule_id"] for _, rule in RULES]

EXPECTED_LEVELS = {
    "critical": {"action": "block_merge", "exit_code": 1, "range": range(20, 30)},
    "major": {"action": "require_review", "exit_code": 0, "range": range(30, 40)},
    "minor": {"action": "warn_only", "exit_code": 0, "range": range(40, 50)},
}


def rule_number(rule_id):
    match = re.fullmatch(r"Rule (\d+)", rule_id)
    assert match, f"Malformed rule_id: {rule_id!r}"
    return int(match.group(1))


def rule_param_id(param):
    severity, rule = param
    return f"{severity}-{rule['rule_id'].replace(' ', '')}"


# =============================================================================
# Document structure
# =============================================================================

class TestMappingStructure:
    """Top level schema of rule-severity-mapping.yaml."""

    def test_version_is_semantic(self, severity_mapping, covers):
        covers("file:rule-severity-mapping.yaml")
        assert re.fullmatch(r"\d+\.\d+", str(severity_mapping["version"])), \
            "version must look like '1.0'"

    def test_last_updated_is_iso_date(self, severity_mapping, covers):
        covers("file:rule-severity-mapping.yaml")
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(severity_mapping["last_updated"])), \
            "last_updated must be an ISO-8601 date"

    def test_only_known_severity_levels(self, severity_mapping):
        assert set(severity_mapping["severity_levels"]) == set(EXPECTED_LEVELS)

    @pytest.mark.parametrize("level_name", sorted(EXPECTED_LEVELS))
    def test_level_metadata(self, severity_mapping, level_name):
        level = severity_mapping["severity_levels"][level_name]
        expected = EXPECTED_LEVELS[level_name]

        assert level["description"], f"{level_name} needs a description"
        assert level["action"] == expected["action"]
        assert level["exit_code"] == expected["exit_code"]
        assert level["rules"], f"{level_name} must define rules"

    def test_only_critical_blocks_merge(self, severity_mapping):
        blocking = [
            name
            for name, level in severity_mapping["severity_levels"].items()
            if level["exit_code"] != 0
        ]
        assert blocking == ["critical"], \
            "Only critical issues may produce a non-zero exit code"

    def test_suppression_guidance_is_complete(self, severity_mapping, covers):
        covers("file:rule-severity-mapping.yaml")
        suppression = severity_mapping["suppression"]

        assert suppression["single_line"].startswith("// NOLINT(")
        assert suppression["block_start"].startswith("// NOLINTBEGIN(")
        assert suppression["block_end"].startswith("// NOLINTEND(")
        assert suppression["file_level"].startswith("// NOLINTFILE(")
        assert len(suppression["notes"]) >= 3, \
            "Suppression guidance must explain when suppressing is acceptable"


# =============================================================================
# Per-rule validation
# =============================================================================

class TestRuleSchema:
    """Every rule, in every severity level, is validated field by field."""

    @pytest.mark.parametrize("param", RULES, ids=rule_param_id)
    def test_rule_has_required_fields(self, param, covers):
        severity, rule = param
        covers(f"rule:{rule['rule_id']}")

        assert rule["rule_id"], "rule_id is required"
        assert rule["name"], f"{rule['rule_id']} needs a name"
        assert rule["rationale"], f"{rule['rule_id']} needs a rationale"
        assert rule["checks"], f"{rule['rule_id']} needs at least one check"
        assert isinstance(rule["checks"], list)

    @pytest.mark.parametrize("param", RULES, ids=rule_param_id)
    def test_rule_id_matches_severity_range(self, param, covers):
        severity, rule = param
        covers(f"rule:{rule['rule_id']}")

        number = rule_number(rule["rule_id"])
        assert number in EXPECTED_LEVELS[severity]["range"], (
            f"{rule['rule_id']} is {severity} but its number is outside "
            f"the {severity} range"
        )

    @pytest.mark.parametrize("param", RULES, ids=rule_param_id)
    def test_rule_examples_contrast_bad_and_good(self, param, covers):
        severity, rule = param
        covers(f"rule:{rule['rule_id']}")

        examples = rule.get("examples")
        if examples is None:
            # Rule 40 (formatting) and Rule 41 (naming) are enforced by
            # configuration tables instead of code snippets.
            assert rule.get("enforced_by") or rule.get("conventions"), (
                f"{rule['rule_id']} must provide examples, an enforced_by "
                f"entry or a conventions table"
            )
            return

        assert examples["bad"].strip(), f"{rule['rule_id']} needs a bad example"
        assert examples["good"].strip(), f"{rule['rule_id']} needs a good example"
        assert examples["bad"] != examples["good"], \
            f"{rule['rule_id']} examples must differ"

    @pytest.mark.parametrize("param", RULES, ids=rule_param_id)
    def test_rationale_explains_impact(self, param, covers):
        severity, rule = param
        covers(f"rule:{rule['rule_id']}")

        rationale = rule["rationale"]
        assert len(rationale.split()) >= 5, \
            f"{rule['rule_id']} rationale is too terse to be useful"
        assert not rationale.endswith("."), \
            f"{rule['rule_id']} rationale should be a single unpunctuated phrase"
        assert rule["name"].lower() not in rationale.lower(), \
            f"{rule['rule_id']} rationale should explain why, not restate the name"

    def test_rule_ids_are_unique(self):
        assert len(RULE_IDS) == len(set(RULE_IDS)), "Duplicate rule_id values"

    def test_rule_names_are_unique(self):
        names = [rule["name"] for _, rule in RULES]
        assert len(names) == len(set(names)), "Duplicate rule names"

    def test_rule_numbers_are_ordered_within_level(self, severity_mapping):
        for name, level in severity_mapping["severity_levels"].items():
            numbers = [rule_number(rule["rule_id"]) for rule in level["rules"]]
            assert numbers == sorted(numbers), f"{name} rules are out of order"


# =============================================================================
# Check assignment
# =============================================================================

class TestCheckAssignment:
    """clang-tidy checks referenced by the mapping."""

    @pytest.mark.parametrize("check", CHECKS)
    def test_check_name_is_well_formed(self, check, covers):
        covers(f"check:{check}")
        assert re.fullmatch(r"[a-z0-9-]+(\.[A-Za-z0-9_.*]+)*", check), \
            f"{check} is not a valid clang-tidy check name"

    @pytest.mark.parametrize("check", CHECKS)
    def test_check_belongs_to_a_known_module(self, check, covers):
        covers(f"check:{check}")
        module = check.split("-")[0]
        known_modules = {
            "bugprone", "cert", "clang", "concurrency", "misc",
            "modernize", "performance", "readability",
        }
        assert module in known_modules, f"{check} uses unknown module {module!r}"

    def test_no_check_is_claimed_by_two_rules(self):
        owners = {}
        for _, rule in RULES:
            for check in rule.get("checks", []):
                owners.setdefault(check, []).append(rule["rule_id"])

        duplicates = {check: ids for check, ids in owners.items() if len(ids) > 1}
        assert not duplicates, f"Checks mapped to multiple rules: {duplicates}"

    def test_critical_rules_cover_the_memory_safety_families(self):
        critical_checks = {
            check
            for severity, rule in RULES
            if severity == "critical"
            for check in rule["checks"]
        }
        for expected in (
            "clang-analyzer-unix.Malloc",
            "clang-analyzer-core.NullDereference",
            "bugprone-double-free",
            "cert-err33-c",
        ):
            assert expected in critical_checks, \
                f"Critical severity must cover {expected}"
