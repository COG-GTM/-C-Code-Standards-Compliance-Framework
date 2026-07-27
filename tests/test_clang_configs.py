"""
Configuration tests for .clang-format, .clang-tidy, .clangd and the VS Code
settings template, including consistency between the configs and the rule
severity mapping.
"""

import re
import subprocess

import pytest

from tests import framework_coverage as fc
from tests.conftest import PROJECT_ROOT, requires_clang_format, requires_clang_tidy

MAPPING = fc.load_severity_mapping()
CHECKS = fc.all_checks(MAPPING)

CRITICAL_CHECKS = [
    check
    for severity, rule in fc.iter_rules(MAPPING)
    if severity == "critical"
    for check in rule["checks"]
]

# Rule 40 is enforced by clang-format, and Rule 45 is C++ only: the
# modernize-* module is deliberately not enabled for this C-focused config.
CHECKS_NOT_ENABLED_BY_DESIGN = {
    "clang-format": "Rule 40 is enforced by .clang-format, not clang-tidy",
    "modernize-use-nullptr": "Rule 45 is C++ only; modernize-* is not enabled",
}

# Critical checks that are reported as warnings rather than promoted to errors
# by WarningsAsErrors. CI blocks on them through the severity mapping instead.
CRITICAL_CHECKS_NOT_PROMOTED = {
    "bugprone-not-null-terminated-result",
    "bugprone-stringview-nullptr",
    "clang-analyzer-core.NonNullParamChecker",
    "clang-analyzer-core.StackAddressEscape",
    "clang-analyzer-core.UndefinedBinaryOperatorResult",
    "clang-analyzer-cplusplus.NewDelete",
    "clang-analyzer-cplusplus.NewDeleteLeaks",
    "cert-msc30-c",
    "cert-msc50-cpp",
    "cert-env33-c",
}


def split_check_list(value):
    """Split a clang-tidy Checks/WarningsAsErrors block scalar into globs."""
    return [item.strip() for item in value.replace("\n", " ").split(",") if item.strip()]


def glob_matches(glob, check):
    pattern = re.escape(glob).replace(r"\*", ".*")
    return re.fullmatch(pattern, check) is not None


def check_is_enabled(globs, check):
    """Apply the clang-tidy glob list in order; later negations win."""
    enabled = False
    for glob in globs:
        negated = glob.startswith("-")
        candidate = glob[1:] if negated else glob
        if glob_matches(candidate, check):
            enabled = not negated
    return enabled


# =============================================================================
# .clang-format
# =============================================================================

