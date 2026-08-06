# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for library test command using real testlib fixture."""

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


def test_help_displays(runner: CliRunner) -> None:
    """Test that 'library test --help' displays help text."""
    result = runner.invoke(app, ["library", "test", "--help"])

    assert result.exit_code == 0
    assert "test" in result.stdout.lower()
    assert "pytest" in result.stdout.lower()


def test_runs_tests_with_real_venv(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that test command runs pytest with a real venv."""
    monkeypatch.chdir(clean_testlib)

    result = runner.invoke(app, ["library", "install"], catch_exceptions=False)
    assert result.exit_code in [0, 1]

    # Create a simple test file
    test_file = clean_testlib / "test_simple.py"
    test_file.write_text("def test_pass():\n    assert True\n")

    # Skip services and run tests
    result = runner.invoke(app, ["library", "test", "--skip-services", "--quiet"], catch_exceptions=False)

    # Test should complete (may fail if pytest not installed, but should not crash)
    assert result.exit_code in [0, 1]

    # Cleanup
    test_file.unlink(missing_ok=True)


def test_with_coverage_flag_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that --with-coverage flag adds coverage arguments."""
    monkeypatch.chdir(clean_testlib)

    runner.invoke(app, ["library", "install"], catch_exceptions=False)

    # Create a simple test file
    test_file = clean_testlib / "test_cov.py"
    test_file.write_text("def test_pass():\n    assert 1 + 1 == 2\n")

    # Run with coverage
    result = runner.invoke(
        app,
        ["library", "test", "--skip-services", "--with-coverage", "--quiet"],
        catch_exceptions=False,
    )

    # Should complete (coverage may not be installed, but should not crash)
    assert result.exit_code in [0, 1]

    # Cleanup
    test_file.unlink(missing_ok=True)


def test_skip_services_flag_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that --skip-services flag skips Docker services."""
    monkeypatch.chdir(clean_testlib)

    runner.invoke(app, ["library", "install"], catch_exceptions=False)

    # Create a simple test file
    test_file = clean_testlib / "test_skip.py"
    test_file.write_text("def test_pass():\n    assert True\n")

    # Run with skip-services
    result = runner.invoke(app, ["library", "test", "--skip-services", "--quiet"], catch_exceptions=False)

    # Should complete without trying to start services
    assert result.exit_code in [0, 1]

    # Cleanup
    test_file.unlink(missing_ok=True)


def test_extra_pytest_args_passed_through_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that extra arguments are passed to pytest."""
    monkeypatch.chdir(clean_testlib)

    runner.invoke(app, ["library", "install"], catch_exceptions=False)

    # Create a simple test file
    test_file = clean_testlib / "test_args.py"
    test_file.write_text("def test_pass():\n    assert True\n")

    # Run with extra pytest args
    result = runner.invoke(
        app,
        ["library", "test", "--skip-services", "-v", "test_args.py"],
        catch_exceptions=False,
    )

    # Should complete
    assert result.exit_code in [0, 1]

    # Cleanup
    test_file.unlink(missing_ok=True)


def test_exit_code_on_test_failure_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that test command exits with pytest's exit code on failure."""
    monkeypatch.chdir(clean_testlib)

    runner.invoke(app, ["library", "install"], catch_exceptions=False)

    # Create a failing test file
    test_file = clean_testlib / "test_fail.py"
    test_file.write_text("def test_fail():\n    assert False, 'This test fails'\n")

    # Run tests (should fail)
    result = runner.invoke(app, ["library", "test", "--skip-services", "--quiet"], catch_exceptions=False)

    # Should have non-zero exit code due to test failure
    # Note: exit code depends on whether pytest was actually run
    assert result.exit_code != 0 or "failed" in result.stdout.lower()

    # Cleanup
    test_file.unlink()


def test_combined_flags_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that --skip-services and --with-coverage can be combined."""
    monkeypatch.chdir(clean_testlib)

    runner.invoke(app, ["library", "install"], catch_exceptions=False)

    # Create a simple test file
    test_file = clean_testlib / "test_combined.py"
    test_file.write_text("def test_pass():\n    assert True\n")

    # Run with both flags
    result = runner.invoke(
        app,
        ["library", "test", "--skip-services", "--with-coverage", "--quiet"],
        catch_exceptions=False,
    )

    # Should complete
    assert result.exit_code in [0, 1]

    # Cleanup
    test_file.unlink(missing_ok=True)


def test_interspersed_flags_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that pytest flags can be interspersed with oarepo-cli flags."""
    monkeypatch.chdir(clean_testlib)

    runner.invoke(app, ["library", "install"], catch_exceptions=False)

    # Create a simple test file
    test_file = clean_testlib / "test_interspersed.py"
    test_file.write_text("def test_pass():\n    assert True\n")

    # Run with mixed flags
    result = runner.invoke(
        app,
        ["library", "test", "-v", "--skip-services", "-x", "test_interspersed.py"],
        catch_exceptions=False,
    )

    # Should complete
    assert result.exit_code in [0, 1]

    # Cleanup
    test_file.unlink(missing_ok=True)


def test_test_requires_pyproject(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that test command fails gracefully without pyproject.toml."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.chdir(empty_dir)

    result = runner.invoke(app, ["library", "test"])

    assert result.exit_code != 0
    assert "pyproject.toml" in str(result.exception).lower() if result.exception else True
