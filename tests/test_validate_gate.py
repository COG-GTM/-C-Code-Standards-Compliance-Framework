"""
validate.sh must fail closed when clang-tidy cannot actually analyze code.

Each test runs the real scripts/validate.sh with a PATH that hides the system
clang tools and optionally adds stub binaries.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
VALIDATE = PROJECT_ROOT / "scripts" / "validate.sh"
EXAMPLES_DIR = PROJECT_ROOT / "examples"
CLANG_TOOLS = {"clang-tidy", "clang-format"}

PROBE_WARNING = (
    "violations.c:1:1: warning: probe [bugprone-probe]"
)


@pytest.fixture(scope="module")
def base_bin(tmp_path_factory):
    """A directory mirroring /usr/bin and /bin minus any clang tooling."""
    bin_dir = tmp_path_factory.mktemp("base-bin")
    for src_dir in ("/usr/local/bin", "/usr/bin", "/bin"):
        if not os.path.isdir(src_dir):
            continue
        for name in os.listdir(src_dir):
            if name.startswith("clang") or (bin_dir / name).exists():
                continue
            os.symlink(os.path.join(src_dir, name), bin_dir / name)
    return bin_dir


def write_stub(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(0o755)


def run_validate(base_bin: Path, stub_dir: Path, target: Path = EXAMPLES_DIR):
    env = {
        "PATH": f"{stub_dir}:{base_bin}",
        "HOME": os.environ.get("HOME", "/tmp"),
        "TERM": "dumb",
    }
    return subprocess.run(
        ["bash", str(VALIDATE), str(target)],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def tidy_stub(per_file_body: str) -> str:
    """clang-tidy stub: valid config, flags the probe, per_file_body otherwise."""
    return f"""
case "$*" in
    *--dump-config*) echo "Checks: '*'"; exit 0 ;;
    *examples/violations.c*--*) echo "{PROBE_WARNING}"; exit 0 ;;
esac
{per_file_body}
"""


@pytest.fixture
def stub_dir(tmp_path):
    d = tmp_path / "stubs"
    d.mkdir()
    write_stub(d, "clang-format", "exit 0\n")
    return d


@pytest.fixture
def single_source(tmp_path):
    d = tmp_path / "src"
    d.mkdir()
    (d / "a.c").write_text("int main(void)\n{\n    return 0;\n}\n")
    return d


def assert_no_file_pass(output: str) -> None:
    """No file may be reported PASS by clang-tidy (or at all, if never reached)."""
    _, sep, tidy_section = output.partition("clang-tidy analysis")
    for line in (tidy_section if sep else output).splitlines():
        if "PASS" in line and line.rstrip().endswith(".c"):
            pytest.fail(f"file reported as PASS: {line}")


def test_missing_clang_tidy_exits_nonzero_with_message(base_bin, stub_dir):
    result = run_validate(base_bin, stub_dir)
    out = result.stdout + result.stderr
    assert result.returncode == 4, out
    assert "clang-tidy not found on PATH" in out
    assert_no_file_pass(out)
    assert "All checks passed" not in out


def test_missing_clang_format_exits_nonzero(base_bin, tmp_path):
    d = tmp_path / "only-tidy"
    d.mkdir()
    write_stub(d, "clang-tidy", tidy_stub("exit 0\n"))
    result = run_validate(base_bin, d)
    assert result.returncode == 4
    assert "clang-format not found on PATH" in result.stdout


def test_rejected_config_exits_nonzero(base_bin, stub_dir):
    write_stub(
        stub_dir,
        "clang-tidy",
        "echo \"error: unknown key 'Foo'\" >&2\nexit 1\n",
    )
    result = run_validate(base_bin, stub_dir)
    assert result.returncode == 4
    assert "clang-tidy rejected" in result.stdout
    assert_no_file_pass(result.stdout)


def test_silent_clang_tidy_fails_probe(base_bin, stub_dir):
    write_stub(stub_dir, "clang-tidy", "exit 0\n")
    result = run_validate(base_bin, stub_dir)
    assert result.returncode == 4
    assert "produced no diagnostics on known-bad probe" in result.stdout
    assert_no_file_pass(result.stdout)


def test_crashing_probe_fails(base_bin, stub_dir):
    write_stub(
        stub_dir,
        "clang-tidy",
        "case \"$*\" in *--dump-config*) exit 0 ;; esac\n"
        f"echo \"{PROBE_WARNING}\"\nkill -SEGV $$\n",
    )
    result = run_validate(base_bin, stub_dir)
    assert result.returncode == 4
    assert "exit status 139" in result.stdout


def test_signal_death_on_source_file_fails(base_bin, stub_dir, single_source):
    write_stub(stub_dir, "clang-tidy", tidy_stub("kill -SEGV $$\n"))
    result = run_validate(base_bin, stub_dir, single_source)
    assert result.returncode == 2, result.stdout
    assert "a.c (clang-tidy exited with status 139)" in result.stdout
    assert_no_file_pass(result.stdout)


def test_status_one_without_diagnostics_fails(base_bin, stub_dir, single_source):
    write_stub(stub_dir, "clang-tidy", tidy_stub("echo 'Segmentation fault'\nexit 1\n"))
    result = run_validate(base_bin, stub_dir, single_source)
    assert result.returncode == 2
    assert "without diagnostics" in result.stdout
    assert_no_file_pass(result.stdout)


def test_clean_run_still_passes(base_bin, stub_dir, single_source):
    write_stub(stub_dir, "clang-tidy", tidy_stub("exit 0\n"))
    result = run_validate(base_bin, stub_dir, single_source)
    assert result.returncode == 0, result.stdout
    assert "PASS" in result.stdout and "a.c" in result.stdout
    assert "All checks passed" in result.stdout


def test_warnings_only_still_exit_zero(base_bin, stub_dir, single_source):
    write_stub(
        stub_dir,
        "clang-tidy",
        tidy_stub("echo 'a.c:1:1: warning: style [readability-x]'\nexit 0\n"),
    )
    result = run_validate(base_bin, stub_dir, single_source)
    assert result.returncode == 0
    assert "a.c (warnings)" in result.stdout


@pytest.mark.skipif(
    shutil.which("clang-tidy") is None or shutil.which("clang-format") is None,
    reason="clang tooling not installed",
)
def test_real_tooling_flags_violations():
    result = subprocess.run(
        ["bash", str(VALIDATE), str(EXAMPLES_DIR)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode in (2, 3), result.stdout
    assert "violations.c (critical issues)" in result.stdout
