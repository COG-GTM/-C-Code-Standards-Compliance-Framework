"""
Framework coverage plugin.

Lives at the repository root so that a bare ``pytest`` invocation registers
the options below (pytest only loads conftest files from the command line
arguments and the rootdir before parsing options).

Tests declare the framework artifacts they exercise with the ``covers``
fixture::

    def test_rule_documented(covers):
        covers("rule:Rule 20", "file:docs/rule-reference.md")

Declarations only count when the declaring test passes. At the end of a run
the plugin prints shell line coverage and artifact coverage and writes
``coverage-summary.json``; ``--framework-cov-fail-under`` turns the artifact
metric into a hard gate for CI.
"""

from pathlib import Path

import pytest

from tests import framework_coverage as fc

PROJECT_ROOT = fc.PROJECT_ROOT

COVERS_KEY = pytest.StashKey[list]()


def pytest_addoption(parser):
    group = parser.getgroup("framework coverage")
    group.addoption(
        "--framework-cov-fail-under",
        type=float,
        default=None,
        help="Fail the run if artifact coverage is below this percentage.",
    )
    group.addoption(
        "--framework-cov-json",
        default=None,
        help="Write the coverage summary to this JSON file.",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "covers(*artifact_ids): framework artifacts asserted by this test"
    )
    config._shell_coverage = fc.ShellCoverage()
    config._artifact_coverage = fc.ArtifactCoverage.build()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.passed:
        return

    declared = list(item.stash.get(COVERS_KEY, []))
    for marker in item.iter_markers(name="covers"):
        declared.extend(marker.args)
    if declared:
        item.config._artifact_coverage.add(declared)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    shell = config._shell_coverage
    artifacts = config._artifact_coverage

    summary_path = config.getoption("--framework-cov-json") or (
        PROJECT_ROOT / "coverage-summary.json"
    )
    payload = fc.write_summary(summary_path, shell, artifacts)

    write = terminalreporter.write_line
    write("")
    write("=" * 70)
    write("Framework coverage")
    write("=" * 70)

    for script, stats in payload["shell_line_coverage"].items():
        write(
            f"  shell  {script:<40} "
            f"{stats['percent']:6.1f}%  ({stats['covered']}/{stats['total']} lines)"
        )
    write(f"  shell  {'TOTAL':<40} {payload['shell_line_coverage_percent']:6.1f}%")

    for kind, stats in payload["artifact_coverage"].items():
        write(
            f"  {kind:<6} {'covered by assertions':<40} "
            f"{stats['percent']:6.1f}%  ({stats['covered']}/{stats['total']})"
        )
    write(f"  total  {'artifact coverage':<40} {payload['artifact_coverage_percent']:6.1f}%")

    unknown = artifacts.unknown_declarations()
    if unknown:
        write(f"  WARNING: unknown artifact declarations: {', '.join(unknown)}")

    write(f"  summary written to {Path(summary_path).name}")


def pytest_sessionfinish(session, exitstatus):
    threshold = session.config.getoption("--framework-cov-fail-under")
    if threshold is None:
        return
    percent = session.config._artifact_coverage.total_percent()
    if percent + 1e-9 < threshold:
        session.exitstatus = 1
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line(
                f"FAIL: artifact coverage {percent:.1f}% is below the "
                f"required {threshold:.1f}%",
                red=True,
            )


@pytest.fixture
def covers(request):
    """Declare the framework artifacts a test asserts on."""
    def declare(*artifact_ids):
        request.node.stash.setdefault(COVERS_KEY, [])
        request.node.stash[COVERS_KEY].extend(artifact_ids)

    return declare
