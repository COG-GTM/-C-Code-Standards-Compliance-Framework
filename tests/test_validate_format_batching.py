"""
Tests for the batched/parallel clang-format step in scripts/validate.sh.

A stub clang-format on PATH logs each invocation and flags any file whose
name contains "bad" as unformatted, so the tests run without real tooling.

Run: pytest tests/test_validate_format_batching.py -v
"""

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
VALIDATE = PROJECT_ROOT / "scripts" / "validate.sh"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

STUB_CLANG_FORMAT = """#!/bin/bash
echo "$*" >> "$STUB_LOG"
files=()
for arg in "$@"; do
    case "$arg" in
        -*) ;;
        *) files+=("$arg") ;;
    esac
done
rc=0
for f in "${files[@]}"; do
    case "$(basename "$f")" in
        *bad*) rc=1 ;;
    esac
done
exit $rc
"""

STUB_CLANG_TIDY = "#!/bin/bash\nexit 0\n"


def _write_exe(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def stub_env(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_exe(bin_dir / "clang-format", STUB_CLANG_FORMAT)
    _write_exe(bin_dir / "clang-tidy", STUB_CLANG_TIDY)
    log = tmp_path / "clang-format.log"
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["STUB_LOG"] = str(log)
    env["VALIDATE_JOBS"] = "4"
    return env, log


def _make_tree(root: Path, good: int, bad: int) -> list:
    src = root / "src"
    src.mkdir()
    names = [f"good_{i:03d}.c" for i in range(good)]
    names += [f"bad_{i:03d}.h" for i in range(bad)]
    for name in names:
        (src / name).write_text("int x;\n")
    return names


def _run(env, target: Path, *extra):
    result = subprocess.run(
        ["bash", str(VALIDATE), str(target), *extra],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    return result.returncode, ANSI.sub("", result.stdout)


def _format_section(output: str) -> str:
    return output.split("--- clang-format check ---")[1].split("--- clang-tidy")[0]


def _file_invocations(log: Path) -> list:
    lines = log.read_text().splitlines()
    return [line for line in lines if "--dump-config" not in line]


def test_check_mode_reports_each_file_and_batches(tmp_path, stub_env):
    env, log = stub_env
    names = _make_tree(tmp_path, good=40, bad=3)

    rc, out = _run(env, tmp_path / "src")
    section = _format_section(out)

    for name in names:
        if name.startswith("bad"):
            assert re.search(rf"FAIL: \S*{name} \(needs formatting\)", section)
        else:
            assert re.search(rf"PASS: \S*{name}$", section, re.M)
    assert "3 file(s) have formatting issues" in section
    assert "Format:   3 file(s) need formatting" in out
    assert rc == 1

    calls = _file_invocations(log)
    assert all("--dry-run --Werror" in c for c in calls)
    assert all("--style=file:" in c for c in calls)
    # One call per batch plus per-file retries for batches containing a bad
    # file; far fewer than the old 1-2 calls per file.
    assert len(calls) < len(names)


def test_output_order_matches_discovery_order(tmp_path, stub_env):
    env, _ = stub_env
    _make_tree(tmp_path, good=30, bad=5)

    _, out = _run(env, tmp_path / "src")
    reported = re.findall(r"(?:PASS|FAIL): (/\S+)", _format_section(out))

    discovered = subprocess.run(
        ["bash", "-c", 'find "$1" -type f \\( -name "*.c" -o -name "*.h" \\)', "_",
         str(tmp_path / "src")],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert reported == discovered


def test_fix_mode_batches_in_place_formatting(tmp_path, stub_env):
    env, log = stub_env
    names = _make_tree(tmp_path, good=50, bad=0)

    rc, out = _run(env, tmp_path / "src", "--fix")
    section = _format_section(out)

    assert section.count("PASS: Formatted:") == len(names)
    assert "All files properly formatted" in section
    assert rc == 0

    calls = _file_invocations(log)
    assert all(c.startswith("-i ") for c in calls)
    assert len(calls) <= 4
    formatted = sum(len(c.split()) - 2 for c in calls)
    assert formatted == len(names)


def test_fix_mode_reports_unformattable_file(tmp_path, stub_env):
    env, _ = stub_env
    _make_tree(tmp_path, good=10, bad=1)

    rc, out = _run(env, tmp_path / "src", "--fix")
    section = _format_section(out)

    assert re.search(r"FAIL: Could not format: \S*bad_000\.h", section)
    assert section.count("PASS: Formatted:") == 10
    assert "1 file(s) have formatting issues" in section
    assert rc == 1
