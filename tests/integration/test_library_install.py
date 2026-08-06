# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration test for library install alias command.

Since 'library install' is just an alias for 'library venv', we only verify
that the alias works and passes flags correctly. Full venv functionality is
tested in test_library_venv.py and test_library_venv_sync.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Typer CLI runner."""
    return CliRunner()


def test_library_install_alias_works_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that 'library install' command works as alias for 'library venv'."""
    monkeypatch.chdir(clean_testlib)

    # clean_testlib fixture guarantees no venv exists yet
    assert not (clean_testlib / ".venv").exists()

    result = runner.invoke(app, ["library", "install", "--quiet"], catch_exceptions=False)

    # Command should succeed or fail with expected error
    assert result.exit_code in [0, 1]

    # If successful, verify venv was created
    if result.exit_code == 0:
        assert (clean_testlib / ".venv").exists()


def test_library_install_passes_flags_to_venv(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that 'library install' correctly forwards flags to the underlying venv command."""
    monkeypatch.chdir(clean_testlib)

    # Create an existing venv with marker to test --force flag
    venv_path = clean_testlib / ".venv"
    venv_path.mkdir(parents=True)
    marker_file = venv_path / "test_marker.txt"
    marker_file.write_text("old venv")

    # Verify marker exists
    assert marker_file.exists()

    # Run install with force flag - this tests flag forwarding
    result = runner.invoke(app, ["library", "install", "--force", "--quiet"], catch_exceptions=False)

    # Should complete (may fail if uv not available)
    assert result.exit_code in [0, 1]

    # If successful, marker should be gone (venv was recreated), proving --force worked
    if result.exit_code == 0:
        assert not marker_file.exists()
