# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for ServerRunner: command/argv/env construction, and real process replacement.

`os.execve`/`os.execvpe` replace the *calling* process, so the real syscall
can't be exercised safely within the pytest worker itself -- most tests here
mock `invenio_cli.exec_invenio_cli`/`os.execve` to verify the right
binary/argv/env would be used, without ever actually replacing anything.
`test_run_no_celery_real_exec_replaces_process` and
`test_run_with_celery_real_exec_replaces_process` additionally drive the
real `os.execve`/`os.execvpe` call for real, each in its own isolated
subprocess (a small driver script run via `sys.executable`) against a tiny
real, local, executable fake binary -- proving the actual process
replacement, argv, env, and cwd wiring all work, without touching the dev
venv's own real `invenio`/`invenio-cli` or risking the test runner itself.
"""

from __future__ import annotations

import stat
import subprocess
import sys
from typing import TYPE_CHECKING, Any

import pytest

from oarepo_cli.core.config import CliConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services.server import ServerRunner

if TYPE_CHECKING:
    from pathlib import Path

FAKE_BINARY_SCRIPT = """#!/bin/sh
echo "CWD:$(pwd)"
echo "ARGV:$@"
echo "CERT:$INVENIO_SITE_CERT_PATH"
echo "KEY:$INVENIO_SITE_KEY_PATH"
echo "FLASK_DEBUG:$FLASK_DEBUG"
exit 42
"""


def make_context(root: Path) -> ProjectContext:
    return ProjectContext(
        root_directory=root,
        pyproject_path=root / "pyproject.toml",
        venv_path=root / ".venv",
        python_binary=root / ".venv" / "bin" / "python",
        oarepo_version=14,
        config=CliConfig(),
    )


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """An empty repository root directory, for ServerRunner tests that need a real path."""
    root = tmp_path / "repo"
    root.mkdir()
    return root


@pytest.fixture
def mock_services_start(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Mock invenio_cli.run_invenio_cli (used only for `services start`)."""
    calls: list[list[str]] = []

    def fake(context: object, args: list[str], **kwargs: Any) -> None:  # noqa: ARG001
        calls.append(list(args))

    monkeypatch.setattr("oarepo_cli.services.server.invenio_cli.run_invenio_cli", fake)
    return calls


