"""
validate.sh must fail closed when clang-tidy cannot analyze the sources.

Each test runs scripts/validate.sh with a PATH that contains only stub
clang-format/clang-tidy binaries plus the coreutils the script needs, so the
tool failure modes (missing binary, rejected config, crash) are reproducible
regardless of which LLVM version is installed.

Run: pytest tests/test_validate_gate.py -v
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
VALIDATE = PROJECT_ROOT / "scripts" / "validate.sh"

COREUTILS = [
    "bash", "cat", "dirname", "find", "grep", "head", "sed", "tail", "tr", "wc",
]

OK_VERSION = 'echo "Ubuntu LLVM version 14.0.0"'


def make_stub(bin_dir, name, body):
    path = bin_dir / name
    path.write_text("#!/bin/bash\n" + body + "\n")
    path.chmod(0o755)


def clang_tidy_stub(version=OK_VERSION, dump_config="exit 0", analyze="exit 0"):
    return f"""
case "$*" in
    *--version*) {version} ;;
    *--dump-config*) {dump_config} ;;
    *) {analyze} ;;
esac
"""


@pytest.fixture
def sandbox(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in COREUTILS:
        found = shutil.which(tool)
        assert found, f"{tool} is required to run validate.sh"
        (bin_dir / tool).symlink_to(found)
    make_stub(bin_dir, "clang-format", "exit 0")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "bad.c").write_text("void f(char *d) { strcpy(d, \"x\"); }\n")
    return bin_dir, src_dir


def run_validate(bin_dir, src_dir):
    env = {"PATH": str(bin_dir), "HOME": os.environ.get("HOME", "/tmp")}
    return subprocess.run(
        [str(bin_dir / "bash"), str(VALIDATE), str(src_dir)],
        env=env,
        capture_output=True,
        text=True,
    )


def assert_not_passed(result):
    assert result.returncode != 0, result.stdout
    tidy_section = result.stdout.partition("clang-tidy analysis")[2]
    assert "PASS\x1b[0m: " not in tidy_section, result.stdout
    assert "All checks passed" not in result.stdout


def test_clean_tool_run_passes(sandbox):
    bin_dir, src_dir = sandbox
    make_stub(bin_dir, "clang-tidy", clang_tidy_stub())
    result = run_validate(bin_dir, src_dir)
    assert result.returncode == 0, result.stdout
    assert "All checks passed" in result.stdout


def test_missing_clang_tidy_fails_closed(sandbox):
    bin_dir, src_dir = sandbox
    result = run_validate(bin_dir, src_dir)
    assert_not_passed(result)
    assert result.returncode == 4
    assert "clang-tidy not found on PATH" in result.stdout


def test_missing_clang_format_fails_closed(sandbox):
    bin_dir, src_dir = sandbox
    (bin_dir / "clang-format").unlink()
    make_stub(bin_dir, "clang-tidy", clang_tidy_stub())
    result = run_validate(bin_dir, src_dir)
    assert_not_passed(result)
    assert result.returncode == 4


def test_old_clang_tidy_fails_closed(sandbox):
    bin_dir, src_dir = sandbox
    make_stub(
        bin_dir, "clang-tidy",
        clang_tidy_stub(version='echo "LLVM version 13.0.1"'),
    )
    result = run_validate(bin_dir, src_dir)
    assert_not_passed(result)
    assert result.returncode == 4
    assert "version 14 or newer is required" in result.stdout


def test_rejected_config_without_lowercase_error_fails_closed(sandbox):
    bin_dir, src_dir = sandbox
    rejected = 'echo "Error: invalid configuration specified." >&2; exit 1'
    make_stub(
        bin_dir, "clang-tidy",
        clang_tidy_stub(dump_config=rejected, analyze=rejected),
    )
    result = run_validate(bin_dir, src_dir)
    assert_not_passed(result)
    assert result.returncode == 4
    assert "clang-tidy rejected" in result.stdout


def test_crash_without_diagnostics_fails(sandbox):
    bin_dir, src_dir = sandbox
    make_stub(
        bin_dir, "clang-tidy",
        clang_tidy_stub(analyze='echo "Segmentation fault" >&2; exit 139'),
    )
    result = run_validate(bin_dir, src_dir)
    assert_not_passed(result)
    assert result.returncode == 2
    assert "clang-tidy exited with status 139" in result.stdout


def test_warnings_only_still_pass_gate(sandbox):
    bin_dir, src_dir = sandbox
    make_stub(
        bin_dir, "clang-tidy",
        clang_tidy_stub(analyze='echo "bad.c:1:1: warning: style [readability-x]"'),
    )
    result = run_validate(bin_dir, src_dir)
    assert result.returncode == 0, result.stdout
    assert "WARN" in result.stdout


def test_clang_tidy_config_has_no_unsupported_keys():
    assert "SystemHeaders" not in (PROJECT_ROOT / ".clang-tidy").read_text()


@pytest.mark.skipif(shutil.which("clang-tidy") is None, reason="clang-tidy not installed")
def test_installed_clang_tidy_accepts_config():
    result = subprocess.run(
        ["clang-tidy", f"--config-file={PROJECT_ROOT / '.clang-tidy'}", "--dump-config"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
