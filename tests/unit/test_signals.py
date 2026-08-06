# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Unit tests for core.signals: SIGTERM forwarding to the active child subprocess.

SIGINT deliberately has no custom handler here (see the module docstring)
-- there's nothing to test for it in this module; services.process.run()'s
own child-killing behavior on KeyboardInterrupt is covered in
test_process.py instead, alongside the SIGTERM-forwarding integration test
(a real, separate worker process is needed there since actually raising
the SystemExit this module's handler raises would abort the test run
itself).
"""

from __future__ import annotations

import signal
import subprocess
import sys

import pytest

from oarepo_cli.core import signals


@pytest.fixture(autouse=True)
def _reset_signals_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test with a clean module-level registry."""
    monkeypatch.setattr(signals, "_active_process", None)
    monkeypatch.setattr(signals, "_installed", False)


def test_register_and_unregister_active_process() -> None:
    """register_active_process()/unregister_active_process() set/clear the module registry."""
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        signals.register_active_process(proc)
        assert signals._active_process is proc  # noqa: SLF001

        signals.unregister_active_process()
        assert signals._active_process is None  # noqa: SLF001
    finally:
        proc.kill()
        proc.wait()


def test_forward_sigterm_signals_and_waits_for_active_process() -> None:
    """Forward sigterm signals and waits for active process.

    The registered child is sent SIGTERM and actually reaped before the
    handler exits -- not left running.
    """
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    signals.register_active_process(proc)

    with pytest.raises(SystemExit) as exc_info:
        signals._forward_sigterm(signal.SIGTERM, None)  # noqa: SLF001

    assert exc_info.value.code == 128 + signal.SIGTERM
    assert proc.poll() is not None


def test_forward_sigterm_without_active_process_just_exits() -> None:
    """Forward sigterm without active process just exits.

    With no registered child, the handler just exits, without erroring.
    """
    with pytest.raises(SystemExit) as exc_info:
        signals._forward_sigterm(signal.SIGTERM, None)  # noqa: SLF001

    assert exc_info.value.code == 128 + signal.SIGTERM


def test_forward_sigterm_skips_already_finished_process() -> None:
    """Forward sigterm skips already finished process.

    A registered process that already exited isn't signaled again.
    """
    proc = subprocess.Popen([sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()
    signals.register_active_process(proc)

    with pytest.raises(SystemExit):
        signals._forward_sigterm(signal.SIGTERM, None)  # noqa: SLF001


def test_install_registers_sigterm_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    """install() registers _forward_sigterm as the SIGTERM handler."""
    calls: list[tuple[int, object]] = []
    monkeypatch.setattr(signal, "signal", lambda sig, handler: calls.append((sig, handler)))

    signals.install()

    assert calls == [(signal.SIGTERM, signals._forward_sigterm)]  # noqa: SLF001


def test_install_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, object]] = []
    monkeypatch.setattr(signal, "signal", lambda sig, handler: calls.append((sig, handler)))

    signals.install()
    signals.install()

    assert len(calls) == 1
