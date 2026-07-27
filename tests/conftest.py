"""
Shared fixtures.

The coverage plugin itself (including the ``covers`` fixture) lives in the
repository root conftest.py.
"""

import shutil
import subprocess

import pytest
import yaml

from tests import framework_coverage as fc

PROJECT_ROOT = fc.PROJECT_ROOT
EXAMPLES_DIR = PROJECT_ROOT / "examples"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DOCS_DIR = PROJECT_ROOT / "docs"


# =============================================================================
# Tool availability
# =============================================================================

def tool_available(name):
    return shutil.which(name) is not None


requires_clang_format = pytest.mark.skipif(
    not tool_available("clang-format"), reason="clang-format not installed"
)

requires_clang_tidy = pytest.mark.skipif(
    not tool_available("clang-tidy"), reason="clang-tidy not installed"
)

requires_bash = pytest.mark.skipif(
    fc.find_bash() is None, reason="bash not available"
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def project_root():
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def severity_mapping():
    return fc.load_severity_mapping()


@pytest.fixture(scope="session")
def clang_format_config():
    path = PROJECT_ROOT / ".clang-format"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def clang_tidy_config():
    path = PROJECT_ROOT / ".clang-tidy"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def clangd_config():
    path = PROJECT_ROOT / ".clangd"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def vscode_settings_template():
    path = PROJECT_ROOT / "vscode-settings.json.template"
    return fc.parse_jsonc(path.read_text(encoding="utf-8"))


@pytest.fixture
def run_script(request):
    """Run a framework shell script with shell line coverage tracing."""
    coverage = request.config._shell_coverage

    def runner(script, args=(), cwd=None, env=None):
        return fc.run_script(script, args=args, cwd=cwd, coverage=coverage, env=env)

    return runner


class CWorkspace:
    """A throwaway project directory seeded with the framework's config."""

    def __init__(self, path):
        self.path = path

    def write(self, name, content):
        path = self.path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        return path

    def read(self, name):
        return (self.path / name).read_text(encoding="utf-8")


@pytest.fixture
def c_workspace(tmp_path):
    """
    A throwaway directory seeded with the framework's clang configuration so
    scripts behave exactly as they would inside a consuming project.
    """
    for config in (".clang-format", ".clang-tidy"):
        shutil.copy(PROJECT_ROOT / config, tmp_path / config)
    return CWorkspace(tmp_path)


def clang_tidy_output(source_path, extra_args=()):
    """Run clang-tidy with the framework config and return combined output."""
    completed = subprocess.run(
        [
            "clang-tidy",
            f"--config-file={PROJECT_ROOT / '.clang-tidy'}",
            str(source_path),
            "--",
            "-I.",
            *extra_args,
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout + completed.stderr