class TestClangFormatConfig:
    """Formatting rules (Rule 40) declared by .clang-format."""

    def test_allman_brace_style(self, clang_format_config, covers):
        covers("file:.clang-format", "rule:Rule 40")
        assert clang_format_config["BreakBeforeBraces"] == "Custom"

        wrapping = clang_format_config["BraceWrapping"]
        for key in (
            "AfterCaseLabel", "AfterClass", "AfterEnum", "AfterFunction",
            "AfterNamespace", "AfterStruct", "AfterUnion", "AfterExternBlock",
            "BeforeCatch", "BeforeElse", "BeforeWhile",
        ):
            assert wrapping[key] is True, f"Allman style requires {key}: true"
        assert wrapping["AfterControlStatement"] == "Always"
        assert wrapping["IndentBraces"] is False

    def test_indentation_is_four_spaces_no_tabs(self, clang_format_config, covers):
        covers("file:.clang-format", "rule:Rule 40")
        assert clang_format_config["IndentWidth"] == 4
        assert clang_format_config["TabWidth"] == 4
        assert clang_format_config["UseTab"] == "Never"
        assert clang_format_config["ContinuationIndentWidth"] == 4

    def test_column_limit_is_one_hundred(self, clang_format_config, covers):
        covers("file:.clang-format")
        assert clang_format_config["ColumnLimit"] == 100

    def test_pointers_bind_to_the_name(self, clang_format_config, covers):
        covers("file:.clang-format", "rule:Rule 41")
        assert clang_format_config["PointerAlignment"] == "Right"
        assert clang_format_config["ReferenceAlignment"] == "Right"
        assert clang_format_config["DerivePointerAlignment"] is False, \
            "Deriving alignment from the file would defeat the standard"

    def test_short_constructs_are_never_collapsed(self, clang_format_config, covers):
        covers("file:.clang-format", "rule:Rule 42")
        assert clang_format_config["AllowShortBlocksOnASingleLine"] == "Never"
        assert clang_format_config["AllowShortIfStatementsOnASingleLine"] == "Never"
        assert clang_format_config["AllowShortFunctionsOnASingleLine"] == "None"
        assert clang_format_config["AllowShortLoopsOnASingleLine"] is False

    def test_include_categories_are_ordered_and_unique(self, clang_format_config, covers):
        covers("file:.clang-format")
        assert clang_format_config["SortIncludes"] == "CaseSensitive"
        assert clang_format_config["IncludeBlocks"] == "Regroup"

        priorities = [c["Priority"] for c in clang_format_config["IncludeCategories"]]
        assert priorities == sorted(priorities), "Include categories must be ordered"
        assert len(priorities) == len(set(priorities)), "Duplicate include priorities"

    @pytest.mark.parametrize(
        "regex_index,sample",
        [
            (0, "<stdio.h>"),
            (1, "<unistd.h>"),
            (2, "<vector>"),
            (3, "<windows.h>"),
            (4, '"project.h"'),
        ],
    )
    def test_include_category_regexes_classify_headers(
        self, clang_format_config, regex_index, sample
    ):
        categories = clang_format_config["IncludeCategories"]
        matched = next(
            index
            for index, category in enumerate(categories)
            if re.search(category["Regex"], sample)
        )
        assert matched == regex_index, \
            f"{sample} should be classified by category {regex_index}"

    @requires_clang_format
    def test_clang_format_accepts_the_config(self, covers):
        covers("file:.clang-format")
        completed = subprocess.run(
            ["clang-format", "--dump-config"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        assert "IndentWidth:     4" in completed.stdout.replace("\r", "")


# =============================================================================
# .clang-tidy
# =============================================================================

class TestClangTidyConfig:
    """Static analysis configuration and its agreement with the mapping."""

    def test_enabled_modules(self, clang_tidy_config, covers):
        covers("file:.clang-tidy")
        globs = split_check_list(clang_tidy_config["Checks"])
        for module in (
            "bugprone-*", "cert-*", "clang-analyzer-*", "concurrency-*",
            "misc-*", "performance-*", "readability-*",
        ):
            assert module in globs, f"{module} must be enabled"

    def test_noisy_checks_are_disabled(self, clang_tidy_config, covers):
        covers("file:.clang-tidy")
        globs = split_check_list(clang_tidy_config["Checks"])
        for disabled in (
            "-bugprone-easily-swappable-parameters",
            "-readability-function-cognitive-complexity",
            "-readability-magic-numbers",
            "-misc-no-recursion",
        ):
            assert disabled in globs, f"{disabled} should be suppressed as noise"

    def test_negations_come_after_the_modules_they_narrow(self, clang_tidy_config):
        globs = split_check_list(clang_tidy_config["Checks"])
        first_negation = next(i for i, g in enumerate(globs) if g.startswith("-"))
        assert all(g.startswith("-") for g in globs[first_negation:]), \
            "All negations must be grouped after the enabling globs"

    @pytest.mark.parametrize("check", CHECKS)
    def test_mapped_check_is_enabled(self, clang_tidy_config, check, covers):
        covers(f"check:{check}", "file:.clang-tidy")
        globs = split_check_list(clang_tidy_config["Checks"])
        enabled = check_is_enabled(globs, check)

        if check in CHECKS_NOT_ENABLED_BY_DESIGN:
            assert not enabled, (
                f"{check} is documented as not enabled "
                f"({CHECKS_NOT_ENABLED_BY_DESIGN[check]}) but the config enables it - "
                f"remove it from CHECKS_NOT_ENABLED_BY_DESIGN"
            )
        else:
            assert enabled, f"{check} is mapped to a rule but not enabled by .clang-tidy"

    @pytest.mark.parametrize("check", sorted(set(CRITICAL_CHECKS)))
    def test_critical_check_promotion(self, clang_tidy_config, check, covers):
        covers(f"check:{check}", "file:.clang-tidy")
        error_globs = split_check_list(clang_tidy_config["WarningsAsErrors"])
        promoted = any(glob_matches(glob, check) for glob in error_globs)

        if check in CRITICAL_CHECKS_NOT_PROMOTED or check in CHECKS_NOT_ENABLED_BY_DESIGN:
            assert not promoted, (
                f"{check} is now promoted to an error - remove it from "
                f"CRITICAL_CHECKS_NOT_PROMOTED"
            )
        else:
            assert promoted, \
                f"Critical check {check} must be in WarningsAsErrors to block merges"

    def test_warnings_as_errors_only_lists_critical_checks(self, clang_tidy_config):
        error_globs = split_check_list(clang_tidy_config["WarningsAsErrors"])
        non_critical = [
            glob
            for glob in error_globs
            if not any(glob_matches(glob, check) for check in CRITICAL_CHECKS)
        ]
        # cert-err34-c and bugprone-sizeof-expression are promoted defensively
        # even though no rule claims them yet.
        assert set(non_critical) <= {"cert-err34-c", "bugprone-sizeof-expression"}, \
            f"Unexpected non-critical checks promoted to errors: {non_critical}"

    def test_checked_functions_cover_allocation_and_io(self, clang_tidy_config, covers):
        covers("rule:Rule 20", "check:bugprone-unused-return-value")
        options = {
            option["key"]: str(option["value"])
            for option in clang_tidy_config["CheckOptions"]
        }
        checked = options["bugprone-unused-return-value.CheckedFunctions"]
        for function in ("malloc", "calloc", "realloc", "fopen", "fclose",
                         "read", "write", "pthread_create", "mmap"):
            assert f"::{function};" in checked or checked.endswith(f"::{function}"), \
                f"{function} must require a checked return value"

    def test_naming_options_match_rule_41_conventions(self, clang_tidy_config, covers):
        covers("rule:Rule 41", "check:readability-identifier-naming")
        options = {
            option["key"]: option["value"]
            for option in clang_tidy_config["CheckOptions"]
        }
        conventions = next(
            rule["conventions"]
            for _, rule in fc.iter_rules(MAPPING)
            if rule["rule_id"] == "Rule 41"
        )

        assert options["readability-identifier-naming.FunctionCase"] == conventions["functions"]
        assert options["readability-identifier-naming.VariableCase"] == conventions["variables"]
        for constant_option in ("GlobalConstantCase", "MacroDefinitionCase"):
            assert options[f"readability-identifier-naming.{constant_option}"] == \
                conventions["constants"]
        for type_option in ("StructCase", "EnumCase", "TypedefCase", "ClassCase"):
            assert options[f"readability-identifier-naming.{type_option}"] == conventions["types"]

    def test_narrowing_conversion_options_are_strict(self, clang_tidy_config, covers):
        covers("rule:Rule 30", "check:bugprone-narrowing-conversions")
        options = {
            option["key"]: option["value"]
            for option in clang_tidy_config["CheckOptions"]
        }
        prefix = "bugprone-narrowing-conversions"
        assert options[f"{prefix}.WarnOnIntegerNarrowingConversion"] is True
        assert options[f"{prefix}.WarnOnFloatingPointNarrowingConversion"] is True

    def test_check_option_keys_are_unique(self, clang_tidy_config):
        keys = [option["key"] for option in clang_tidy_config["CheckOptions"]]
        assert len(keys) == len(set(keys)), "Duplicate CheckOptions keys"

    def test_check_options_reference_enabled_checks(self, clang_tidy_config):
        globs = split_check_list(clang_tidy_config["Checks"])
        for option in clang_tidy_config["CheckOptions"]:
            check = option["key"].rsplit(".", 1)[0]
            assert check_is_enabled(globs, check), \
                f"Option {option['key']} configures a disabled check"

    def test_headers_are_analysed_but_system_headers_are_not(self, clang_tidy_config, covers):
        covers("file:.clang-tidy")
        assert clang_tidy_config["HeaderFilterRegex"] == ".*"
        assert clang_tidy_config["SystemHeaders"] is False
        assert clang_tidy_config["FormatStyle"] == "file", \
            "Fix-its must be formatted with the project's .clang-format"

    @requires_clang_tidy
    def test_clang_tidy_accepts_the_config(self, covers):
        covers("file:.clang-tidy")
        completed = subprocess.run(
            ["clang-tidy", "--list-checks",
             f"--config-file={PROJECT_ROOT / '.clang-tidy'}"],
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        assert "Enabled checks:" in completed.stdout


# =============================================================================
# .clangd
# =============================================================================

class TestClangdConfig:
    """Editor/LSP configuration."""

    def test_compile_flags_target_c17_with_warnings(self, clangd_config, covers):
        covers("file:.clangd")
        added = clangd_config["CompileFlags"]["Add"]
        for flag in ("-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-xc"):
            assert flag in added, f"{flag} must be passed to clangd"
        assert "-I." in added

    def test_clangd_enables_the_same_modules_as_clang_tidy(
        self, clangd_config, clang_tidy_config, covers
    ):
        covers("file:.clangd", "file:.clang-tidy")
        clangd_added = set(clangd_config["Diagnostics"]["ClangTidy"]["Add"])
        tidy_globs = {
            glob for glob in split_check_list(clang_tidy_config["Checks"])
            if not glob.startswith("-")
        }
        # concurrency-* is CI-only; every other module must be available in the editor.
        assert tidy_globs - clangd_added <= {"concurrency-*"}, \
            "Editor diagnostics must mirror the CI check modules"

    def test_clangd_suppresses_the_same_noisy_checks(
        self, clangd_config, clang_tidy_config, covers
    ):
        covers("file:.clangd")
        clangd_removed = set(clangd_config["Diagnostics"]["ClangTidy"]["Remove"])
        tidy_negations = {
            glob[1:] for glob in split_check_list(clang_tidy_config["Checks"])
            if glob.startswith("-")
        }
        assert clangd_removed <= tidy_negations, \
            "clangd must not silence checks that CI still enforces"

    def test_background_indexing_is_enabled(self, clangd_config, covers):
        covers("file:.clangd")
        assert clangd_config["Index"]["Background"] == "Build"
        assert clangd_config["Index"]["StandardLibrary"] is True

    def test_inlay_hints_are_configured(self, clangd_config):
        hints = clangd_config["InlayHints"]
        assert hints["ParameterNames"] is True
        assert hints["DeducedTypes"] is True
        assert isinstance(hints["TypeNameLimit"], int)


# =============================================================================
# VS Code / Windsurf settings template
# =============================================================================

class TestVSCodeTemplate:
    """The editor template shipped for Windsurf/VS Code users."""

    def test_template_is_valid_json(self, vscode_settings_template, covers):
        covers("file:vscode-settings.json.template")
        assert isinstance(vscode_settings_template, dict)

    @pytest.mark.parametrize("language", ["[c]", "[cpp]"])
    def test_template_formats_on_save_with_clangd(
        self, vscode_settings_template, language, covers
    ):
        covers("file:vscode-settings.json.template")
        settings = vscode_settings_template[language]
        assert settings["editor.defaultFormatter"] == "llvm-vs-code-extensions.vscode-clangd"
        assert settings["editor.formatOnSave"] is True
        assert settings["editor.insertSpaces"] is True

    def test_template_disables_conflicting_intellisense(self, vscode_settings_template, covers):
        covers("file:vscode-settings.json.template")
        for key in ("C_Cpp.intelliSenseEngine", "C_Cpp.autocomplete",
                    "C_Cpp.errorSquiggles", "C_Cpp.formatting"):
            assert vscode_settings_template[key] == "disabled", \
                f"{key} conflicts with clangd and must be disabled"

    def test_template_enables_clangd_config_and_tidy(self, vscode_settings_template, covers):
        covers("file:vscode-settings.json.template", "file:.clangd")
        arguments = vscode_settings_template["clangd.arguments"]
        for flag in ("--enable-config", "--background-index", "--clang-tidy"):
            assert flag in arguments, f"clangd must be started with {flag}"

    @pytest.mark.parametrize("language", ["[c]", "[cpp]"])
    def test_template_matches_clang_format_indentation(
        self, vscode_settings_template, clang_format_config, language, covers
    ):
        covers("file:vscode-settings.json.template", "file:.clang-format")
        tab_size = vscode_settings_template[language]["editor.tabSize"]
        assert tab_size == clang_format_config["IndentWidth"], \
            "Editor tab size must match .clang-format IndentWidth"

    def test_template_associates_c_and_cpp_extensions(self, vscode_settings_template):
        associations = vscode_settings_template["files.associations"]
        assert associations["*.h"] == "c"
        assert associations["*.c"] == "c"
        for extension in ("*.hpp", "*.cpp", "*.cc", "*.cxx"):
            assert associations[extension] == "cpp"

    def test_template_has_no_absolute_user_paths(self, covers):
        covers("file:vscode-settings.json.template")
        raw = (PROJECT_ROOT / "vscode-settings.json.template").read_text(encoding="utf-8")
        assert not re.search(r"[A-Za-z]:\\\\Users", raw), "Template leaks a local path"
        assert "/home/" not in raw and "/Users/" not in raw, "Template leaks a local path"
        fc.parse_jsonc(raw)
