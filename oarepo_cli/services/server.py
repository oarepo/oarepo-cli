# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Repository development server execution."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, NoReturn

from oarepo_cli.services import invenio_cli, process, repository
from oarepo_cli.ui import ConsoleOutput

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from oarepo_cli.core.context import ProjectContext


class ServerRunner:
    """Runs the repository's development server.

    Mirrors ``repository_runner.sh``'s ``run_server()``:
    1. Starts Docker services (``invenio-cli services start``), unless
       ``no_services``
    2. Replaces this process (``os.execve``/``os.execvpe``) with either
       ``invenio-cli run`` (which manages Celery itself) or -- if
       ``no_celery`` -- the venv's own ``invenio run`` directly, bypassing
       invenio-cli and Celery entirely
    3. Either way, ``INVENIO_SITE_CERT_PATH``/``INVENIO_SITE_KEY_PATH`` point
       at ``docker/development.{crt,key}``

    Uses process replacement rather than spawning a tracked child process,
    mirroring ``cli/library.py``'s ``library_shell``/``library_invenio``
    (and bash's own ``run_server()``, where ``invenio-cli run``/``invenio
    run`` is simply the last foreground command the script runs): the
    installed invenio-cli's own ``run`` command already spawns and
    gracefully signal-handles its own child processes (web server, Celery
    worker, jobs scheduler -- see
    ``invenio_cli.commands.local.LocalCommands._handle_sigint``), on the
    assumption that *it* is the terminal's own foreground process. An
    earlier version of this module instead spawned invenio-cli as a
    supervised child and forwarded SIGINT/SIGTERM to it -- strictly worse:
    invenio-cli's own children only ever listen for SIGINT, so a forwarded
    SIGTERM would never have cleanly cascaded to them anyway, and the extra
    layer only risked double-handling. Process replacement sidesteps the
    whole problem by making invenio-cli/invenio literally the process a
    terminal Ctrl+C (or a signal sent to this process's own PID) hits
    directly.

    As with any exec-based command, ``run()`` never returns on success.
    Docker services are deliberately not stopped first or on any later exit
    -- see ``03-migration-guide.md``'s "Identical behavior" promise for
    ``run``, and bash's own ``run_server()``, which never stops them either.
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

    def run(
        self,
        *,
        no_services: bool = False,
        no_celery: bool = False,
        extra_args: Sequence[str] = (),
    ) -> NoReturn:
        """Start Docker services (unless skipped), then replace this process with the server.

        Never returns on success -- the process image is replaced.

        Args:
            no_services: If True, don't start Docker services first
            no_celery: If True, run the venv's own ``invenio run`` directly
                (no Celery worker) instead of ``invenio-cli run``
            extra_args: Extra arguments forwarded to the underlying
                ``invenio-cli run``/``invenio run`` command

        Raises:
            ProcessExecutionError: If starting Docker services fails
            OSError: If exec'ing the server binary fails

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

        if no_celery:
            self._exec_bare_invenio(cert_path, key_path, site_env, extra_args)
        else:
            invenio_cli.exec_invenio_cli(self._context, ["run", *extra_args], env=site_env)

    def _exec_bare_invenio(
        self,
        cert_path: Path,
        key_path: Path,
        site_env: dict[str, str],
        extra_args: Sequence[str],
    ) -> NoReturn:
        """Replace this process with the venv's own ``invenio run``, bypassing invenio-cli/Celery.

        Mirrors ``repository_runner.sh``'s ``--no-celery`` branch: sets
        ``FLASK_DEBUG``/``PYTHONWARNINGS`` and execs the venv's ``invenio``
        binary directly with ``--cert``/``--key``.
        """
        os.chdir(self._context.root_directory)
        invenio_path = repository.get_invenio_binary(self._context)
        argv = [
            str(invenio_path),
            "run",
            "--cert",
            str(cert_path),
            "--key",
            str(key_path),
            *extra_args,
        ]
        env = process.build_subprocess_env({**site_env, "FLASK_DEBUG": "1", "PYTHONWARNINGS": "ignore"})
        os.execve(str(invenio_path), argv, env)  # noqa S606 no shell is ok here, replacing the process
