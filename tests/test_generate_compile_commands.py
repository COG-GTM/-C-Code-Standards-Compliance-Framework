"""
Tests for scripts/generate-compile-commands.sh (manual generation path).

Verifies that hostile filenames cannot inject compiler arguments into
compile_commands.json and that paths with spaces/globs are kept intact.

Run: pytest tests/test_generate_compile_commands.py -v
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "generate-compile-commands.sh"

INJECTION_NAME = 'x","-include","evil.h","y.c'
HOSTILE_NAMES = [
    INJECTION_NAME,
    "with space.c",
    "star*.c",
    "back\\slash.cpp",
    "new\nline.cc",
    "plain.c",
]

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("python3") is None,
    reason="bash and python3 required",
)


def run_script(target: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), str(target)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def load_db(target: Path):
    return json.loads((target / "compile_commands.json").read_text())


@pytest.fixture
def hostile_tree(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    for name in HOSTILE_NAMES:
        (src / name).write_text("int x;\n")
    (tmp_path / "inc").mkdir()
    return tmp_path


def test_output_is_valid_json_with_one_entry_per_file(hostile_tree):
    result = run_script(hostile_tree)
    assert result.returncode == 0, result.stdout + result.stderr

    db = load_db(hostile_tree)
    expected = sorted(str(hostile_tree / "src" / n) for n in HOSTILE_NAMES)
    assert sorted(e["file"] for e in db) == expected
    assert f"with {len(HOSTILE_NAMES)} entries" in result.stdout


def test_filenames_cannot_inject_compiler_arguments(hostile_tree):
    assert run_script(hostile_tree).returncode == 0

    for entry in load_db(hostile_tree):
        abs_file = entry["file"]
        args = entry["arguments"]
        assert entry["directory"] == str(hostile_tree)
        assert args[1:5] == [
            "-c",
            "-std=c17" if abs_file.endswith(".c") else "-std=c++17",
            "-Wall",
            "-Wextra",
        ]
        assert args[5:10] == ["-I.", "-I./include", "-I./src", "-I./inc", abs_file]
        assert args[10] == "-o"
        assert args[11] == abs_file.rsplit(".", 1)[0] + ".o"
        assert len(args) == 12
        assert "-include" not in args
        assert "evil.h" not in args


def test_template_escapes_directory(tmp_path):
    target = tmp_path / 'dir","-include","evil.h'
    target.mkdir()
    result = run_script(target)
    assert result.returncode == 0, result.stdout + result.stderr

    db = load_db(target)
    assert len(db) == 1
    assert db[0]["directory"] == str(target)
    assert db[0]["file"] == str(target / "src" / "main.c")
    assert "-include" not in db[0]["arguments"]
