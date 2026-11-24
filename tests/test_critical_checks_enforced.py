"""
Critical rules must block merges.

Every check listed under `critical` in rule-severity-mapping.yaml has to be
promoted to an error by .clang-tidy WarningsAsErrors, and scripts/validate.sh
has to exit non-zero when one of them is reported.
"""

import fnmatch
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

PROJECT_ROOT = Path(__file__).parent.parent
VALIDATE = PROJECT_ROOT / "scripts" / "validate.sh"
MAPPING = PROJECT_ROOT / "rule-severity-mapping.yaml"

STACK_ESCAPE_SOURCE = """\
char *greeting(void)
{
    char buffer[16] = "hello";
    return buffer;
}
"""


def critical_checks():
    mapping = yaml.safe_load(MAPPING.read_text())
    rules = mapping["severity_levels"]["critical"]["rules"]
    return [check for rule in rules for check in rule["checks"]]


def clang_tidy_config():
    return yaml.safe_load((PROJECT_ROOT / ".clang-tidy").read_text())


def split_globs(value):
    return [g.strip() for g in value.split(",") if g.strip()]


def is_enabled(check, globs):
    enabled = False
    for glob in globs:
        if glob.startswith("-"):
            if fnmatch.fnmatchcase(check, glob[1:]):
                enabled = False
        elif fnmatch.fnmatchcase(check, glob):
            enabled = True
    return enabled


class TestConfigSync:
    def test_every_critical_check_is_enabled(self):
        globs = split_globs(clang_tidy_config()["Checks"])
        missing = [c for c in critical_checks() if not is_enabled(c, globs)]
        assert not missing, f"Critical checks not enabled in Checks: {missing}"

    def test_every_critical_check_is_warning_as_error(self):
        globs = split_globs(clang_tidy_config()["WarningsAsErrors"])
        missing = [c for c in critical_checks() if not is_enabled(c, globs)]
        assert not missing, f"Critical checks missing from WarningsAsErrors: {missing}"

    def test_validate_reads_same_critical_checks_as_yaml(self):
        script = (
            f"source <(sed -n '/^load_critical_checks()/,/^}}/p' '{VALIDATE}'); "
            f"load_critical_checks '{MAPPING}'"
        )
        result = subprocess.run(
            ["bash", "-c", script], capture_output=True, text=True, check=True
        )
        assert result.stdout.split() == critical_checks()


def write_stub(path, body):
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def run_validate(tmp_path):
    """Run validate.sh against one file with stub clang tools on PATH."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_stub(bin_dir / "clang-format", "exit 0\n")
    write_stub(bin_dir / "clang-tidy", 'printf "%b" "$STUB_TIDY_OUTPUT"\nexit 0\n')
    target = tmp_path / "src"
    target.mkdir()
    (target / "x.c").write_text("int main(void) { return 0; }\n")

    def run(tidy_output, **extra_env):
        env = dict(os.environ)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
        env["STUB_TIDY_OUTPUT"] = tidy_output
        env.update(extra_env)
        return subprocess.run(
            [str(VALIDATE), str(target)], capture_output=True, text=True, env=env
        )

    return run


class TestValidateGate:
    @pytest.mark.parametrize(
        "check",
        [
            "clang-analyzer-core.StackAddressEscape",
            "clang-analyzer-core.NonNullParamChecker",
            "clang-analyzer-cplusplus.NewDeleteLeaks",
            "bugprone-not-null-terminated-result",
            "cert-env33-c",
        ],
    )
    def test_critical_warning_fails(self, run_validate, check):
        result = run_validate(f"src/x.c:4:5: warning: bad thing [{check}]\\n")
        assert result.returncode == 2, result.stdout
        assert "critical issues" in result.stdout

    def test_critical_check_in_multi_check_list_fails(self, run_validate):
        result = run_validate(
            "src/x.c:2:12: warning: rand() has limited randomness "
            "[cert-msc50-cpp,cert-msc30-c]\\n"
        )
        assert result.returncode == 2, result.stdout

    def test_major_warning_does_not_fail(self, run_validate):
        result = run_validate(
            "src/x.c:2:12: warning: narrowing [bugprone-narrowing-conversions]\\n"
        )
        assert result.returncode == 0, result.stdout
        assert "warnings" in result.stdout

    def test_missing_mapping_fails_closed(self, run_validate, tmp_path):
        result = run_validate("", SEVERITY_MAPPING=str(tmp_path / "missing.yaml"))
        assert result.returncode == 4, result.stdout


@pytest.mark.skipif(shutil.which("clang-tidy") is None, reason="clang-tidy not installed")
def test_shipped_config_turns_stack_address_escape_into_error(tmp_path):
    config = clang_tidy_config()
    inline = yaml.safe_dump(
        {"Checks": config["Checks"], "WarningsAsErrors": config["WarningsAsErrors"]}
    )
    source = tmp_path / "escape.c"
    source.write_text(STACK_ESCAPE_SOURCE)
    result = subprocess.run(
        ["clang-tidy", f"--config={inline}", str(source), "--"],
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "error:" in output and "clang-analyzer-core.StackAddressEscape" in output
