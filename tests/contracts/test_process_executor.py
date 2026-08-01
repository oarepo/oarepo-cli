# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Contract tests for ProcessExecutor implementations."""

from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from oarepo_cli.core.errors import ProcessExecutionError
from oarepo_cli.services.process import ProcessExecutor

if TYPE_CHECKING:
    from tests.fakes import FakeProcessExecutor


def test_returns_zero_exit_code_for_success(executor: ProcessExecutor) -> None:
    """Test that successful commands return exit code 0."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(["echo", "hello"], returncode=0, stdout="hello")
    result = executor.run(["echo", "hello"], check=False)
    assert result.return_code == 0


def test_captures_stdout_correctly(executor: ProcessExecutor) -> None:
    """Test that stdout is captured correctly."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["echo", "test output"],
        returncode=0,
        stdout="test output\n",
    )
    result = executor.run(["echo", "test output"], check=False)
    assert "test output" in result.stdout


def test_captures_stderr_correctly(executor: ProcessExecutor) -> None:
    """Test that stderr is captured correctly."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["fake-error-command"],
        returncode=1,
        stdout="",
        stderr="error message\n",
    )
    result = executor.run(
        ["fake-error-command"],
        check=False,
    )
    assert "error message" in result.stderr


def test_raises_on_nonzero_with_check_true(executor: ProcessExecutor) -> None:
    """Test that check=True raises ProcessExecutionError on non-zero exit."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["failing-command"],
        returncode=42,
        stdout="",
        stderr="failed",
    )
    with pytest.raises(ProcessExecutionError) as exc_info:
        executor.run(["failing-command"], check=True)

    assert exc_info.value.returncode == 42
    assert exc_info.value.command == ["failing-command"]


def test_does_not_raise_on_nonzero_with_check_false(executor: ProcessExecutor) -> None:
    """Test that check=False does not raise on non-zero exit."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["failing-command"],
        returncode=42,
        stdout="",
        stderr="failed",
    )
    result = executor.run(
        ["failing-command"],
        check=False,
    )
    assert result.return_code == 42


def test_environment_variables_passed_correctly(executor: ProcessExecutor) -> None:
    """Test that environment variables are passed to the command."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["print-env"],
        returncode=0,
        stdout="test_value\n",
    )
    executor.run(
        ["print-env"],
        env={"TEST_VAR": "test_value"},
        check=False,
    )
    # Verify the environment was recorded
    assert fake.last_env is not None
    assert fake.last_env.get("TEST_VAR") == "test_value"


def test_cwd_parameter_sets_working_directory(executor: ProcessExecutor, tmp_path: Path) -> None:
    """Test that cwd parameter is recorded correctly."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["ls"],
        returncode=0,
        stdout="",
    )

    test_dir = tmp_path / "test_subdir"
    test_dir.mkdir()

    result = executor.run(
        ["ls"],
        cwd=test_dir,
        check=False,
    )
    assert fake.last_cwd == test_dir
    assert result.cwd == test_dir


def test_command_is_stored_in_result(executor: ProcessExecutor) -> None:
    """Test that the command is stored in ProcessResult."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["echo", "test"],
        returncode=0,
        stdout="test",
    )
    result = executor.run(["echo", "test"], check=False)
    assert "echo" in result.command
    assert "test" in result.command


def test_duration_is_positive(executor: ProcessExecutor) -> None:
    """Test that duration_ms is always positive."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["echo", "test"],
        returncode=0,
        stdout="test",
        duration_ms=50,
    )
    result = executor.run(["echo", "test"], check=False)
    assert result.duration_ms >= 0


def test_success_property_returns_true_for_zero_exit(executor: ProcessExecutor) -> None:
    """Test that success property returns True for exit code 0."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["success-command"],
        returncode=0,
        stdout="ok",
    )
    result = executor.run(["success-command"], check=False)
    assert result.success is True


def test_success_property_returns_false_for_nonzero_exit(executor: ProcessExecutor) -> None:
    """Test that success property returns False for non-zero exit code."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["fail-command"],
        returncode=1,
        stderr="error",
    )
    result = executor.run(["fail-command"], check=False)
    assert result.success is False


def test_check_method_raises_on_failure(executor: ProcessExecutor) -> None:
    """Test that check() method raises ProcessExecutionError on failure."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["fail-command"],
        returncode=1,
        stderr="error",
    )
    result = executor.run(["fail-command"], check=False)

    with pytest.raises(ProcessExecutionError):
        result.check()


def test_check_method_returns_self_on_success(executor: ProcessExecutor) -> None:
    """Test that check() method returns self on success."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["success-command"],
        returncode=0,
        stdout="ok",
    )
    result = executor.run(["success-command"], check=False)

    checked = result.check()
    assert checked is result


def test_get_output_returns_stripped_stdout(executor: ProcessExecutor) -> None:
    """Test that get_output returns stripped stdout."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["python", "-c", 'print("hello world")'],
        returncode=0,
        stdout="hello world\n",
    )
    output = executor.get_output(["python", "-c", 'print("hello world")'])
    assert output == "hello world"


def test_stream_yields_lines(executor: ProcessExecutor) -> None:
    """Test that stream yields output lines."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["multi-line-command"],
        returncode=0,
        stdout="line1\nline2\nline3\n",
        stderr="error1\n",
    )
    lines = list(executor.stream(["multi-line-command"]))
    assert "line1" in lines
    assert "line2" in lines
    assert "line3" in lines


def test_capture_output_false_returns_empty_strings(executor: ProcessExecutor) -> None:
    """Test that capture_output=False returns empty stdout/stderr."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["some-command"],
        returncode=0,
        stdout="should be hidden",
        stderr="also hidden",
    )
    result = executor.run(["some-command"], capture_output=False, check=False)
    assert result.stdout == ""
    assert result.stderr == ""


def test_forward_stdout_parameter_is_recorded(executor: ProcessExecutor) -> None:
    """Test that forward_stdout parameter is accepted (even if ignored)."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["streaming-command"],
        returncode=0,
        stdout="streaming output\n",
    )
    # Should not raise even though we don't actually stream
    result = executor.run(
        ["streaming-command"],
        forward_stdout=True,
        check=False,
    )
    assert result.return_code == 0


def test_timeout_parameter_is_accepted(executor: ProcessExecutor) -> None:
    """Test that timeout parameter is accepted (even if ignored in fake)."""
    fake = cast("FakeProcessExecutor", executor)
    fake.register_response(
        ["slow-command"],
        returncode=0,
        stdout="done",
    )
    # Should not raise even though we don't actually enforce timeout
    result = executor.run(
        ["slow-command"],
        timeout=30.0,
        check=False,
    )
    assert result.return_code == 0
