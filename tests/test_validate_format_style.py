"""
validate.sh must always check formatting against the project .clang-format.

A failing project-style check must never be retried with clang-format's own
style discovery, which would honour a .clang-format planted in the target
tree (or LLVM defaults) and turn a real violation into a pass.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
VALIDATE = PROJECT_ROOT / "scripts" / "validate.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("clang-format") is None, reason="clang-format not installed"
)

LLVM_STYLE_SOURCE = (
    "int add(int a, int b) {\n"
    "  if (a) {\n"
    "    return a + b;\n"
    "  }\n"
    "  return b;\n"
    "}\n"
)

PROJECT_STYLE_SOURCE = (
    "int add(int a, int b)\n"
    "{\n"
    "    if (a)\n"
    "    {\n"
    "        return a + b;\n"
    "    }\n"
    "    return b;\n"
    "}\n"
)


@pytest.fixture
def target_tree(tmp_path):
    tree = tmp_path / "target"
    tree.mkdir()
    (tree / ".clang-format").write_text("BasedOnStyle: LLVM\n")
    return tree


@pytest.fixture
def pre14_path(tmp_path):
    """PATH whose clang-format rejects --style=file:<path> like clang-format < 14."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    real = shutil.which("clang-format")
    stub = bin_dir / "clang-format"
    stub.write_text(
        "#!/bin/bash\n"
        'for a in "$@"; do case "$a" in --style=file:*) '
        'echo "Invalid value for -style" >&2; exit 1;; esac; done\n'
        f'exec "{real}" "$@"\n'
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    return f"{bin_dir}{os.pathsep}{os.environ['PATH']}"


def run_validate(target, *args, path=None):
    env = dict(os.environ)
    if path:
        env["PATH"] = path
    return subprocess.run(
        [str(VALIDATE), str(target), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def format_section(output):
    return output.split("clang-format check", 1)[1].split("clang-tidy analysis", 1)[0]


@pytest.mark.parametrize("use_pre14", [False, True], ids=["style-file-path", "pre14-fallback"])
def test_planted_style_file_does_not_mask_violation(target_tree, pre14_path, use_pre14):
    (target_tree / "llvm.c").write_text(LLVM_STYLE_SOURCE)

    result = run_validate(target_tree, path=pre14_path if use_pre14 else None)

    assert "llvm.c (needs formatting)" in format_section(result.stdout)
    assert result.returncode & 1, result.stdout


@pytest.mark.parametrize("use_pre14", [False, True], ids=["style-file-path", "pre14-fallback"])
def test_project_style_source_passes(target_tree, pre14_path, use_pre14):
    (target_tree / "ok.c").write_text(PROJECT_STYLE_SOURCE)

    result = run_validate(target_tree, path=pre14_path if use_pre14 else None)

    assert "needs formatting" not in format_section(result.stdout)
    assert not result.returncode & 1, result.stdout


@pytest.mark.parametrize("use_pre14", [False, True], ids=["style-file-path", "pre14-fallback"])
def test_fix_applies_project_style_not_planted_style(target_tree, pre14_path, use_pre14):
    source = target_tree / "llvm.c"
    source.write_text(LLVM_STYLE_SOURCE)

    run_validate(target_tree, "--fix", path=pre14_path if use_pre14 else None)

    assert source.read_text() == PROJECT_STYLE_SOURCE
