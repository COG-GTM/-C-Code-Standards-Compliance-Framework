"""
Behavioural tests for scripts/generate-compile-commands.sh.

clangd is useless without a compilation database, so each generation strategy
the script advertises (CMake, Bear, manual scan, minimal template) is driven
through a throwaway project.
"""

import json
import shutil

import pytest

from tests import framework_coverage as fc
from tests.conftest import requires_bash

pytestmark = requires_bash

SCRIPT = "scripts/generate-compile-commands.sh"

SOURCE = """\
#include <stdio.h>

int main(void)
{
    printf("hello\\n");
    return 0;
}
"""


def load_database(workspace):
    return json.loads(workspace.read("compile_commands.json"))


class TestManualGeneration:
    """The fallback used by projects without CMake or Bear."""

    def test_generates_an_entry_per_source_file(self, c_workspace, run_script, covers):
        covers("file:scripts/generate-compile-commands.sh")
        c_workspace.write("src/main.c", SOURCE)
        c_workspace.write("src/util.c", SOURCE)

        result = run_script(SCRIPT, ["."], cwd=c_workspace.path)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "Generated compile_commands.json with 2 entries" in result.stdout

        database = load_database(c_workspace)
        assert len(database) == 2
        assert {entry["file"].split("/")[-1] for entry in database} == {"main.c", "util.c"}

    def test_entries_are_valid_json_with_required_keys(self, c_workspace, run_script, covers):
        covers("file:scripts/generate-compile-commands.sh", "file:.clangd")
        c_workspace.write("main.c", SOURCE)

        run_script(SCRIPT, ["."], cwd=c_workspace.path)

        entry = load_database(c_workspace)[0]
        assert set(entry) == {"directory", "file", "arguments"}
        assert entry["file"].endswith("main.c")
        assert entry["arguments"][0] in {"clang", "gcc", "cc"}
        assert "-c" in entry["arguments"]

    def test_c_sources_use_c17_and_cpp_sources_use_cpp17(self, c_workspace, run_script):
        c_workspace.write("main.c", SOURCE)
        c_workspace.write("main.cpp", SOURCE)

        run_script(SCRIPT, ["."], cwd=c_workspace.path)

        standards = {
            entry["file"].split(".")[-1]: [
                argument for argument in entry["arguments"] if argument.startswith("-std=")
            ]
            for entry in load_database(c_workspace)
        }
        assert standards["c"] == ["-std=c17"]
        assert standards["cpp"] == ["-std=c++17"]

    def test_build_and_vendor_directories_are_excluded(self, c_workspace, run_script):
        c_workspace.write("main.c", SOURCE)
        c_workspace.write("build/generated.c", SOURCE)
        c_workspace.write("third_party/dep.c", SOURCE)
        c_workspace.write("vendor/lib.c", SOURCE)

        run_script(SCRIPT, ["."], cwd=c_workspace.path)

        files = [entry["file"] for entry in load_database(c_workspace)]
        assert len(files) == 1
        assert files[0].endswith("main.c")

    def test_warning_flags_are_always_enabled(self, c_workspace, run_script):
        c_workspace.write("main.c", SOURCE)

        run_script(SCRIPT, ["."], cwd=c_workspace.path)

        arguments = load_database(c_workspace)[0]["arguments"]
        assert "-Wall" in arguments
        assert "-Wextra" in arguments


class TestTemplateFallback:
    """When there is nothing to scan the script still leaves a usable stub."""

    def test_template_is_created_for_an_empty_project(self, c_workspace, run_script, covers):
        covers("file:scripts/generate-compile-commands.sh")
        result = run_script(SCRIPT, ["."], cwd=c_workspace.path)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "No C/C++ source files found" in result.stdout
        assert "Created template compile_commands.json" in result.stdout

        database = load_database(c_workspace)
        assert len(database) == 1
        assert database[0]["file"].endswith("src/main.c")

    def test_template_tells_the_user_to_edit_it(self, c_workspace, run_script):
        result = run_script(SCRIPT, ["."], cwd=c_workspace.path)

        assert "Edit this file to match your project structure" in result.stdout


class TestTargetDirectory:
    """The optional directory argument."""

    def test_defaults_to_the_current_directory(self, c_workspace, run_script):
        c_workspace.write("main.c", SOURCE)

        result = run_script(SCRIPT, [], cwd=c_workspace.path)

        assert result.returncode == 0
        assert (c_workspace.path / "compile_commands.json").exists()

    def test_generates_inside_the_requested_directory(self, c_workspace, run_script):
        c_workspace.write("project/main.c", SOURCE)

        result = run_script(SCRIPT, ["project"], cwd=c_workspace.path)

        assert result.returncode == 0, result.stdout
        assert (c_workspace.path / "project" / "compile_commands.json").exists()
        assert not (c_workspace.path / "compile_commands.json").exists()

    def test_reports_the_working_directory_and_project_root(self, c_workspace, run_script):
        c_workspace.write("main.c", SOURCE)

        result = run_script(SCRIPT, ["."], cwd=c_workspace.path)

        assert "Working directory:" in result.stdout
        assert "Project root:" in result.stdout


@pytest.mark.skipif(shutil.which("cmake") is None, reason="cmake not installed")
class TestCMakeGeneration:
    """CMake is the preferred strategy when the project provides it."""

    def test_cmake_project_uses_cmake(self, c_workspace, run_script, covers):
        covers("file:scripts/generate-compile-commands.sh")
        c_workspace.write("main.c", SOURCE)
        c_workspace.write(
            "CMakeLists.txt",
            "cmake_minimum_required(VERSION 3.10)\n"
            "project(coverage_probe C)\n"
            "add_executable(coverage_probe main.c)\n",
        )

        result = run_script(SCRIPT, ["."], cwd=c_workspace.path)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "using CMake" in result.stdout
        assert (c_workspace.path / "compile_commands.json").exists()

    def test_broken_cmake_project_falls_back(self, c_workspace, run_script):
        c_workspace.write("main.c", SOURCE)
        c_workspace.write("CMakeLists.txt", "this is not valid cmake\n")

        result = run_script(SCRIPT, ["."], cwd=c_workspace.path)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "CMake generation failed, trying alternatives" in result.stdout
        assert (c_workspace.path / "compile_commands.json").exists()


class TestScriptContract:
    """Static guarantees the documentation relies on."""

    def test_script_is_documented_and_fails_fast(self, covers):
        covers("file:scripts/generate-compile-commands.sh")
        content = (fc.PROJECT_ROOT / SCRIPT).read_text(encoding="utf-8")

        assert content.startswith("#!/bin/bash")
        assert "set -e" in content
        assert "Usage:" in content

    def test_all_advertised_strategies_exist(self):
        content = (fc.PROJECT_ROOT / SCRIPT).read_text(encoding="utf-8")

        for function in (
            "generate_with_cmake", "generate_with_bear",
            "generate_manually", "create_template",
        ):
            assert f"{function}()" in content, f"Missing strategy: {function}"
