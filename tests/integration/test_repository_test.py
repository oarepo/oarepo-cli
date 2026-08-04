# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for `repository test`, using a real venv/pytest (installed on
demand, since -- unlike a library -- a fresh repository has no "tests" extras
convention of its own).

`services.repository.run_tests()` ends by `os.execve`-ing into pytest, which
replaces the *calling* process -- exercising that for real (rather than mocking
`os.execve`, already covered in tests/unit/test_repository_service.py) means driving
it from its own isolated subprocess (a small driver script run via `sys.executable`),
never through this test's own CliRunner/pytest worker process, mirroring
test_server_runner.py's identical rationale for `ServerRunner`'s exec calls.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Typer CLI runner."""
    return CliRunner()


def test_repository_test_help_displays(runner: CliRunner) -> None:
    """Test that 'repository test --help' displays help text. Safe to drive through
    CliRunner directly: --help is intercepted by Typer before the command body (and
    any os.execve) is ever reached."""
    result = runner.invoke(app, ["repository", "test", "--help"])

    assert result.exit_code == 0
    assert "test" in result.stdout.lower()
    assert "pytest" in result.stdout.lower()


def _run_tests_in_subprocess(project_root: Path) -> subprocess.CompletedProcess[str]:
    """Call services.repository.run_tests() for real, in its own isolated subprocess."""
    driver = f"""
from pathlib import Path
from oarepo_cli.core.config import CliConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services.repository import run_tests

root = Path({str(project_root)!r})
context = ProjectContext(
    root_directory=root,
    pyproject_path=root / "pyproject.toml",
    venv_path=root / ".venv",
    python_binary=root / ".venv" / "bin" / "python3.14",
    oarepo_version=14,
    config=CliConfig(),
)
run_tests(context, quiet=True)
"""
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", driver], capture_output=True, text=True
    )


def test_repository_test_runs_real_pytest_and_installs_it_on_demand(
    lint_project_multi_module: Path,
) -> None:
    """`run_tests()` installs pytest into the venv (missing by default in a fresh
    repository fixture) and then really execs into it, end to end, in its own
    isolated subprocess -- inheriting pytest's own exit code."""
    tests_dir = lint_project_multi_module / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_pass():\n    assert True\n")

    result = _run_tests_in_subprocess(lint_project_multi_module)

    assert result.returncode == 0, result.stderr


def test_repository_test_exit_code_on_failure(lint_project_multi_module: Path) -> None:
    """A failing test makes the subprocess exit with pytest's own non-zero code."""
    tests_dir = lint_project_multi_module / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text(
        "def test_fail():\n    assert False, 'this test fails'\n"
    )

    result = _run_tests_in_subprocess(lint_project_multi_module)

    assert result.returncode != 0
