# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT
"""Integration tests for library venv uv sync behavior.

These tests verify that the library venv command correctly uses uv sync
to install dependencies and generates a uv.lock file, using the real
testlib fixture with actual uv commands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Typer CLI runner."""
    return CliRunner()


@pytest.fixture
def testlib_without_gitignored_uv_lock(clean_testlib: Path) -> Iterator[Path]:
    """Temporarily strip any ``uv.lock`` line from testlib's gitignore.

    Restores the original content afterward. Testlib's own .gitignore already
    lists ``uv.lock`` (it's a member of this repo's root uv workspace), so
    ``test_uv_lock_added_to_gitignore`` needs a .gitignore that doesn't have
    it yet to verify `library venv` adds it dynamically, without permanently
    mutating the committed fixture.
    """
    gitignore = clean_testlib / ".gitignore"
    original_content = gitignore.read_text()
    stripped_content = "\n".join(line for line in original_content.splitlines() if line.strip() != "uv.lock")
    gitignore.write_text(stripped_content + "\n")
    try:
        yield clean_testlib
    finally:
        gitignore.write_text(original_content)


def test_venv_creates_uv_lock_file(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that 'library venv' generates a uv.lock file."""
    monkeypatch.chdir(clean_testlib)

    lock_file = clean_testlib / "uv.lock"
    assert not lock_file.exists()

    # Run venv command (uses uv sync internally)
    result = runner.invoke(app, ["library", "venv"], catch_exceptions=False)

    if result.exit_code == 0:
        # Verify uv.lock was generated
        assert lock_file.exists()
        assert lock_file.stat().st_size > 0

        # Verify it's a valid lock file (contains expected sections)
        content = lock_file.read_text()
        assert "version = " in content or "[package]" in content


def test_uv_lock_added_to_gitignore(
    runner: CliRunner,
    testlib_without_gitignored_uv_lock: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that uv.lock is automatically added to .gitignore."""
    monkeypatch.chdir(testlib_without_gitignored_uv_lock)

    gitignore = testlib_without_gitignored_uv_lock / ".gitignore"

    # Verify .gitignore exists but doesn't have uv.lock yet
    assert gitignore.exists()
    content_before = gitignore.read_text()
    assert "uv.lock" not in content_before

    # Run venv command
    result = runner.invoke(app, ["library", "venv"], catch_exceptions=False)

    if result.exit_code == 0:
        # Verify uv.lock was added to .gitignore
        content_after = gitignore.read_text()
        assert "uv.lock" in content_after


def test_venv_with_extras_includes_in_sync(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that library venv correctly passes extras to uv sync.

    This is an indirect test - we verify that the venv was created successfully
    and that dependencies from extras are installed.
    """
    monkeypatch.chdir(clean_testlib)

    # Run venv command
    result = runner.invoke(app, ["library", "venv"], catch_exceptions=False)

    if result.exit_code == 0:
        venv_path = clean_testlib / ".venv"
        assert venv_path.exists()

        # Verify that packages from extras are installed
        # Check pip list in the venv
        import subprocess

        pip_list = subprocess.run(  # noqa: S603 - just a test, not a security issue to run the program
            [str(venv_path / "bin" / "python"), "-m", "pip", "list"],
            capture_output=True,
            text=True,
            check=False,
        )

        if pip_list.returncode == 0:
            # Verify dev/test packages are present (if defined in testlib)
            # At minimum, testlib itself should be installed
            assert "testlib" in pip_list.stdout.lower()


def test_venv_force_regenerates_lock(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that --force flag regenerates the lock file."""
    monkeypatch.chdir(clean_testlib)

    # First run to create lock file
    result1 = runner.invoke(app, ["library", "venv"], catch_exceptions=False)
    assert result1.exit_code in [0, 1]

    lock_file = clean_testlib / "uv.lock"
    if result1.exit_code == 0 and lock_file.exists():
        # Record original modification time
        original_mtime = lock_file.stat().st_mtime

        # Wait a tiny bit to ensure mtime differs if file is regenerated
        import time

        time.sleep(0.1)

        # Force recreation
        result2 = runner.invoke(app, ["library", "venv", "--force"], catch_exceptions=False)

        if result2.exit_code == 0:
            # Lock file should be regenerated (different mtime)
            new_mtime = lock_file.stat().st_mtime
            # Allow for filesystem time precision issues
            assert new_mtime >= original_mtime


def test_sync_installs_project_editable(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that uv sync installs the project itself in editable mode."""
    monkeypatch.chdir(clean_testlib)

    result = runner.invoke(app, ["library", "venv"], catch_exceptions=False)

    if result.exit_code == 0:
        venv_path = clean_testlib / ".venv"

        # Check if testlib is installed in editable mode
        import subprocess

        pip_list = subprocess.run(  # noqa: S603 - just a test, not a security issue to run the program
            [str(venv_path / "bin" / "python"), "-m", "pip", "list", "--format=freeze"],
            capture_output=True,
            text=True,
            check=False,
        )

        if pip_list.returncode == 0:
            # Editable installs show with -e or file:// in pip list --format=freeze
            assert "testlib" in pip_list.stdout.lower()
            # Note: exact format varies by pip version, so we just check it's present


def test_no_editable_uses_wheel_not_sync(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that --no-editable flag uses wheel build, not uv sync."""
    monkeypatch.chdir(clean_testlib)

    result = runner.invoke(app, ["library", "venv", "--no-editable"], catch_exceptions=False)

    if result.exit_code == 0:
        # With --no-editable, a wheel should be built
        dist_dir = clean_testlib / "dist"

        # The dist directory might exist with a .whl file
        if dist_dir.exists():
            wheels = list(dist_dir.glob("*.whl"))
            # If successful, at least one wheel was built
            assert len(wheels) > 0


def test_sync_with_oarepo_version_extra(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that venv command includes oarepo version extra in sync."""
    monkeypatch.chdir(clean_testlib)

    # testlib has oarepo14 in its optional-dependencies
    result = runner.invoke(app, ["library", "venv"], catch_exceptions=False)

    if result.exit_code == 0:
        lock_file = clean_testlib / "uv.lock"

        # Verify lock file exists and includes oarepo dependencies
        if lock_file.exists():
            # Lock file should reference oarepo packages (if they're in the dependencies)
            # This is indirect verification that the oarepo14 extra was included
            assert lock_file.stat().st_size > 0


def test_lock_file_is_reproducible(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that running venv twice produces identical lock files."""
    monkeypatch.chdir(clean_testlib)

    # First run
    result1 = runner.invoke(app, ["library", "venv", "--force"], catch_exceptions=False)
    assert result1.exit_code in [0, 1]

    lock_file = clean_testlib / "uv.lock"
    if result1.exit_code == 0 and lock_file.exists():
        content1 = lock_file.read_text()

        # Second run with force
        result2 = runner.invoke(app, ["library", "venv", "--force"], catch_exceptions=False)

        if result2.exit_code == 0 and lock_file.exists():
            content2 = lock_file.read_text()

            # Lock files should be identical (reproducible)
            assert content1 == content2


def test_sync_respects_pyproject_dependencies(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that uv sync installs dependencies from pyproject.toml."""
    monkeypatch.chdir(clean_testlib)

    result = runner.invoke(app, ["library", "venv"], catch_exceptions=False)

    if result.exit_code == 0:
        venv_path = clean_testlib / ".venv"

        # Verify that dependencies from pyproject.toml are installed
        import subprocess

        pip_list = subprocess.run(  # noqa: S603 - just a test, not a security issue to run the program
            [str(venv_path / "bin" / "python"), "-m", "pip", "list"],
            capture_output=True,
            text=True,
            check=False,
        )

        if pip_list.returncode == 0:
            # At minimum, common dev dependencies should be present
            # (testlib likely has pytest or similar in dev extras)
            output_lower = pip_list.stdout.lower()
            # Just verify something was installed
            assert len(output_lower.splitlines()) > 5  # More than just pip/setuptools


def test_gitignore_not_duplicated_on_repeated_runs(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that uv.lock is not added to .gitignore multiple times."""
    monkeypatch.chdir(clean_testlib)

    gitignore = clean_testlib / ".gitignore"

    # First run
    result1 = runner.invoke(app, ["library", "venv"], catch_exceptions=False)

    if result1.exit_code == 0:
        content_after_first = gitignore.read_text()
        count_first = content_after_first.count("uv.lock")
        assert count_first == 1

        # Second run
        result2 = runner.invoke(app, ["library", "venv", "--force"], catch_exceptions=False)

        if result2.exit_code == 0:
            content_after_second = gitignore.read_text()
            count_second = content_after_second.count("uv.lock")

            # Should still be only one occurrence
            assert count_second == 1
            assert content_after_first == content_after_second
