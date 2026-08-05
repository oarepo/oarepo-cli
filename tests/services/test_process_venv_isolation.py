# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for virtual environment isolation in process module."""

from __future__ import annotations

import os
import sys

import pytest

from oarepo_cli.services import process


def test_strip_venv_vars_removes_virtual_env() -> None:
    """Test that VIRTUAL_ENV variable is stripped."""
    env = {"VIRTUAL_ENV": "/path/to/venv", "OTHER": "value"}
    cleaned = process._strip_venv_vars(env)

    assert "VIRTUAL_ENV" not in cleaned
    assert "OTHER" in cleaned
    assert cleaned["OTHER"] == "value"


def test_strip_venv_vars_removes_all_venv_variables() -> None:
    """Test that all venv-related variables are stripped."""
    env = {
        "VIRTUAL_ENV": "/path/to/venv",
        "VIRTUAL_ENV_PROMPT": "(venv) ",
        "_OLD_VIRTUAL_PATH": "/usr/bin",
        "_OLD_VIRTUAL_PYTHONHOME": "/usr",
        "OTHER": "value",
    }
    cleaned = process._strip_venv_vars(env)

    assert "VIRTUAL_ENV" not in cleaned
    assert "VIRTUAL_ENV_PROMPT" not in cleaned
    assert "_OLD_VIRTUAL_PATH" not in cleaned
    assert "_OLD_VIRTUAL_PYTHONHOME" not in cleaned
    assert "OTHER" in cleaned


def test_strip_venv_vars_removes_venv_bin_from_path_unix() -> None:
    """Test that venv bin directory is removed from PATH on Unix."""
    if sys.platform == "win32":
        pytest.skip("Unix-specific test")

    venv_path = "/home/user/.venv"
    env = {
        "VIRTUAL_ENV": venv_path,
        "PATH": f"{venv_path}/bin:/usr/bin:/usr/local/bin",
    }
    cleaned = process._strip_venv_vars(env)

    assert "VIRTUAL_ENV" not in cleaned
    assert cleaned["PATH"] == "/usr/bin:/usr/local/bin"


def test_strip_venv_vars_removes_venv_bin_from_path_with_trailing_slash() -> None:
    """Test that venv bin directory with trailing slash is removed from PATH."""
    if sys.platform == "win32":
        pytest.skip("Unix-specific test")

    venv_path = "/home/user/.venv"
    env = {
        "VIRTUAL_ENV": venv_path,
        "PATH": f"{venv_path}/bin/:/usr/bin:/usr/local/bin",
    }
    cleaned = process._strip_venv_vars(env)

    assert cleaned["PATH"] == "/usr/bin:/usr/local/bin"


def test_strip_venv_vars_handles_multiple_venv_bin_in_path() -> None:
    """Test that multiple occurrences of venv bin are removed."""
    if sys.platform == "win32":
        pytest.skip("Unix-specific test")

    venv_path = "/home/user/.venv"
    env = {
        "VIRTUAL_ENV": venv_path,
        "PATH": f"{venv_path}/bin:/usr/bin:{venv_path}/bin:/usr/local/bin",
    }
    cleaned = process._strip_venv_vars(env)

    assert cleaned["PATH"] == "/usr/bin:/usr/local/bin"


def test_strip_venv_vars_preserves_path_without_venv() -> None:
    """Test that PATH is preserved when venv bin is not present."""
    env = {
        "VIRTUAL_ENV": "/home/user/.venv",
        "PATH": "/usr/bin:/usr/local/bin",
    }
    cleaned = process._strip_venv_vars(env)

    assert cleaned["PATH"] == "/usr/bin:/usr/local/bin"


def test_strip_venv_vars_no_virtual_env_set() -> None:
    """Test that PATH is unchanged when VIRTUAL_ENV is not set."""
    env = {"PATH": "/usr/bin:/usr/local/bin"}
    cleaned = process._strip_venv_vars(env)

    assert cleaned["PATH"] == "/usr/bin:/usr/local/bin"


def test_build_subprocess_env_strips_venv_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that build_subprocess_env() strips venv variables by default."""
    monkeypatch.setenv("VIRTUAL_ENV", "/path/to/venv")
    monkeypatch.setenv("OTHER", "value")

    result = process.build_subprocess_env()

    assert "VIRTUAL_ENV" not in result
    assert "OTHER" in result


def test_build_subprocess_env_includes_oarepo_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that build_subprocess_env() includes OARepo defaults by default."""
    # Clear any existing UV_EXTRA_INDEX_URL to test the default
    monkeypatch.delenv("UV_EXTRA_INDEX_URL", raising=False)

    result = process.build_subprocess_env()

    assert "UV_EXTRA_INDEX_URL" in result
    assert "gitlab.cesnet.cz" in result["UV_EXTRA_INDEX_URL"]
    assert "INVENIO_APP_THEME" in result


