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
    """run_invenio_cli runs the invenio-cli binary installed alongside oarepo-cli's own
    venv directly (not via uvx from a hardcoded git ref) with the given args appended."""
    mock_run = Mock()
    monkeypatch.setattr("oarepo_cli.services.invenio_cli.process.run", mock_run)
    monkeypatch.setattr(
        "oarepo_cli.services.invenio_cli._invenio_cli_path", lambda: "/venv/bin/invenio-cli"
    )

    invenio_cli.run_invenio_cli(mock_context, ["services", "setup"])

    call_args = mock_run.call_args
    assert call_args is not None
    command = call_args[0][0]
    assert command == ["/venv/bin/invenio-cli", "services", "setup"]


def test_invenio_cli_path_prefers_binary_next_to_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_invenio_cli_path() resolves the binary installed alongside oarepo-cli's own venv,
    mirroring services.lint._tool_path's rationale for ruff/ty."""
    fake_binary = tmp_path / "invenio-cli"
    fake_binary.touch()
    monkeypatch.setattr("oarepo_cli.services.invenio_cli.sys.executable", str(tmp_path / "python"))

    assert invenio_cli._invenio_cli_path() == str(fake_binary)


def test_invenio_cli_path_falls_back_to_bare_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a sibling binary (e.g. a dev checkout run outside its own venv), falls back
    to the bare name, resolved via PATH by the subprocess call."""
    monkeypatch.setattr("oarepo_cli.services.invenio_cli.sys.executable", str(tmp_path / "python"))

    assert invenio_cli._invenio_cli_path() == "invenio-cli"


def test_run_invenio_cli_passes_options_correctly(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that run_invenio_cli passes quiet, check, and env options correctly."""
    mock_run = Mock()
    monkeypatch.setattr("oarepo_cli.services.invenio_cli.process.run", mock_run)
    monkeypatch.delenv("UV_PRERELEASE", raising=False)

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
    # Custom env is merged on top of the UV_PRERELEASE default, not replacing it
    assert kwargs["env"] == {"UV_PRERELEASE": "allow", "FOO": "bar"}


def test_run_invenio_cli_defaults_uv_prerelease_to_allow(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_invenio_cli must allow pre-release versions by default.

    Mirrors repository_runner.sh's `export UV_PRERELEASE=${UV_PRERELEASE:-"allow"}`,
    so uv resolves the same way whether invoked directly or via invenio-cli.
    """
    mock_run = Mock()
    monkeypatch.setattr("oarepo_cli.services.invenio_cli.process.run", mock_run)
    monkeypatch.delenv("UV_PRERELEASE", raising=False)

    invenio_cli.run_invenio_cli(mock_context, ["install"])

    kwargs = mock_run.call_args[1]
    assert kwargs["env"] == {"UV_PRERELEASE": "allow"}


def test_run_invenio_cli_respects_existing_uv_prerelease_env(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An already-exported UV_PRERELEASE should be honored, not overridden."""
    mock_run = Mock()
    monkeypatch.setattr("oarepo_cli.services.invenio_cli.process.run", mock_run)
    monkeypatch.setenv("UV_PRERELEASE", "if-necessary-or-explicit")

    invenio_cli.run_invenio_cli(mock_context, ["install"])

    kwargs = mock_run.call_args[1]
    assert kwargs["env"] == {"UV_PRERELEASE": "if-necessary-or-explicit"}
