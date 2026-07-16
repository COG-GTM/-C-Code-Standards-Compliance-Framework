"""
Code Standards Compliance Tests

Verifies that clang-format and clang-tidy configurations work correctly
and that the severity mapping is complete.

Requirements:
    - clang-format (LLVM 20 toolchain; 14+ supported)
    - clang-tidy (LLVM 20 toolchain; 17+ required for the SystemHeaders key)
    - pytest
    - PyYAML

Run: pytest tests/test_compliance.py -v
"""

import os
import subprocess
import shutil
from pathlib import Path

import pytest

# =============================================================================
# Test Configuration
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def command_exists(cmd: str) -> bool:
    """Check if a command exists on the system."""
    return shutil.which(cmd) is not None


# Skip markers for missing tools
requires_clang_format = pytest.mark.skipif(
    not command_exists("clang-format"),
    reason="clang-format not installed"
)

requires_clang_tidy = pytest.mark.skipif(
    not command_exists("clang-tidy"),
    reason="clang-tidy not installed"
)


# =============================================================================
# Configuration File Tests
# =============================================================================

class TestConfigurationFiles:
    """Tests for configuration file existence and validity."""

    def test_clang_format_exists(self):
        """Verify .clang-format config exists at project root."""
        config_path = PROJECT_ROOT / ".clang-format"
        assert config_path.exists(), "Missing .clang-format configuration file"

    def test_clang_tidy_exists(self):
        """Verify .clang-tidy config exists at project root."""
        config_path = PROJECT_ROOT / ".clang-tidy"
        assert config_path.exists(), "Missing .clang-tidy configuration file"

    def test_severity_mapping_exists(self):
        """Verify rule-severity-mapping.yaml exists."""
        mapping_path = PROJECT_ROOT / "rule-severity-mapping.yaml"
        assert mapping_path.exists(), "Missing rule-severity-mapping.yaml"

    def test_windsurf_rules_exist(self):
        """Verify Windsurf rules file exists."""
        rules_path = PROJECT_ROOT / "windsurf" / "c-safety-critical-rules.md"
        assert rules_path.exists(), "Missing windsurf/c-safety-critical-rules.md"

    def test_validate_script_exists(self):
        """Verify validation script exists."""
        script_path = SCRIPTS_DIR / "validate.sh"
        assert script_path.exists(), "Missing scripts/validate.sh"

    def test_validate_script_is_executable(self):
        """Verify validation script has correct structure."""
        script_path = SCRIPTS_DIR / "validate.sh"
        if script_path.exists():
            content = script_path.read_text()
            assert "#!/bin/bash" in content, "Script should have bash shebang"
            assert "clang-format" in content, "Script should use clang-format"
            assert "clang-tidy" in content, "Script should use clang-tidy"


# =============================================================================
# clang-format Tests
# =============================================================================

