"""
Tests for the batched/parallel clang-format step in scripts/validate.sh.

A stub clang-format on PATH logs every invocation so the tests can assert
that files are formatted in batches (not one process per file) while the
per-file PASS/FAIL report and FORMAT_ERRORS count stay unchanged.

Run: pytest tests/test_validate_format_batching.py -v
"""

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
VALIDATE = PROJECT_ROOT / "scripts" / "validate.sh"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

# Fails (exit 1) for any file whose content contains "BADFORMAT"; logs argv.
STUB_CLANG_FORMAT = """#!/bin/bash
printf '%s\\n' "$*" >> "$STUB_LOG"
for arg in "$@"; do
    case "$arg" in
        --dump-config) exit 0 ;;
    esac
done
rc=0
for arg in "$@"; do
    case "$arg" in
        -*) ;;
        *) if grep -q BADFORMAT "$arg" 2>/dev/null; then rc=1; fi ;;
    esac
done
exit $rc
"""

STUB_CLANG_TIDY = """#!/bin/bash
exit 0
"""


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
    log.write_text("")
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["STUB_LOG"] = str(log)
    return env, log


def _make_tree(root: Path, count: int, bad=()):
    src = root / "src"
    src.mkdir()
    for i in range(count):
        ext = ".h" if i % 3 == 0 else ".c"
        content = "BADFORMAT\n" if i in bad else "int ok;\n"
        (src / f"f{i:02d}{ext}").write_text(content)
    return src


def _run(src: Path, env, *extra, jobs="4"):
    env = dict(env)
    env["VALIDATE_JOBS"] = jobs
    result = subprocess.run(
        ["bash", str(VALIDATE), str(src), *extra],
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, ANSI.sub("", result.stdout)


def _format_calls(log: Path):
    return [line for line in log.read_text().splitlines() if "--dump-config" not in line]


def _format_section(out: str) -> str:
    return out.split("--- clang-format check ---")[1].split("--- clang-tidy analysis ---")[0]


def _discovery_order(src: Path):
    out = subprocess.run(
        ["find", str(src), "-type", "f"], capture_output=True, text=True, check=True
    ).stdout
    return out.split()


def test_check_mode_batches_clean_tree(tmp_path, stub_env):
    env, log = stub_env
    src = _make_tree(tmp_path, 40)

    code, out = _run(src, env)

    assert code == 0
    calls = _format_calls(log)
    assert len(calls) <= 4, calls
    assert all("--dry-run --Werror" in c for c in calls)
    assert all(f"--style=file:{PROJECT_ROOT}/.clang-format" in c for c in calls)
    section = _format_section(out)
    expected = [f"✓ PASS: {f}" for f in _discovery_order(src)]
    assert [l for l in section.splitlines() if l.startswith(("✓", "✗"))][:-1] == expected
    assert "All files properly formatted" in section


def test_check_mode_reports_each_failing_file_in_order(tmp_path, stub_env):
    env, log = stub_env
    bad = {3, 17, 29}
    src = _make_tree(tmp_path, 40, bad=bad)

    code, out = _run(src, env)

    assert code == 1
    section = _format_section(out)
    expected = []
    for f in _discovery_order(src):
        if "BADFORMAT" in Path(f).read_text():
            expected.append(f"✗ FAIL: {f} (needs formatting)")
        else:
            expected.append(f"✓ PASS: {f}")
    lines = [l for l in section.splitlines() if l.startswith(("✓", "✗"))]
    assert lines[:-1] == expected
    assert lines[-1] == f"✗ FAIL: {len(bad)} file(s) have formatting issues"
    assert f"Format:   {len(bad)} file(s) need formatting" in out
    # Far fewer than one process per file plus a retry each.
    assert len(_format_calls(log)) < 40


def test_fix_mode_uses_batched_in_place_calls(tmp_path, stub_env):
    env, log = stub_env
    src = _make_tree(tmp_path, 40)

    code, out = _run(src, env, "--fix")

    assert code == 0
    calls = _format_calls(log)
    assert len(calls) <= 4, calls
    assert all(c.startswith("-i ") for c in calls)
    assert sum(len(c.split()) - 2 for c in calls) == 40
    section = _format_section(out)
    for f in _discovery_order(src):
        assert f"✓ PASS: Formatted: {f}" in section


def test_fix_mode_failure_is_per_file(tmp_path, stub_env):
    env, _ = stub_env
    src = _make_tree(tmp_path, 10, bad={4})

    code, out = _run(src, env, "--fix")

    assert code == 1
    bad_file = next(f for f in _discovery_order(src) if "BADFORMAT" in Path(f).read_text())
    section = _format_section(out)
    assert f"✗ FAIL: Could not format: {bad_file}" in section
    assert section.count("✓ PASS: Formatted:") == 9


def test_single_job_matches_parallel_output(tmp_path, stub_env):
    env, _ = stub_env
    src = _make_tree(tmp_path, 25, bad={0, 12, 24})

    serial = _run(src, env, jobs="1")
    parallel = _run(src, env, jobs="8")

    assert serial == parallel


@pytest.mark.skipif(shutil.which("clang-format") is None, reason="clang-format not installed")
def test_real_fix_mode_matches_per_file_formatting(tmp_path):
    batched = tmp_path / "batched"
    reference = tmp_path / "reference"
    shutil.copytree(PROJECT_ROOT / "examples", batched)
    shutil.copytree(PROJECT_ROOT / "examples", reference)
    for f in sorted(reference.rglob("*.[ch]")):
        subprocess.run(
            ["clang-format", "-i", f"--style=file:{PROJECT_ROOT}/.clang-format", str(f)],
            check=True,
        )

    subprocess.run(["bash", str(VALIDATE), str(batched), "--fix"], capture_output=True)

    for f in sorted(reference.rglob("*.[ch]")):
        assert (batched / f.relative_to(reference)).read_text() == f.read_text()


def test_long_paths_split_by_xargs_byte_limit_keep_pairing(tmp_path, stub_env):
    env, _ = stub_env
    deep = tmp_path
    for _ in range(12):
        deep = deep / ("d" * 200)
    deep.mkdir(parents=True)
    src = _make_tree(deep, 120, bad={7, 77})

    code, out = _run(src, env, jobs="1")

    assert code == 1
    section = _format_section(out)
    lines = [l for l in section.splitlines() if l.startswith(("✓", "✗"))]
    assert len(lines) == 121
    assert lines[-1] == "✗ FAIL: 2 file(s) have formatting issues"
    assert sum("(needs formatting)" in l for l in lines) == 2
