# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for ServerRunner: command construction, and real signal-handling behavior.

There's no real invenio-cli/invenio install to run the actual server
against here, so `invenio_cli.popen_invenio_cli`/the venv `invenio` binary
are replaced with small real, local, long-running processes (`python -c
"import time; time.sleep(...)"`) -- this exercises the real
Popen/signal-forwarding/timeout-escalation machinery (the whole point of
this module) against a real child process, rather than mocking it away,
while still being fast and not depending on invenio being installed.
"""

from __future__ import annotations

import signal
import subprocess
import sys
import threading
import time
from typing import TYPE_CHECKING, Any

import pytest

from oarepo_cli.core.config import CliConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services.server import ServerRunner

if TYPE_CHECKING:
    from pathlib import Path

SLEEP_100 = [sys.executable, "-c", "import time; time.sleep(100)"]


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
def mock_popen_invenio_cli(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Mock invenio_cli.popen_invenio_cli to spawn a real, short-lived local process."""
    calls: list[dict[str, Any]] = []

    def fake(context: object, args: list[str], *, env: dict[str, str] | None = None):  # noqa: ARG001
        calls.append({"args": list(args), "env": env})
        return subprocess.Popen([sys.executable, "-c", "print('ok')"])

    monkeypatch.setattr("oarepo_cli.services.server.invenio_cli.popen_invenio_cli", fake)
    return calls


def test_run_starts_services_when_not_skipped(
    repo_root: Path,
    mock_services_start: list[list[str]],
    mock_popen_invenio_cli: list[dict[str, Any]],  # noqa: ARG001
) -> None:
    """run() starts Docker services via invenio-cli before running the server."""
    context = make_context(repo_root)
    runner = ServerRunner(context, quiet=True)

    runner.run()

    assert mock_services_start == [["services", "start"]]


def test_run_skips_services_when_no_services(
    repo_root: Path,
    mock_services_start: list[list[str]],
    mock_popen_invenio_cli: list[dict[str, Any]],  # noqa: ARG001
) -> None:
    """run(no_services=True) doesn't start Docker services."""
    context = make_context(repo_root)
    runner = ServerRunner(context, quiet=True)

    runner.run(no_services=True)

    assert mock_services_start == []


def test_run_with_celery_delegates_to_invenio_cli_run(
    repo_root: Path,
    mock_services_start: list[list[str]],  # noqa: ARG001
    mock_popen_invenio_cli: list[dict[str, Any]],
) -> None:
    """Without --no-celery, run() delegates to `invenio-cli run` with cert/key env vars."""
    context = make_context(repo_root)
    runner = ServerRunner(context, quiet=True)

    runner.run(extra_args=["--debugger"])

    assert len(mock_popen_invenio_cli) == 1
    assert mock_popen_invenio_cli[0]["args"] == ["run", "--debugger"]
    env = mock_popen_invenio_cli[0]["env"]
    assert env["INVENIO_SITE_CERT_PATH"] == str(repo_root / "docker" / "development.crt")
    assert env["INVENIO_SITE_KEY_PATH"] == str(repo_root / "docker" / "development.key")


