# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for oarepo_cli.services.process.

process.run()/get_output() are plain functions with exactly one real
implementation, so they are exercised directly against real, trivial,
always-available commands (echo, true, false, python3 -c ...) rather than
through an injected executor or a hand-written fake.
"""

from __future__ import annotations

import multiprocessing
import os
import signal
import sys
import time
from typing import TYPE_CHECKING

import pytest

from oarepo_cli.core.errors import ProcessExecutionError
from oarepo_cli.services import process

if TYPE_CHECKING:
    from pathlib import Path


def test_returns_zero_exit_code_for_success() -> None:
    """A successful command reports return_code 0."""
    result = process.run(["echo", "hello"], check=False)
    assert result.return_code == 0


def test_captures_stdout_correctly() -> None:
    """Captured stdout contains the command's actual output."""
    result = process.run(["echo", "test output"], check=False)
    assert "test output" in result.stdout


def test_captures_stderr_correctly() -> None:
    """Captured stderr contains output the command wrote there specifically."""
    result = process.run(
        ["python3", "-c", 'import sys; print("error", file=sys.stderr)'],
        check=False,
    )
    assert "error" in result.stderr


def test_raises_on_nonzero_with_check_true() -> None:
    """check=True (the default) raises ProcessExecutionError with the real returncode/command."""
    with pytest.raises(ProcessExecutionError) as exc_info:
        process.run(["python3", "-c", "import sys; sys.exit(42)"], check=True)

    assert exc_info.value.returncode == 42
    assert exc_info.value.command == ["python3", "-c", "import sys; sys.exit(42)"]


def test_does_not_raise_on_nonzero_with_check_false() -> None:
    """check=False returns the ProcessResult instead of raising on a non-zero exit."""
    result = process.run(["python3", "-c", "import sys; sys.exit(42)"], check=False)
    assert result.return_code == 42


def test_environment_variables_passed_correctly() -> None:
    """A custom env dict is visible to the child process."""
    result = process.run(
        ["python3", "-c", "import os; print(os.environ.get('TEST_VAR', ''))"],
        env={"TEST_VAR": "test_value"},
        check=False,
    )
    assert result.stdout.strip() == "test_value"


def test_cwd_parameter_sets_working_directory(tmp_path: Path) -> None:
    """The command actually runs in cwd, and cwd is recorded on the result."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    result = process.run(["cat", "test.txt"], cwd=tmp_path, check=False)

    assert "content" in result.stdout
    assert result.cwd == tmp_path


def test_command_is_stored_in_result() -> None:
    """The exact command list given is available on the returned result."""
    result = process.run(["echo", "test"], check=False)
    assert "echo" in result.command
    assert "test" in result.command


def test_duration_is_positive() -> None:
    """duration_ms is a non-negative measurement of how long the command took."""
    result = process.run(["echo", "test"], check=False)
    assert result.duration_ms >= 0


def test_success_property_returns_true_for_zero_exit() -> None:
    """.success is True for a zero exit code."""
    result = process.run(["true"], check=False)
    assert result.success is True


def test_success_property_returns_false_for_nonzero_exit() -> None:
    """.success is False for a non-zero exit code."""
    result = process.run(["false"], check=False)
    assert result.success is False


def test_check_method_raises_on_failure() -> None:
    """ProcessResult.check() raises ProcessExecutionError for a failed result."""
    result = process.run(["false"], check=False)

    with pytest.raises(ProcessExecutionError):
        result.check()


def test_check_method_returns_self_on_success() -> None:
    """ProcessResult.check() returns the same instance when the command succeeded."""
    result = process.run(["true"], check=False)

    checked = result.check()
    assert checked is result


def test_get_output_returns_stripped_stdout() -> None:
    """get_output() returns just stdout, with surrounding whitespace stripped."""
    output = process.get_output(["echo", "hello world"])
    assert output == "hello world"


def test_capture_output_false_returns_empty_strings() -> None:
    """INTERACTIVE mode never captures output, so stdout/stderr are both empty strings."""
    result = process.run(
        ["echo", "hidden"], output_mode=process.ProcessOutputMode.INTERACTIVE, check=False
    )
    assert result.stdout == ""
    assert result.stderr == ""


def test_forward_output_mode_is_accepted() -> None:
    """FORWARD mode runs successfully (capturing output while also displaying it)."""
    result = process.run(
        ["echo", "test"], output_mode=process.ProcessOutputMode.FORWARD, check=False
    )
    assert result.return_code == 0


def test_shell_injection_prevented() -> None:
    """Ensure arguments are not interpreted as shell commands."""
    result = process.run(["echo", "; rm -rf /"], check=False)

    # The output should contain the literal string, not have executed rm
    assert "; rm -rf /" in result.stdout
    assert result.return_code == 0


def test_utf8_encoding_handled_correctly() -> None:
    """Non-ASCII output (CJK characters, emoji) is captured correctly as UTF-8."""
    result = process.run(["python3", "-c", "print('Hello 世界 🌍')"], check=False)

    assert "世界" in result.stdout
    assert "🌍" in result.stdout


def _sigterm_worker(child_pid_file: str) -> None:
    """Installs the real SIGTERM handler, then runs a long-lived child via process.run().

    Run in a separate process (see test below) since the handler this
    installs raises SystemExit -- doing that in the test process itself
    would abort the whole test run.
    """
    from oarepo_cli.core import signals

    signals.install()
    process.run(
        [
            sys.executable,
            "-c",
            f"import os; open({child_pid_file!r}, 'w').write(str(os.getpid())); "
            "import time; time.sleep(30)",
        ],
        check=False,
    )


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal semantics assumed")
def test_sigterm_forwarded_to_child_and_worker_exits_cleanly(tmp_path: Path) -> None:
    """A SIGTERM sent to a process that's inside process.run() is forwarded to
    its child subprocess (which is killed, not orphaned), and the process
    itself exits via SystemExit(143) rather than hanging or leaving a
    traceback."""
    child_pid_file = tmp_path / "child.pid"

    worker = multiprocessing.Process(target=_sigterm_worker, args=(str(child_pid_file),))
    worker.start()

    for _ in range(50):
        if child_pid_file.exists() and child_pid_file.read_text():
            break
        time.sleep(0.1)
    else:
        pytest.fail("child subprocess never reported its PID")
    child_pid = int(child_pid_file.read_text())

    assert worker.pid is not None
    os.kill(worker.pid, signal.SIGTERM)
    worker.join(timeout=10)

    assert worker.exitcode == 128 + signal.SIGTERM
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)
