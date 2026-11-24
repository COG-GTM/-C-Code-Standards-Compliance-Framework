"""generate-compile-commands.sh must not run project build code unless --use-build is given."""

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "generate-compile-commands.sh"


def _write_exec(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def untrusted(tmp_path):
    """A project tree whose CMakeLists.txt, Makefile, make and bear all leave a marker when run."""
    proj = tmp_path / "proj"
    (proj / "src").mkdir(parents=True)
    (proj / "src" / "main.c").write_text("int main(void) { return 0; }\n")
    marker = tmp_path / "marker"
    (proj / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.10)\n"
        "project(evil C)\n"
        f'execute_process(COMMAND sh -c "echo cmake-ran >> {marker}")\n'
    )
    (proj / "Makefile").write_text(
        f"all:\n\t@echo make-ran >> {marker}\nclean:\n\t@echo make-clean-ran >> {marker}\n"
    )
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _write_exec(bindir / "bear", f'#!/bin/sh\necho bear-ran >> "{marker}"\nshift\nexec "$@"\n')
    if shutil.which("cmake") is None:
        _write_exec(bindir / "cmake", f'#!/bin/sh\necho cmake-ran >> "{marker}"\nexit 1\n')
    env = dict(os.environ, PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}")
    return proj, marker, env


def _run(proj, env, *args):
    return subprocess.run(
        ["bash", str(SCRIPT), *args, str(proj)], env=env, capture_output=True, text=True, timeout=120
    )


def _ran(marker):
    return marker.read_text().split() if marker.exists() else []


def test_default_does_not_run_cmake(untrusted):
    proj, marker, env = untrusted
    result = _run(proj, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _ran(marker) == []
    assert not (proj / "build").exists()
    assert "--use-build" in result.stdout


def test_default_does_not_run_make_or_bear(untrusted):
    proj, marker, env = untrusted
    (proj / "CMakeLists.txt").unlink()
    result = _run(proj, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _ran(marker) == []


def test_default_writes_valid_manual_database(untrusted):
    proj, _, env = untrusted
    assert _run(proj, env).returncode == 0
    entries = json.loads((proj / "compile_commands.json").read_text())
    main_c = str((proj / "src" / "main.c").resolve())
    assert [e["file"] for e in entries] == [main_c]
    args = entries[0]["arguments"]
    assert {"-I.", "-I./include", "-I./src"} <= set(args)
    assert main_c in args


def test_use_build_opts_in_to_cmake(untrusted):
    proj, marker, env = untrusted
    result = _run(proj, env, "--use-build")
    assert "cmake-ran" in _ran(marker), result.stdout + result.stderr
    assert "trusted" in result.stdout


def test_use_build_opts_in_to_bear(untrusted):
    proj, marker, env = untrusted
    (proj / "CMakeLists.txt").unlink()
    result = _run(proj, env, "--use-build")
    assert result.returncode == 0, result.stdout + result.stderr
    assert {"bear-ran", "make-clean-ran", "make-ran"} <= set(_ran(marker))


def test_unknown_option_is_rejected(untrusted):
    proj, marker, env = untrusted
    result = _run(proj, env, "--use-buld")
    assert result.returncode == 2
    assert _ran(marker) == []
    assert not (proj / "compile_commands.json").exists()