def test_run_returns_child_exit_code(
    repo_root: Path,
    mock_services_start: list[list[str]],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run() blocks until the server child exits and returns its exit code."""
    context = make_context(repo_root)
    runner = ServerRunner(context, quiet=True)

    def fake_popen_invenio_cli(context: object, args: list[str], **kwargs: Any):  # noqa: ARG001
        return subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(7)"])

    monkeypatch.setattr(
        "oarepo_cli.services.server.invenio_cli.popen_invenio_cli", fake_popen_invenio_cli
    )

    exit_code = runner.run()

    assert exit_code == 7


def test_run_no_celery_uses_bare_invenio_binary(
    repo_root: Path,
    mock_services_start: list[list[str]],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--no-celery bypasses invenio-cli entirely, running the venv's own invenio binary
    directly, with FLASK_DEBUG/PYTHONWARNINGS set and --cert/--key passed."""
    context = make_context(repo_root)
    runner = ServerRunner(context, quiet=True)

    popen_calls: list[dict[str, Any]] = []
    real_popen = subprocess.Popen

    def fake_popen(command: list[str], *, cwd: object = None, env: dict[str, str] | None = None):
        popen_calls.append({"command": command, "cwd": cwd, "env": env})
        return real_popen([sys.executable, "-c", "print('ok')"])

    monkeypatch.setattr("oarepo_cli.services.server.process.popen", fake_popen)

    runner.run(no_celery=True, extra_args=["-p", "5001"])

    assert len(popen_calls) == 1
    command = popen_calls[0]["command"]
    invenio_path = repo_root / ".venv" / "bin" / "invenio"
    assert command[0] == str(invenio_path)
    assert command[1:] == [
        "run",
        "--cert",
        str(repo_root / "docker" / "development.crt"),
        "--key",
        str(repo_root / "docker" / "development.key"),
        "-p",
        "5001",
    ]
    env = popen_calls[0]["env"]
    assert env["FLASK_DEBUG"] == "1"
    assert env["PYTHONWARNINGS"] == "ignore"
    assert env["INVENIO_SITE_CERT_PATH"] == str(repo_root / "docker" / "development.crt")


def test_signal_forwarding_terminates_child(
    repo_root: Path,
    mock_services_start: list[list[str]],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A SIGINT/SIGTERM received while the server is running is forwarded to the real
    child process, and run() returns (rather than blocking forever) once it exits."""
    context = make_context(repo_root)
    runner = ServerRunner(context, quiet=True)

    def fake_popen_invenio_cli(context: object, args: list[str], **kwargs: Any):  # noqa: ARG001
        return subprocess.Popen(SLEEP_100)

    monkeypatch.setattr(
        "oarepo_cli.services.server.invenio_cli.popen_invenio_cli", fake_popen_invenio_cli
    )

    def send_signal_shortly_after_start() -> None:
        # Wait for run() to have installed its handler and spawned the child.
        while runner._child is None:  # noqa: SLF001
            time.sleep(0.01)
        runner._forward_signal(signal.SIGTERM, None)  # noqa: SLF001

    thread = threading.Thread(target=send_signal_shortly_after_start)
    thread.start()

    start = time.monotonic()
    exit_code = runner.run()
    elapsed = time.monotonic() - start
    thread.join()

    assert exit_code != 0  # killed by signal, didn't run to completion
    assert elapsed < 5, "child should have been terminated well before the 100s sleep completed"


def test_signal_handlers_restored_after_run(
    repo_root: Path,
    mock_services_start: list[list[str]],  # noqa: ARG001
    mock_popen_invenio_cli: list[dict[str, Any]],  # noqa: ARG001
) -> None:
    """run() restores the previous SIGINT/SIGTERM handlers afterward, rather than
    leaking its own handler for the rest of the process's lifetime."""
    context = make_context(repo_root)
    runner = ServerRunner(context, quiet=True)

    original_sigint = signal.getsignal(signal.SIGINT)
    original_sigterm = signal.getsignal(signal.SIGTERM)

    runner.run()

    assert signal.getsignal(signal.SIGINT) is original_sigint
    assert signal.getsignal(signal.SIGTERM) is original_sigterm


def test_forward_signal_escalates_to_kill_on_timeout(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the child doesn't exit within the grace period, _forward_signal kills it."""
    monkeypatch.setattr("oarepo_cli.services.server._CHILD_TERMINATE_TIMEOUT_SECONDS", 0.05)
    context = make_context(repo_root)
    runner = ServerRunner(context, quiet=True)

    from unittest.mock import Mock

    child = Mock()
    child.poll.return_value = None
    child.wait.side_effect = [subprocess.TimeoutExpired(cmd="x", timeout=0.05), 0]
    runner._child = child  # noqa: SLF001

    runner._forward_signal(signal.SIGTERM, None)  # noqa: SLF001

    child.send_signal.assert_called_once_with(signal.SIGTERM)
    child.kill.assert_called_once()


def test_forward_signal_noop_if_no_child_running(repo_root: Path) -> None:
    """_forward_signal is a no-op if there's no child (or it already exited)."""
    context = make_context(repo_root)
    runner = ServerRunner(context, quiet=True)

    runner._forward_signal(signal.SIGTERM, None)  # noqa: SLF001
