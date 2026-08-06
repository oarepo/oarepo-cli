# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for CLI command wrapper decorators."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
import typer

if TYPE_CHECKING:
    from oarepo_cli.core.context import ProjectContext
    from oarepo_cli.ui import ConsoleOutput

from oarepo_cli.cli.command_wrapper import with_context_and_console, with_context_only
from oarepo_cli.core.errors import OARepoError


def test_with_context_and_console_basic(tmp_path):
    """Test that decorator injects context and console correctly."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'test'\n")

    # Track if function was called with correct arguments
    called_with = {}

    @with_context_and_console()
    def test_command(context: ProjectContext, console: ConsoleOutput, quiet: bool = False):
        called_with["context"] = context
        called_with["console"] = console
        called_with["quiet"] = quiet
        return "success"

    with patch("oarepo_cli.cli.command_wrapper.discover_context") as mock_discover:
        mock_context = Mock()
        mock_discover.return_value = mock_context

        result = test_command(quiet=True)

        assert result == "success"
        assert called_with["context"] is mock_context
        assert called_with["console"] is not None  # Console was injected
        assert called_with["quiet"] is True


def test_with_context_and_console_with_messages(tmp_path):
    """Test that decorator shows start and success messages."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'test'\n")

    @with_context_and_console(
        start_message="Starting test...",
        success_message="Test completed!",
    )
    def test_command(
        context: ProjectContext,
        console: ConsoleOutput,
    ):
        return "done"

    with patch("oarepo_cli.cli.command_wrapper.discover_context") as mock_discover:
        mock_context = Mock()
        mock_discover.return_value = mock_context

        with patch("oarepo_cli.cli.command_wrapper.ConsoleOutputClass") as mock_console_class:
            mock_console = Mock()
            mock_console_class.return_value = mock_console

            result = test_command()

            assert result == "done"
            # Check start message was shown
            mock_console.info.assert_called_once()
            assert "🚀 Starting test..." in str(mock_console.info.call_args)

            # Check success message was shown
            mock_console.success.assert_called_once()
            assert "✨ ✓ Test completed!" in str(mock_console.success.call_args)


def test_with_context_and_console_error_handling():
    """Test that decorator handles OARepoError correctly."""

    @with_context_and_console(error_prefix="Test error")
    def test_command(
        context: ProjectContext,
        console: ConsoleOutput,
    ):
        raise OARepoError("Something went wrong")

    with patch("oarepo_cli.cli.command_wrapper.discover_context") as mock_discover:
        mock_context = Mock()
        mock_discover.return_value = mock_context

        with patch("oarepo_cli.cli.command_wrapper.ConsoleOutputClass") as mock_console_class:
            mock_console = Mock()
            mock_console_class.return_value = mock_console

            with pytest.raises(typer.Exit) as exc_info:
                test_command()

            assert exc_info.value.exit_code == 1

            # Check error message was shown
            mock_console.error.assert_called_once()
            assert "❌ Test error:" in str(mock_console.error.call_args)
            assert "Something went wrong" in str(mock_console.error.call_args)


def test_with_context_and_console_no_messages():
    """Test decorator works without start/success messages."""

    @with_context_and_console()
    def test_command(
        context: ProjectContext,
        console: ConsoleOutput,
    ):
        return "result"

    with patch("oarepo_cli.cli.command_wrapper.discover_context") as mock_discover:
        mock_context = Mock()
        mock_discover.return_value = mock_context

        with patch("oarepo_cli.cli.command_wrapper.ConsoleOutputClass") as mock_console_class:
            mock_console = Mock()
            mock_console_class.return_value = mock_console

            result = test_command()

            assert result == "result"
            # No start or success messages should be shown
            mock_console.info.assert_not_called()
            mock_console.success.assert_not_called()


def test_with_context_only():
    """Test that with_context_only decorator only injects context."""
    called_with = {}

    @with_context_only
    def test_command(context: ProjectContext, some_arg: str):
        called_with["context"] = context
        called_with["some_arg"] = some_arg
        return "done"

    with patch("oarepo_cli.cli.command_wrapper.discover_context") as mock_discover:
        mock_context = Mock()
        mock_discover.return_value = mock_context

        result = test_command(some_arg="test")

        assert result == "done"
        assert called_with["context"] is mock_context
        assert called_with["some_arg"] == "test"


def test_with_context_only_preserves_errors():
    """Test that with_context_only doesn't catch exceptions."""

    @with_context_only
    def test_command(context: ProjectContext):
        raise ValueError("Some error")

    with patch("oarepo_cli.cli.command_wrapper.discover_context") as mock_discover:
        mock_context = Mock()
        mock_discover.return_value = mock_context

        # Error should propagate unchanged
        with pytest.raises(ValueError, match="Some error"):
            test_command()


def test_with_context_and_console_preserves_function_metadata():
    """Test that decorator preserves function name and docstring."""

    @with_context_and_console()
    def my_command(context: ProjectContext, console: ConsoleOutput):
        """This is my command."""

    assert my_command.__name__ == "my_command"
    assert my_command.__doc__ == "This is my command."


def test_with_context_only_preserves_function_metadata():
    """Test that with_context_only preserves function metadata."""

    @with_context_only
    def another_command(context: ProjectContext):
        """Another command."""

    assert another_command.__name__ == "another_command"
    assert another_command.__doc__ == "Another command."
