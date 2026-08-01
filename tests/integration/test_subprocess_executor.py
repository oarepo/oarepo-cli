# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for SubprocessExecutor."""

from pathlib import Path

import pytest

from oarepo_cli.adapters.subprocess_executor import SubprocessExecutor
from oarepo_cli.core.errors import ProcessExecutionError, TimeoutExceeded


def test_successful_command_execution() -> None:
    """Test that successful commands return exit code 0."""
    executor = SubprocessExecutor()
    result = executor.run(["echo", "hello"], check=False)

    assert result.return_code == 0
    assert "hello" in result.stdout


def test_captures_stdout_correctly() -> None:
    """Test that stdout is captured correctly."""
    executor = SubprocessExecutor()
    result = executor.run(["echo", "test output"], check=False)

    assert "test output" in result.stdout


def test_captures_stderr_correctly() -> None:
    """Test that stderr is captured correctly."""
    executor = SubprocessExecutor()
    result = executor.run(
        ["python3", "-c", 'import sys; print("error", file=sys.stderr)'],
        check=False,
    )

    assert "error" in result.stderr


def test_raises_on_nonzero_exit_with_check_true() -> None:
    """Test that check=True raises ProcessExecutionError on non-zero exit."""
    executor = SubprocessExecutor()

    with pytest.raises(ProcessExecutionError) as exc_info:
        executor.run(["python3", "-c", "import sys; sys.exit(42)"], check=True)

    assert exc_info.value.returncode == 42
    assert exc_info.value.command == ["python3", "-c", "import sys; sys.exit(42)"]


def test_does_not_raise_on_nonzero_exit_with_check_false() -> None:
    """Test that check=False does not raise on non-zero exit."""
    executor = SubprocessExecutor()
    result = executor.run(
        ["python3", "-c", "import sys; sys.exit(42)"],
        check=False,
    )

    assert result.return_code == 42


def test_environment_variables_passed_correctly(tmp_path: Path) -> None:
    """Test that environment variables are passed to the command."""
    executor = SubprocessExecutor()

    # Create a temp script that prints an env var
    script = tmp_path / "print_env.py"
    script.write_text("import os; print(os.environ.get('TEST_VAR', ''))")

    result = executor.run(
        ["python3", str(script)],
        env={"TEST_VAR": "test_value"},
        check=False,
    )

    assert result.stdout.strip() == "test_value"


def test_cwd_parameter_sets_working_directory(tmp_path: Path) -> None:
    """Test that cwd parameter sets the working directory."""
    executor = SubprocessExecutor()

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


def test_command_is_stored_in_result() -> None:
    """Test that the command is stored in ProcessResult."""
    executor = SubprocessExecutor()
    result = executor.run(["echo", "test"], check=False)

    assert "echo" in result.command
    assert "test" in result.command


def test_duration_is_positive() -> None:
    """Test that duration_ms is always positive."""
    executor = SubprocessExecutor()
    result = executor.run(["echo", "test"], check=False)

    assert result.duration_ms >= 0


def test_success_property_returns_true_for_zero_exit() -> None:
    """Test that success property returns True for exit code 0."""
    executor = SubprocessExecutor()
    result = executor.run(["echo", "ok"], check=False)

    assert result.success is True


def test_success_property_returns_false_for_nonzero_exit() -> None:
    """Test that success property returns False for non-zero exit code."""
    executor = SubprocessExecutor()
    result = executor.run(["false"], check=False)

    assert result.success is False


def test_get_output_returns_stripped_stdout() -> None:
    """Test that get_output returns stripped stdout."""
    executor = SubprocessExecutor()
    output = executor.get_output(["echo", "hello world"])

    assert output == "hello world"


def test_stream_yields_lines() -> None:
    """Test that stream yields output lines."""
    executor = SubprocessExecutor()

    # Use python3 to print multiple lines
    lines = list(
        executor.stream(
            [
                "python3",
                "-c",
                "import sys; print('line1'); print('line2'); print('line3')",
            ]
        )
    )

    assert "line1" in lines
    assert "line2" in lines
    assert "line3" in lines


def test_timeout_raises_timeout_exceeded() -> None:
    """Test that timeout raises TimeoutExceeded exception."""
    executor = SubprocessExecutor()

    with pytest.raises(TimeoutExceeded) as exc_info:
        # Sleep for 5 seconds but timeout after 0.1 seconds
        executor.run(
            ["python3", "-c", "import time; time.sleep(5)"],
            timeout=0.1,
            check=True,
        )

    assert exc_info.value.timeout == 0.1
    assert "sleep" in str(exc_info.value.command)


def test_shell_injection_prevented() -> None:
    """Test that shell injection is prevented (args are literal, not executed)."""
    executor = SubprocessExecutor()

    # This should NOT execute "rm -rf /" as a command
    # Instead it should try to find a file literally named "; rm -rf /"
    result = executor.run(
        ["echo", "; rm -rf /"],
        check=False,
    )

    # The output should contain the literal string, not have executed rm
    assert "; rm -rf /" in result.stdout
    assert result.return_code == 0


def test_utf8_encoding_handled_correctly() -> None:
    """Test that UTF-8 encoding is handled correctly."""
    executor = SubprocessExecutor()

    # Print some UTF-8 characters
    result = executor.run(
        ["python3", "-c", "print('Hello 世界 🌍')"],
        check=False,
    )

    assert "世界" in result.stdout
    assert "🌍" in result.stdout


def test_capture_output_false_returns_empty_strings() -> None:
    """Test that capture_output=False returns empty stdout/stderr."""
    executor = SubprocessExecutor()
    result = executor.run(["echo", "hidden"], capture_output=False, check=False)

    assert result.stdout == ""
    assert result.stderr == ""
