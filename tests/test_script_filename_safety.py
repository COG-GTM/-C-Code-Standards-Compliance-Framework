"""
Regression tests: filenames from the scanned tree must never be word-split
into extra (option-looking) arguments for clang-format / clang-tidy, and
must never break out of compile_commands.json strings.

Run: pytest tests/test_script_filename_safety.py -v
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

INJECTED_NAME = "a --load=x.so.c"
COMPLIANT_SOURCE = "int main(void)\n{\n    return 0;\n}\n"

# Records each argv as one NUL-terminated record of NUL-separated arguments.
STUB_TOOL = """#!/bin/bash
{
    printf '%s\\0' "$(basename "$0")" "$@"
    printf '\\n\\0'
} >> "$ARGV_LOG"
exit 0
"""


def _read_invocations(log_path):
    if not log_path.exists():
        return []
    invocations = []
    current = []
    for arg in log_path.read_bytes().split(b"\0"):
        if arg == b"\n":
            invocations.append(current)
            current = []
        elif arg:
            current.append(arg.decode())
    return invocations


@pytest.fixture
def stub_env(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("clang-format", "clang-tidy"):
        stub = bin_dir / tool
        stub.write_text(STUB_TOOL)
        stub.chmod(0o755)
    log_path = tmp_path / "argv.log"
    env = dict(os.environ)
    env["PATH"] = "%s%s%s" % (bin_dir, os.pathsep, env.get("PATH", ""))
    env["ARGV_LOG"] = str(log_path)
    return env, log_path


@pytest.fixture
def hostile_tree(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / INJECTED_NAME).write_text(COMPLIANT_SOURCE)
    (src / "x.so.c").write_text(COMPLIANT_SOURCE)
    (src / "-leading.c").write_text(COMPLIANT_SOURCE)
    return src


@pytest.mark.parametrize("mode", [[], ["--fix"]])
def test_validate_passes_each_filename_as_one_argument(stub_env, hostile_tree, mode):
    env, log_path = stub_env
    subprocess.run(
        [str(SCRIPTS_DIR / "validate.sh"), ".", *mode],
        cwd=hostile_tree, env=env, capture_output=True, text=True, check=False,
    )
    invocations = _read_invocations(log_path)
    tools = {inv[0] for inv in invocations}
    assert tools == {"clang-format", "clang-tidy"}

    for inv in invocations:
        args = inv[1:]
        assert "--load=x.so.c" not in args, inv
        assert "./a" not in args, inv
        assert not any(a == "-leading.c" for a in args), inv

    tidy_operands = [inv[2] for inv in invocations if inv[0] == "clang-tidy"]
    assert sorted(tidy_operands) == sorted(
        ["./" + INJECTED_NAME, "./x.so.c", "./-leading.c"]
    )
    for inv in invocations:
        if inv[0] == "clang-tidy":
            assert inv[3] == "--", inv

    format_operands = [inv[-1] for inv in invocations if inv[0] == "clang-format"]
    assert set(format_operands) == {"./" + INJECTED_NAME, "./x.so.c", "./-leading.c"}
    for inv in invocations:
        if inv[0] == "clang-format":
            assert inv[-2] == "--", inv


def test_safe_path_prefixes_leading_dash():
    script = SCRIPTS_DIR / "validate.sh"
    body = script.read_text()
    start = body.index("safe_path() {")
    end = body.index("\n}\n", start) + 3
    result = subprocess.run(
        ["bash", "-c", body[start:end] + 'safe_path "-x.c"; echo; safe_path "src/a.c"'],
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.splitlines() == ["./-x.c", "src/a.c"]


@pytest.mark.skipif(
    shutil.which("bear") is not None,
    reason="bear installed; manual compile_commands generation not exercised",
)
def test_compile_commands_stays_valid_json_with_hostile_names(tmp_path):
    (tmp_path / INJECTED_NAME).write_text(COMPLIANT_SOURCE)
    (tmp_path / 'q", "-fplugin=x.so.c').write_text(COMPLIANT_SOURCE)
    (tmp_path / "ok.c").write_text(COMPLIANT_SOURCE)
    subprocess.run(
        ["bash", str(SCRIPTS_DIR / "generate-compile-commands.sh")],
        cwd=tmp_path, capture_output=True, text=True, check=True,
    )
    entries = json.loads((tmp_path / "compile_commands.json").read_text())
    files = sorted(Path(e["file"]).name for e in entries)
    assert files == sorted([INJECTED_NAME, "ok.c"])
    for entry in entries:
        assert not any("-fplugin" in a for a in entry["arguments"])