@requires_clang_format
class TestClangFormat:
    """Tests for clang-format configuration."""

    def test_config_is_valid_yaml(self):
        """Verify .clang-format is valid and can be parsed."""
        result = subprocess.run(
            ["clang-format", "--dump-config"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Invalid .clang-format: {result.stderr}"

    def test_config_has_expected_settings(self):
        """Verify key settings are present in config."""
        result = subprocess.run(
            ["clang-format", "--dump-config"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        config = result.stdout

        # Check for expected settings
        assert "IndentWidth:" in config, "Missing IndentWidth setting"
        assert "BreakBeforeBraces:" in config, "Missing BreakBeforeBraces setting"
        assert "PointerAlignment:" in config, "Missing PointerAlignment setting"

    def test_compliant_example_format(self):
        """Test that compliant.c can be processed by clang-format."""
        compliant = EXAMPLES_DIR / "compliant.c"
        if not compliant.exists():
            pytest.skip("compliant.c not found")

        result = subprocess.run(
            ["clang-format", "--dry-run", str(compliant)],
            capture_output=True,
            text=True,
        )
        # Just verify it runs without error
        assert result.returncode == 0, f"clang-format failed: {result.stderr}"


# =============================================================================
# clang-tidy Tests
# =============================================================================

@requires_clang_tidy
class TestClangTidy:
    """Tests for clang-tidy configuration."""

    def test_config_is_valid(self):
        """Verify .clang-tidy can be loaded."""
        config_path = PROJECT_ROOT / ".clang-tidy"
        assert config_path.exists()

        # Try to run clang-tidy with the config
        result = subprocess.run(
            ["clang-tidy", "--list-checks", f"--config-file={config_path}"],
            capture_output=True,
            text=True,
        )
        # clang-tidy returns 0 even with no files
        assert "Enabled checks:" in result.stdout or result.returncode == 0

    def test_violations_detected(self):
        """Test that violations.c triggers warnings."""
        violations = EXAMPLES_DIR / "violations.c"
        if not violations.exists():
            pytest.skip("violations.c not found")

        result = subprocess.run(
            ["clang-tidy", str(violations), "--", "-I."],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        combined_output = result.stdout + result.stderr
        # Should find at least some warnings in the violations file
        has_issues = "warning:" in combined_output or "error:" in combined_output
        assert has_issues, "Expected violations.c to trigger warnings"


# =============================================================================
# Severity Mapping Tests
# =============================================================================

class TestSeverityMapping:
    """Tests for rule severity classification."""

    @pytest.fixture
    def severity_config(self):
        """Load the severity mapping configuration."""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")

        mapping_path = PROJECT_ROOT / "rule-severity-mapping.yaml"
        with open(mapping_path) as f:
            return yaml.safe_load(f)

    def test_has_all_severity_levels(self, severity_config):
        """Verify all three severity levels are defined."""
        assert "severity_levels" in severity_config

        levels = severity_config["severity_levels"]
        assert "critical" in levels, "Missing 'critical' severity level"
        assert "major" in levels, "Missing 'major' severity level"
        assert "minor" in levels, "Missing 'minor' severity level"

    def test_critical_has_rules(self, severity_config):
        """Verify critical level has rules defined."""
        critical = severity_config["severity_levels"]["critical"]
        assert "rules" in critical
        assert len(critical["rules"]) > 0, "Critical level should have rules"

    def test_critical_rules_have_checks(self, severity_config):
        """Verify critical rules have associated clang-tidy checks."""
        critical = severity_config["severity_levels"]["critical"]
        for rule in critical["rules"]:
            assert "rule_id" in rule, "Rule missing rule_id"
            assert "checks" in rule, f"Rule {rule.get('rule_id')} missing checks"
            assert len(rule["checks"]) > 0, f"Rule {rule.get('rule_id')} has no checks"

    def test_rule_ids_are_unique(self, severity_config):
        """Verify all rule IDs are unique across severity levels."""
        all_rule_ids = []

        for level in severity_config["severity_levels"].values():
            if "rules" in level:
                for rule in level["rules"]:
                    all_rule_ids.append(rule.get("rule_id"))

        # Remove None values
        all_rule_ids = [r for r in all_rule_ids if r]

        # Check for duplicates
        assert len(all_rule_ids) == len(set(all_rule_ids)), "Duplicate rule IDs found"

    def test_critical_rules_start_at_20(self, severity_config):
        """Verify critical rules use the expected numbering scheme."""
        critical = severity_config["severity_levels"]["critical"]
        rule_ids = [r.get("rule_id", "") for r in critical.get("rules", [])]

        # At least one rule should be Rule 2x
        has_rule_20s = any("Rule 2" in r for r in rule_ids)
        assert has_rule_20s, "Expected critical rules to start at Rule 20"


# =============================================================================
# Example Files Tests
# =============================================================================

class TestExampleFiles:
    """Tests for example code files."""

    def test_compliant_example_exists(self):
        """Verify compliant.c example exists."""
        compliant = EXAMPLES_DIR / "compliant.c"
        assert compliant.exists(), "Missing examples/compliant.c"

    def test_violations_example_exists(self):
        """Verify violations.c example exists."""
        violations = EXAMPLES_DIR / "violations.c"
        assert violations.exists(), "Missing examples/violations.c"

    def test_compliant_has_main(self):
        """Verify compliant.c has a main function."""
        compliant = EXAMPLES_DIR / "compliant.c"
        if compliant.exists():
            content = compliant.read_text()
            assert "int main" in content, "compliant.c should have main()"

    def test_violations_documents_rules(self):
        """Verify violations.c documents which rules are violated."""
        violations = EXAMPLES_DIR / "violations.c"
        if violations.exists():
            content = violations.read_text()
            # Should mention rule violations
            assert "Rule 20" in content or "VIOLATION" in content, \
                "violations.c should document rule violations"


# =============================================================================
# Documentation Tests
# =============================================================================

class TestDocumentation:
    """Tests for documentation completeness."""

    def test_readme_exists(self):
        """Verify README.md exists."""
        readme = PROJECT_ROOT / "README.md"
        assert readme.exists(), "Missing README.md"

    def test_readme_has_quick_start(self):
        """Verify README has quick start section."""
        readme = PROJECT_ROOT / "README.md"
        if readme.exists():
            content = readme.read_text()
            assert "Quick Start" in content, "README should have Quick Start section"

    def test_readme_has_severity_info(self):
        """Verify README documents severity levels."""
        readme = PROJECT_ROOT / "README.md"
        if readme.exists():
            content = readme.read_text()
            assert "Critical" in content and "Major" in content and "Minor" in content, \
                "README should document severity levels"

    def test_rule_reference_exists(self):
        """Verify rule reference documentation exists."""
        rule_ref = PROJECT_ROOT / "docs" / "rule-reference.md"
        assert rule_ref.exists(), "Missing docs/rule-reference.md"


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
