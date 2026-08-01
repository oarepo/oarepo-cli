# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for oarepo_cli.services.process.

process.run()/stream()/get_output() are plain functions with exactly one real
implementation, so they are exercised directly against real, trivial,
always-available commands (echo, true, false, python3 -c ...) rather than
through an injected executor or a hand-written fake.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from oarepo_cli.core.errors import ProcessExecutionError, TimeoutExceeded
from oarepo_cli.services import process

if TYPE_CHECKING:
    from pathlib import Path


def test_returns_zero_exit_code_for_success() -> None:
    result = process.run(["echo", "hello"], check=False)
    assert result.return_code == 0


def test_captures_stdout_correctly() -> None:
    result = process.run(["echo", "test output"], check=False)
    assert "test output" in result.stdout


def test_captures_stderr_correctly() -> None:
    result = process.run(
        ["python3", "-c", 'import sys; print("error", file=sys.stderr)'],
        check=False,
    )
    assert "error" in result.stderr


def test_raises_on_nonzero_with_check_true() -> None:
    with pytest.raises(ProcessExecutionError) as exc_info:
        process.run(["python3", "-c", "import sys; sys.exit(42)"], check=True)

    assert exc_info.value.returncode == 42
    assert exc_info.value.command == ["python3", "-c", "import sys; sys.exit(42)"]


def test_does_not_raise_on_nonzero_with_check_false() -> None:
    result = process.run(["python3", "-c", "import sys; sys.exit(42)"], check=False)
    assert result.return_code == 42


def test_environment_variables_passed_correctly() -> None:
    result = process.run(
        ["python3", "-c", "import os; print(os.environ.get('TEST_VAR', ''))"],
        env={"TEST_VAR": "test_value"},
        check=False,
    )
    assert result.stdout.strip() == "test_value"


def test_cwd_parameter_sets_working_directory(tmp_path: Path) -> None:
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    result = process.run(["cat", "test.txt"], cwd=tmp_path, check=False)

    assert "content" in result.stdout
    assert result.cwd == tmp_path


def test_command_is_stored_in_result() -> None:
    result = process.run(["echo", "test"], check=False)
    assert "echo" in result.command
    assert "test" in result.command


def test_duration_is_positive() -> None:
    result = process.run(["echo", "test"], check=False)
    assert result.duration_ms >= 0


def test_success_property_returns_true_for_zero_exit() -> None:
    result = process.run(["true"], check=False)
    assert result.success is True


def test_success_property_returns_false_for_nonzero_exit() -> None:
    result = process.run(["false"], check=False)
    assert result.success is False


def test_check_method_raises_on_failure() -> None:
    result = process.run(["false"], check=False)

    with pytest.raises(ProcessExecutionError):
        result.check()


def test_check_method_returns_self_on_success() -> None:
    result = process.run(["true"], check=False)

    checked = result.check()
    assert checked is result


def test_get_output_returns_stripped_stdout() -> None:
    output = process.get_output(["echo", "hello world"])
    assert output == "hello world"


def test_stream_yields_lines() -> None:
    lines = list(
        process.stream(["python3", "-c", "print('line1'); print('line2'); print('line3')"])
    )
    assert "line1" in lines
    assert "line2" in lines
    assert "line3" in lines


def test_stream_sets_pythonunbuffered_by_default() -> None:
    lines = list(
        process.stream(["python3", "-c", "import os; print(os.environ.get('PYTHONUNBUFFERED'))"])
    )
    assert lines == ["1"]


def test_stream_allows_overriding_pythonunbuffered() -> None:
    lines = list(
        process.stream(
            ["python3", "-c", "import os; print(os.environ.get('PYTHONUNBUFFERED'))"],
            env={"PYTHONUNBUFFERED": "0"},
        )
    )
    assert lines == ["0"]


def test_capture_output_false_returns_empty_strings() -> None:
    result = process.run(["echo", "hidden"], capture_output=False, check=False)
    assert result.stdout == ""
    assert result.stderr == ""


def test_forward_stdout_parameter_is_accepted() -> None:
    result = process.run(["echo", "test"], forward_stdout=True, check=False)
    assert result.return_code == 0


def test_timeout_does_not_raise_when_command_completes_in_time() -> None:
    result = process.run(["echo", "quick"], timeout=30.0, check=False)
    assert result.return_code == 0


def test_timeout_raises_timeout_exceeded() -> None:
    with pytest.raises(TimeoutExceeded) as exc_info:
        process.run(
            ["python3", "-c", "import time; time.sleep(5)"],
            timeout=0.1,
            check=True,
        )

    assert exc_info.value.timeout == 0.1
    assert "time" in str(exc_info.value.command)


def test_shell_injection_prevented() -> None:
    """Ensure arguments are not interpreted as shell commands."""
    result = process.run(["echo", "; rm -rf /"], check=False)

    # The output should contain the literal string, not have executed rm
    assert "; rm -rf /" in result.stdout
    assert result.return_code == 0


def test_utf8_encoding_handled_correctly() -> None:
    result = process.run(["python3", "-c", "print('Hello 世界 🌍')"], check=False)

    assert "世界" in result.stdout
    assert "🌍" in result.stdout
