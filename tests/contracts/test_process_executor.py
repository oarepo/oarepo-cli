# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Contract tests for ProcessExecutor implementations.

These tests verify that all ProcessExecutor implementations satisfy the
protocol contract using real command execution (for subprocess) or
simulated responses (for fake).
"""

from pathlib import Path

import pytest

from oarepo_cli.core.errors import ProcessExecutionError
from oarepo_cli.services.process import ProcessExecutor


def test_returns_zero_exit_code_for_success(executor: ProcessExecutor) -> None:
    """Test that successful commands return exit code 0."""
    # Use echo which should always succeed
    result = executor.run(["echo", "hello"], check=False)
    assert result.return_code == 0


def test_captures_stdout_correctly(executor: ProcessExecutor) -> None:
    """Test that stdout is captured correctly."""
    result = executor.run(["echo", "test output"], check=False)
    assert "test output" in result.stdout


def test_captures_stderr_correctly(executor: ProcessExecutor) -> None:
    """Test that stderr is captured correctly."""
    result = executor.run(
        ["python3", "-c", 'import sys; print("error", file=sys.stderr)'],
        check=False,
    )
    assert "error" in result.stderr


def test_raises_on_nonzero_with_check_true(executor: ProcessExecutor) -> None:
    """Test that check=True raises ProcessExecutionError on non-zero exit."""
    with pytest.raises(ProcessExecutionError) as exc_info:
        executor.run(["false"], check=True)  # 'false' always exits with 1

    assert exc_info.value.returncode == 1
    assert "false" in exc_info.value.command


def test_does_not_raise_on_nonzero_with_check_false(executor: ProcessExecutor) -> None:
    """Test that check=False does not raise on non-zero exit."""
    result = executor.run(["false"], check=False)
    assert result.return_code == 1


def test_environment_variables_passed_correctly(executor: ProcessExecutor, tmp_path: Path) -> None:
    """Test that environment variables are passed to the command."""
    # Create a temp script that prints an env var
    script = tmp_path / "print_env.py"
    script.write_text("import os; print(os.environ.get('TEST_VAR', ''))")

    result = executor.run(
        ["python3", str(script)],
        env={"TEST_VAR": "test_value"},
        check=False,
    )
    assert result.stdout.strip() == "test_value"


def test_cwd_parameter_sets_working_directory(executor: ProcessExecutor, tmp_path: Path) -> None:
    """Test that cwd parameter sets the working directory."""
    # Create a file in tmp_path
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    result = executor.run(
        ["cat", "test.txt"],
        cwd=tmp_path,
        check=False,
    )
    assert "content" in result.stdout
    assert result.cwd == tmp_path


def test_command_is_stored_in_result(executor: ProcessExecutor) -> None:
    """Test that the command is stored in ProcessResult."""
    result = executor.run(["echo", "test"], check=False)
    assert "echo" in result.command
    assert "test" in result.command


def test_duration_is_positive(executor: ProcessExecutor) -> None:
    """Test that duration_ms is always positive."""
    result = executor.run(["echo", "test"], check=False)
    assert result.duration_ms >= 0


def test_success_property_returns_true_for_zero_exit(executor: ProcessExecutor) -> None:
    """Test that success property returns True for exit code 0."""
    result = executor.run(["true"], check=False)  # 'true' always exits with 0
    assert result.success is True


def test_success_property_returns_false_for_nonzero_exit(executor: ProcessExecutor) -> None:
    """Test that success property returns False for non-zero exit code."""
    result = executor.run(["false"], check=False)
    assert result.success is False


def test_check_method_raises_on_failure(executor: ProcessExecutor) -> None:
    """Test that check() method raises ProcessExecutionError on failure."""
    result = executor.run(["false"], check=False)

    with pytest.raises(ProcessExecutionError):
        result.check()


def test_check_method_returns_self_on_success(executor: ProcessExecutor) -> None:
    """Test that check() method returns self on success."""
    result = executor.run(["true"], check=False)

    checked = result.check()
    assert checked is result


def test_get_output_returns_stripped_stdout(executor: ProcessExecutor) -> None:
    """Test that get_output returns stripped stdout."""
    output = executor.get_output(["echo", "hello world"])
    assert output == "hello world"


def test_stream_yields_lines(executor: ProcessExecutor) -> None:
    """Test that stream yields output lines."""
    lines = list(
        executor.stream(["python3", "-c", "print('line1'); print('line2'); print('line3')"])
    )
    assert "line1" in lines
    assert "line2" in lines
    assert "line3" in lines


def test_capture_output_false_returns_empty_strings(executor: ProcessExecutor) -> None:
    """Test that capture_output=False returns empty stdout/stderr."""
    result = executor.run(["echo", "hidden"], capture_output=False, check=False)
    assert result.stdout == ""
    assert result.stderr == ""


def test_forward_stdout_parameter_is_accepted(executor: ProcessExecutor) -> None:
    """Test that forward_stdout parameter is accepted."""
    # Should not raise even though behavior differs between implementations
    result = executor.run(["echo", "test"], forward_stdout=True, check=False)
    assert result.return_code == 0


def test_timeout_parameter_is_accepted(executor: ProcessExecutor) -> None:
    """Test that timeout parameter is accepted."""
    # Quick command that completes before timeout
    result = executor.run(["echo", "quick"], timeout=30.0, check=False)
    assert result.return_code == 0
