# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Centralized SIGTERM handling: forwards SIGTERM to the active child subprocess, then exits.

SIGINT deliberately isn't handled here. Python's default disposition
already raises ``KeyboardInterrupt`` in the main thread on SIGINT, and two
things already do the right thing with that, for free:

- ``services.process.run()`` kills its own child subprocess on any
  exception raised while waiting for it (mirroring
  ``subprocess.run()``'s own behavior -- CPython's implementation kills
  its child in a bare ``except:`` clause explicitly commented "Including
  KeyboardInterrupt, communicate handled that").
- ``cli.main.cli_main()``'s own ``except KeyboardInterrupt`` prints a
  message and exits with code 130.

Installing a custom ``signal.signal(SIGINT, ...)`` handler would only get
in the way of both of those: a raw OS-level handler runs instead of Python
raising the exception, so none of the normal ``except``/``finally``/
context-manager unwinding gets a chance to run.

SIGTERM is different: Python's default disposition for it is immediate
termination, with no exception raised and no chance for any cleanup code
to run at all -- so it does need an explicit handler here. Forwarding to
whatever child is currently running and then waiting for it is
deliberately unbounded (no timeout, no forced kill): some operations this
CLI shells out to (``uv sync``, docker image pulls, ``copier`` template
rendering) can legitimately take a long time, and a fixed grace period
would just as often kill a healthy operation as a stuck one.
"""

from __future__ import annotations

import signal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import subprocess

_active_process: subprocess.Popen[Any] | None = None
_installed = False


def register_active_process(process: subprocess.Popen[Any]) -> None:
    """Record the currently-running child subprocess, so a SIGTERM can be forwarded to it.

    Called by ``services.process.run()`` around every subprocess it spawns.
    Overwrites any previous registration -- oarepo-cli only ever runs one
    subprocess at a time (no concurrent/background children), so there's
    at most one to track.
    """
    global _active_process
    _active_process = process


def unregister_active_process() -> None:
    """Clear the active child subprocess record once it has finished."""
    global _active_process
    _active_process = None


def _forward_sigterm(signum: int, _frame: object) -> None:
    """Forward SIGTERM to the active child subprocess (if any), then exit.

    Waits for the child to actually terminate before this process exits --
    deliberately unbounded, see the module docstring.
    """
    process = _active_process
    if process is not None and process.poll() is None:
        process.send_signal(signum)
        process.wait()
    raise SystemExit(128 + signum)


def install() -> None:
    """Install the SIGTERM handler. Idempotent -- call once, at CLI startup."""
    global _installed
    if _installed:
        return
    signal.signal(signal.SIGTERM, _forward_sigterm)
    _installed = True
