# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest

from oarepo_cli.core.errors import (
    ConfigurationError,
    FileNotFoundError,
    LockAcquisitionError,
    OARepoError,
    ProcessExecutionError,
    ValidationError,
    VersionMismatchError,
    safe_run,
)


class TestExceptionHierarchy:
    """Test that each exception type can be raised and caught."""

    def test_base_exception_can_be_raised(self) -> None:
        with pytest.raises(OARepoError):
            raise OARepoError("Base error message")

    def test_configuration_error_can_be_raised(self) -> None:
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("Config is invalid")

    def test_version_mismatch_error_can_be_raised(self) -> None:
        with pytest.raises(VersionMismatchError):
            raise VersionMismatchError("Version mismatch")

    def test_process_execution_error_can_be_raised(self) -> None:
        with pytest.raises(ProcessExecutionError):
            raise ProcessExecutionError(
                "Process failed",
                command=["echo", "test"],
                returncode=1,
                stdout="",
                stderr="error",
            )

    def test_file_not_found_error_can_be_raised(self) -> None:
        with pytest.raises(FileNotFoundError):
            raise FileNotFoundError("File not found")

    def test_validation_error_can_be_raised(self) -> None:
        with pytest.raises(ValidationError):
            raise ValidationError("Validation failed")

    def test_lock_acquisition_error_can_be_raised(self) -> None:
        with pytest.raises(LockAcquisitionError):
            raise LockAcquisitionError("Cannot acquire lock")

    def test_all_exceptions_are_subclasses_of_base(self) -> None:
        assert issubclass(ConfigurationError, OARepoError)
        assert issubclass(VersionMismatchError, OARepoError)
        assert issubclass(ProcessExecutionError, OARepoError)
        assert issubclass(FileNotFoundError, OARepoError)
        assert issubclass(ValidationError, OARepoError)
        assert issubclass(LockAcquisitionError, OARepoError)

    def test_base_exception_catches_all_subclasses(self) -> None:
        with pytest.raises(OARepoError):
            raise ConfigurationError("Should be caught by base")

        with pytest.raises(OARepoError):
            raise ProcessExecutionError(
                "Should be caught",
                command=["test"],
                returncode=1,
            )


class TestExitCodes:
    """Test that exit codes are correctly defined for each exception type."""

    def test_base_exception_exit_code(self) -> None:
        assert OARepoError.exit_code == 1

    def test_configuration_error_exit_code(self) -> None:
        assert ConfigurationError.exit_code == 10

    def test_version_mismatch_error_exit_code(self) -> None:
        assert VersionMismatchError.exit_code == 11

    def test_process_execution_error_exit_code(self) -> None:
        assert ProcessExecutionError.exit_code == 12

    def test_file_not_found_error_exit_code(self) -> None:
        assert FileNotFoundError.exit_code == 13

    def test_validation_error_exit_code(self) -> None:
        assert ValidationError.exit_code == 14

    def test_lock_acquisition_error_exit_code(self) -> None:
        assert LockAcquisitionError.exit_code == 15


class TestProcessExecutionError:
    """Test ProcessExecutionError formatting and attributes."""

    def test_basic_attributes(self) -> None:
        exc = ProcessExecutionError(
            "Process failed",
            command=["echo", "test"],
            returncode=1,
            stdout="output",
            stderr="error",
        )
        assert exc.message == "Process failed"
        assert exc.command == ["echo", "test"]
        assert exc.returncode == 1
        assert exc.stdout == "output"
        assert exc.stderr == "error"

    def test_str_format_with_all_fields(self) -> None:
        exc = ProcessExecutionError(
            "Process failed",
            command=["echo", "test"],
            returncode=1,
            stdout="output",
            stderr="error",
        )
        str_repr = str(exc)
        assert "Process failed" in str_repr
        assert "Command: echo test" in str_repr
        assert "Return code: 1" in str_repr
        assert "Stdout: output" in str_repr
        assert "Stderr: error" in str_repr

    def test_str_format_without_stdout_stderr(self) -> None:
        exc = ProcessExecutionError(
            "Process failed",
            command=["echo", "test"],
            returncode=1,
            stdout=None,
            stderr=None,
        )
        str_repr = str(exc)
        assert "Process failed" in str_repr
        assert "Command: echo test" in str_repr
        assert "Return code: 1" in str_repr
        assert "Stdout:" not in str_repr
        assert "Stderr:" not in str_repr

    def test_command_with_multiple_args(self) -> None:
        exc = ProcessExecutionError(
            "Failed",
            command=["python", "-m", "pytest", "-v"],
            returncode=2,
        )
        assert "Command: python -m pytest -v" in str(exc)


class TestSafeRun:
    """Test the safe_run utility function."""

    def test_safe_run_returns_result_on_success(self) -> None:
        def success_func() -> int:
            return 42

        result = safe_run(success_func)
        assert result == 42

    def test_safe_run_raises_on_oarepo_error_when_check_true(self) -> None:
        def failing_func() -> None:
            raise ConfigurationError("Config error")

        with pytest.raises(ConfigurationError):
            safe_run(failing_func, check=True)

    def test_safe_run_returns_exception_when_check_false(self) -> None:
        def failing_func() -> None:
            raise ConfigurationError("Config error")

        result = safe_run(failing_func, check=False)
        assert isinstance(result, ConfigurationError)
        assert result.message == "Config error"

    def test_safe_run_passes_arguments(self) -> None:
        def add_func(a: int, b: int) -> int:
            return a + b

        result = safe_run(add_func, 10, 20)
        assert result == 30

    def test_safe_run_passes_keyword_arguments(self) -> None:
        def greet_func(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        result = safe_run(greet_func, "World", greeting="Hi")
        assert result == "Hi, World!"

    def test_safe_run_preserves_custom_exit_codes(self) -> None:
        def failing_func() -> None:
            raise ConfigurationError("Custom error")

        with pytest.raises(ConfigurationError) as exc_info:
            safe_run(failing_func, check=True)

        assert exc_info.value.exit_code == 10
