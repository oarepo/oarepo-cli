# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Repository development server execution, with graceful signal handling."""

from __future__ import annotations

import signal
import subprocess
from typing import TYPE_CHECKING

from oarepo_cli.core.platform import get_platform_detector
from oarepo_cli.services import invenio_cli, process
from oarepo_cli.ui import ConsoleOutput

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path
    from types import FrameType

    from oarepo_cli.core.context import ProjectContext

_CHILD_TERMINATE_TIMEOUT_SECONDS = 10


class ServerRunner:
    """Runs the repository's development server.

    Mirrors ``repository_runner.sh``'s ``run_server()``:
    1. Starts Docker services (``invenio-cli services start``), unless
       ``no_services``
    2. Either delegates to ``invenio-cli run`` (which manages Celery itself),
       or -- if ``no_celery`` -- runs the venv's own ``invenio run`` directly,
       bypassing invenio-cli and Celery entirely
    3. Either way, ``INVENIO_SITE_CERT_PATH``/``INVENIO_SITE_KEY_PATH`` point
       at ``docker/development.{crt,key}``

    Unlike the bash version (which simply runs the server as the shell's own
    foreground process and lets a terminal Ctrl+C kill it directly), this
    spawns the server as a tracked child process and installs SIGINT/SIGTERM
    handlers that forward the signal to it, wait for a graceful exit, and
    escalate to SIGKILL if it doesn't exit in time -- needed because a signal
    sent specifically to this process (e.g. ``kill <pid>``, not a terminal
    Ctrl+C) wouldn't otherwise reach the child on its own.

    Per an explicit product decision, Docker services are deliberately *not*
    auto-stopped when the server exits or is interrupted, despite
    01-detailed-design.md's state diagram suggesting otherwise: bash's
    ``run_server()`` never stops them either (Ctrl+C just kills the
    foreground process, services stay up for the next command, exactly like
    the ``library`` domain's pattern), and 03-migration-guide.md explicitly
    promises "Identical behavior" for ``run``. Users stop services explicitly
    via ``repository services stop``.
    """

    def __init__(self, context: ProjectContext, *, quiet: bool = False) -> None:
        """Initialize the server runner.

        Args:
            context: Project context with paths and configuration
            quiet: If True, suppress status/progress messages (never
                applies to the server's own output, which always streams
                live)
        """
        self._context = context
        self._quiet = quiet
        self._child: subprocess.Popen[bytes] | None = None

    def run(
        self,
        *,
        no_services: bool = False,
        no_celery: bool = False,
        extra_args: Sequence[str] = (),
    ) -> int:
        """Start Docker services (unless skipped) and run the server in the foreground.

        Blocks until the server process exits (normally or via a forwarded
        SIGINT/SIGTERM), then returns its exit code.

        Args:
            no_services: If True, don't start Docker services first
            no_celery: If True, run the venv's own ``invenio run`` directly
                (no Celery worker) instead of ``invenio-cli run``
            extra_args: Extra arguments forwarded to the underlying
                ``invenio-cli run``/``invenio run`` command

        Returns:
            The server process's exit code

        Raises:
            ProcessExecutionError: If starting Docker services fails
        """
        console = ConsoleOutput(quiet=self._quiet)

        if not no_services:
            console.info("→ Starting Docker services...\n")
            invenio_cli.run_invenio_cli(self._context, ["services", "start"], quiet=self._quiet)

        cert_path = self._context.root_directory / "docker" / "development.crt"
        key_path = self._context.root_directory / "docker" / "development.key"
        site_env = {
            "INVENIO_SITE_CERT_PATH": str(cert_path),
            "INVENIO_SITE_KEY_PATH": str(key_path),
        }

        console.info("→ Starting server...\n")

        previous_sigint = signal.signal(signal.SIGINT, self._forward_signal)
        previous_sigterm = signal.signal(signal.SIGTERM, self._forward_signal)
        try:
            if no_celery:
                self._child = self._popen_bare_invenio(cert_path, key_path, site_env, extra_args)
            else:
                self._child = invenio_cli.popen_invenio_cli(
                    self._context, ["run", *extra_args], env=site_env
                )
            return self._child.wait()
        finally:
            signal.signal(signal.SIGINT, previous_sigint)
            signal.signal(signal.SIGTERM, previous_sigterm)
            self._child = None

    def _popen_bare_invenio(
        self,
        cert_path: Path,
        key_path: Path,
        site_env: dict[str, str],
        extra_args: Sequence[str],
    ) -> subprocess.Popen[bytes]:
        """Run the venv's own ``invenio run`` directly, bypassing invenio-cli/Celery.

        Mirrors ``repository_runner.sh``'s ``--no-celery`` branch: sets
        ``FLASK_DEBUG``/``PYTHONWARNINGS`` and invokes the venv's ``invenio``
        binary directly with ``--cert``/``--key``.
        """
        bin_dir = get_platform_detector().get_venv_bin_dir()
        invenio_path = self._context.venv_path / bin_dir / "invenio"
        command = [
            str(invenio_path),
            "run",
            "--cert",
            str(cert_path),
            "--key",
            str(key_path),
            *extra_args,
        ]
        env = {**site_env, "FLASK_DEBUG": "1", "PYTHONWARNINGS": "ignore"}
        return process.popen(command, cwd=self._context.root_directory, env=env)

    def _forward_signal(self, signum: int, _frame: FrameType | None) -> None:
        """Forward a received SIGINT/SIGTERM to the running server child, if any.

        Sends the same signal first (graceful shutdown), then escalates to
        SIGKILL if the child hasn't exited within
        ``_CHILD_TERMINATE_TIMEOUT_SECONDS``.
        """
        child = self._child
        if child is None or child.poll() is not None:
            return

        child.send_signal(signum)
        try:
            child.wait(timeout=_CHILD_TERMINATE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
