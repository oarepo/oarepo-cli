# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Unit tests for invenio_cli service module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services import invenio_cli


@pytest.fixture
def mock_context() -> Mock:
    """Create a mock ProjectContext."""
    context = Mock(spec=ProjectContext)
    context.root_directory = Path("/fake/project")
    context.python_binary = Path("/usr/bin/python3.14")
    return context


def test_run_invenio_cli_constructs_correct_command(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that run_invenio_cli constructs the uvx command correctly."""
    mock_run = Mock()
    monkeypatch.setattr("oarepo_cli.services.invenio_cli.process.run", mock_run)

    invenio_cli.run_invenio_cli(mock_context, ["services", "setup"])

    # Verify command structure
    call_args = mock_run.call_args
    assert call_args is not None
    command = call_args[0][0]
    assert command[0] == "uvx"
    assert f"--python={mock_context.python_binary}" in command
    assert "--with" in command
    assert "git+https://github.com/oarepo/oarepo-cli@rdm-14" in command
    assert "--from" in command
    assert "git+https://github.com/oarepo/invenio-cli@oarepo-feature-docker-environment" in command
    assert "invenio-cli" in command
    assert "services" in command
    assert "setup" in command


def test_run_invenio_cli_passes_options_correctly(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that run_invenio_cli passes quiet, check, and env options correctly."""
    mock_run = Mock()
    monkeypatch.setattr("oarepo_cli.services.invenio_cli.process.run", mock_run)

    custom_env = {"FOO": "bar"}
    invenio_cli.run_invenio_cli(
        mock_context,
        ["install"],
        quiet=True,
        check=False,
        env=custom_env,
    )

    call_args = mock_run.call_args
    assert call_args is not None
    kwargs = call_args[1]
    assert kwargs["interactive"] is False  # quiet=True -> interactive=False
    assert kwargs["check"] is False
    assert kwargs["env"] == custom_env


def test_run_invenio_shell_constructs_correct_command(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that run_invenio_shell constructs the correct uv run command."""
    mock_run = Mock()
    monkeypatch.setattr("oarepo_cli.services.invenio_cli.process.run", mock_run)

    python_code = "print(app.instance_path)"
    invenio_cli.run_invenio_shell(mock_context, python_code)

    call_args = mock_run.call_args
    assert call_args is not None
    command = call_args[0][0]
    assert command == [
        "uv",
        "run",
        "invenio",
        "shell",
        "--no-term-title",
        "-c",
        python_code,
    ]

    # Verify PYTHON_BASIC_REPL=0 is set
    kwargs = call_args[1]
    assert kwargs["env"]["PYTHON_BASIC_REPL"] == "0"


def test_run_invenio_shell_passes_options_correctly(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that run_invenio_shell passes quiet and check options correctly."""
    mock_run = Mock()
    monkeypatch.setattr("oarepo_cli.services.invenio_cli.process.run", mock_run)

    invenio_cli.run_invenio_shell(
        mock_context,
        "print('test')",
        quiet=True,
        check=False,
    )

    call_args = mock_run.call_args
    assert call_args is not None
    kwargs = call_args[1]
    assert kwargs["interactive"] is False  # quiet=True -> interactive=False
    assert kwargs["check"] is False