def test_build_subprocess_env_preserves_existing_oarepo_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that existing OARepo env vars are not overwritten."""
    custom_index = "https://custom.pypi.org/simple"
    monkeypatch.setenv("UV_EXTRA_INDEX_URL", custom_index)

    result = process.build_subprocess_env()

    # Should preserve the existing value, not overwrite with default
    assert result["UV_EXTRA_INDEX_URL"] == custom_index


def test_build_subprocess_env_can_skip_oarepo_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that OARepo defaults can be skipped."""
    monkeypatch.delenv("UV_EXTRA_INDEX_URL", raising=False)

    result = process.build_subprocess_env(include_oarepo_defaults=False)

    assert "UV_EXTRA_INDEX_URL" not in result


def test_build_subprocess_env_can_preserve_venv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that build_subprocess_env() can preserve venv variables when requested."""
    monkeypatch.setenv("VIRTUAL_ENV", "/path/to/venv")
    monkeypatch.setenv("OTHER", "value")

    result = process.build_subprocess_env(strip_venv=False, include_oarepo_defaults=False)

    # No stripping, no defaults, no custom env -> a plain copy of the parent environment
    assert result == dict(os.environ)
    assert result["VIRTUAL_ENV"] == "/path/to/venv"


def test_build_subprocess_env_custom_vars_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that custom environment variables override parent vars."""
    monkeypatch.setenv("VAR", "parent")

    result = process.build_subprocess_env({"VAR": "custom"})

    assert result["VAR"] == "custom"


def test_run_strips_venv_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that run() strips venv variables by default."""
    monkeypatch.setenv("VIRTUAL_ENV", "/path/to/venv")

    # Run a simple command that echoes an env var
    result = process.run(
        ["python3", "-c", "import os; print(os.environ.get('VIRTUAL_ENV', 'NOT_SET'))"],
        check=True,
    )

    assert result.stdout.strip() == "NOT_SET"


def test_run_can_preserve_venv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that run() can preserve venv when strip_venv=False."""
    venv_path = "/path/to/venv"
    monkeypatch.setenv("VIRTUAL_ENV", venv_path)

    result = process.run(
        ["python3", "-c", "import os; print(os.environ.get('VIRTUAL_ENV', 'NOT_SET'))"],
        check=True,
        strip_venv=False,
        env={},  # Need to pass env dict to get environment
    )

    assert result.stdout.strip() == venv_path


def test_stream_strips_venv_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that stream() strips venv variables by default."""
    monkeypatch.setenv("VIRTUAL_ENV", "/path/to/venv")

    lines = list(
        process.stream(
            ["python3", "-c", "import os; print(os.environ.get('VIRTUAL_ENV', 'NOT_SET'))"]
        )
    )

    assert len(lines) == 1
    assert lines[0] == "NOT_SET"


def test_get_output_strips_venv_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that get_output() strips venv variables by default."""
    monkeypatch.setenv("VIRTUAL_ENV", "/path/to/venv")

    output = process.get_output(
        ["python3", "-c", "import os; print(os.environ.get('VIRTUAL_ENV', 'NOT_SET'))"]
    )

    assert output == "NOT_SET"


def test_get_system_path_strips_active_venv_bin(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_system_path() must exclude an active venv's bin dir, mirroring
    repository_runner.sh's get_highest_available_python -- otherwise
    resolving a system Python while a project's own venv is activated
    finds that venv's own interpreter, which is wrong for anything that
    needs to (re)create that very venv (e.g. `repository upgrade`)."""
    if sys.platform == "win32":
        pytest.skip("Unix-specific test")

    venv_path = "/home/user/project/.venv"
    monkeypatch.setenv("VIRTUAL_ENV", venv_path)
    monkeypatch.setenv("PATH", f"{venv_path}/bin:/usr/bin:/usr/local/bin")

    assert process.get_system_path() == "/usr/bin:/usr/local/bin"


def test_get_system_path_unchanged_without_active_venv(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_system_path() returns PATH unchanged when no venv is active."""
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/usr/local/bin")

    assert process.get_system_path() == "/usr/bin:/usr/local/bin"