@pytest.fixture
def mock_exec_invenio_cli(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Mock invenio_cli.exec_invenio_cli so it records the call instead of exec'ing."""
    calls: list[dict[str, Any]] = []

    def fake(context: object, args: list[str], *, env: dict[str, str] | None = None) -> None:  # noqa: ARG001
        calls.append({"args": list(args), "env": env})

    monkeypatch.setattr("oarepo_cli.services.server.invenio_cli.exec_invenio_cli", fake)
    return calls


@pytest.fixture
def mock_exec_bare_invenio(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Mock os.execve/os.chdir at the server module, so no real chdir/exec occurs."""
    calls: list[dict[str, Any]] = []

    def fake_execve(path: str, argv: list[str], env: dict[str, str]) -> None:
        calls.append({"path": path, "argv": argv, "env": env})

    monkeypatch.setattr("oarepo_cli.services.server.os.execve", fake_execve)
    monkeypatch.setattr("oarepo_cli.services.server.os.chdir", lambda _path: None)
    return calls


def test_run_starts_services_when_not_skipped(
    repo_root: Path,
    mock_services_start: list[list[str]],
    mock_exec_invenio_cli: list[dict[str, Any]],  # noqa: ARG001
) -> None:
    """run() starts Docker services via invenio-cli before running the server."""
    context = make_context(repo_root)
    ServerRunner(context, quiet=True).run()

    assert mock_services_start == [["services", "start"]]


def test_run_skips_services_when_no_services(
    repo_root: Path,
    mock_services_start: list[list[str]],
    mock_exec_invenio_cli: list[dict[str, Any]],  # noqa: ARG001
) -> None:
    """run(no_services=True) doesn't start Docker services."""
    context = make_context(repo_root)
    ServerRunner(context, quiet=True).run(no_services=True)

    assert mock_services_start == []


def test_run_with_celery_delegates_to_exec_invenio_cli(
    repo_root: Path,
    mock_services_start: list[list[str]],  # noqa: ARG001
    mock_exec_invenio_cli: list[dict[str, Any]],
) -> None:
    """Without --no-celery, run() hands off to invenio_cli.exec_invenio_cli(["run", ...])
    with cert/key env vars."""
    context = make_context(repo_root)
    ServerRunner(context, quiet=True).run(extra_args=["--debugger"])

    assert len(mock_exec_invenio_cli) == 1
    assert mock_exec_invenio_cli[0]["args"] == ["run", "--debugger"]
    env = mock_exec_invenio_cli[0]["env"]
    assert env["INVENIO_SITE_CERT_PATH"] == str(repo_root / "docker" / "development.crt")
    assert env["INVENIO_SITE_KEY_PATH"] == str(repo_root / "docker" / "development.key")


def test_run_no_celery_execs_bare_invenio_binary(
    repo_root: Path,
    mock_services_start: list[list[str]],  # noqa: ARG001
    mock_exec_bare_invenio: list[dict[str, Any]],
) -> None:
    """--no-celery bypasses invenio-cli entirely, exec'ing the venv's own invenio binary
    directly, with FLASK_DEBUG/PYTHONWARNINGS set and --cert/--key passed."""
    context = make_context(repo_root)
    ServerRunner(context, quiet=True).run(no_celery=True, extra_args=["-p", "5001"])

    assert len(mock_exec_bare_invenio) == 1
    call = mock_exec_bare_invenio[0]
    invenio_path = repo_root / ".venv" / "bin" / "invenio"
    assert call["path"] == str(invenio_path)
    assert call["argv"] == [
        str(invenio_path),
        "run",
        "--cert",
        str(repo_root / "docker" / "development.crt"),
        "--key",
        str(repo_root / "docker" / "development.key"),
        "-p",
        "5001",
    ]
    env = call["env"]
    assert env["FLASK_DEBUG"] == "1"
    assert env["PYTHONWARNINGS"] == "ignore"
    assert env["INVENIO_SITE_CERT_PATH"] == str(repo_root / "docker" / "development.crt")


def test_run_no_celery_applies_same_env_defaults_as_blocking_calls(
    repo_root: Path,
    mock_services_start: list[list[str]],  # noqa: ARG001
    mock_exec_bare_invenio: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--no-celery's exec'd environment gets the same OAREPO_ENV_DEFAULTS/venv-stripping
    treatment any process.run() call gets, rather than being built from bare
    os.environ, which would silently miss both."""
    monkeypatch.setenv("VIRTUAL_ENV", "/oarepo-cli/own/venv")
    monkeypatch.delenv("INVENIO_APP_THEME", raising=False)
    context = make_context(repo_root)

    ServerRunner(context, quiet=True).run(no_celery=True)

    env = mock_exec_bare_invenio[0]["env"]
    assert "VIRTUAL_ENV" not in env
    assert env["INVENIO_APP_THEME"] == '["semantic-ui"]'


def test_run_no_celery_does_not_call_invenio_cli(
    repo_root: Path,
    mock_services_start: list[list[str]],  # noqa: ARG001
    mock_exec_bare_invenio: list[dict[str, Any]],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--no-celery never touches invenio-cli at all."""
    called: list[bool] = []
    monkeypatch.setattr(
        "oarepo_cli.services.server.invenio_cli.exec_invenio_cli",
        lambda *_args, **_kwargs: called.append(True),
    )

    context = make_context(repo_root)
    ServerRunner(context, quiet=True).run(no_celery=True)

    assert called == []


def _make_executable(path: Path, content: str) -> None:
    path.write_text(content)
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def test_run_no_celery_real_exec_replaces_process(repo_root: Path) -> None:
    """End-to-end: run(no_celery=True) really execve()s into the venv's own invenio
    binary, inheriting its exit code and passing cwd/argv/env correctly."""
    invenio_bin_dir = repo_root / ".venv" / "bin"
    invenio_bin_dir.mkdir(parents=True)
    _make_executable(invenio_bin_dir / "invenio", FAKE_BINARY_SCRIPT)

    driver = f"""
from pathlib import Path
from oarepo_cli.core.config import CliConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services.server import ServerRunner

root = Path({str(repo_root)!r})
context = ProjectContext(
    root_directory=root,
    pyproject_path=root / "pyproject.toml",
    venv_path=root / ".venv",
    python_binary=root / ".venv" / "bin" / "python",
    oarepo_version=14,
    config=CliConfig(),
)
ServerRunner(context, quiet=True).run(no_services=True, no_celery=True, extra_args=["-p", "5001"])
"""
    result = subprocess.run([sys.executable, "-c", driver], capture_output=True, text=True)

    assert result.returncode == 42, result.stderr
    assert f"CWD:{repo_root}" in result.stdout
    assert "ARGV:run --cert" in result.stdout
    assert "-p 5001" in result.stdout
    assert f"CERT:{repo_root / 'docker' / 'development.crt'}" in result.stdout
    assert "FLASK_DEBUG:1" in result.stdout


def test_run_with_celery_real_exec_replaces_process(repo_root: Path, tmp_path: Path) -> None:
    """End-to-end: run() (no --no-celery) really execve()s into invenio-cli, inheriting
    its exit code and passing cwd/argv/env correctly -- doesn't touch the real
    invenio-cli, only a fake one substituted in for this one subprocess."""
    fake_invenio_cli = tmp_path / "fake-invenio-cli"
    _make_executable(fake_invenio_cli, FAKE_BINARY_SCRIPT)

    driver = f"""
from pathlib import Path
import oarepo_cli.services.invenio_cli as invenio_cli_module
from oarepo_cli.core.config import CliConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services.server import ServerRunner

invenio_cli_module._invenio_cli_path = lambda: {str(fake_invenio_cli)!r}

root = Path({str(repo_root)!r})
context = ProjectContext(
    root_directory=root,
    pyproject_path=root / "pyproject.toml",
    venv_path=root / ".venv",
    python_binary=root / ".venv" / "bin" / "python",
    oarepo_version=14,
    config=CliConfig(),
)
ServerRunner(context, quiet=True).run(no_services=True, extra_args=["--debugger"])
"""
    result = subprocess.run([sys.executable, "-c", driver], capture_output=True, text=True)

    assert result.returncode == 42, result.stderr
    assert f"CWD:{repo_root}" in result.stdout
    assert "ARGV:run --debugger" in result.stdout
    assert f"CERT:{repo_root / 'docker' / 'development.crt'}" in result.stdout
