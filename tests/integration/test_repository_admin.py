# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for repository admin/maintenance commands.

This file tests repository commands for translations, indexing, reset, and info:
- `repository translations` - delegates to make-translations or invenio-cli translations compile
- `repository index rebuild` - delegates to services.repository.rebuild_index
- `repository reset` - confirms with "yes" before calling reset_repository
- `repository info` - prints Python version and discovered models

Delegation, argument wiring, and error/exit-code handling are covered here
by mocking `discover_context()` and the specific service function/module
each subcommand delegates to.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app
from oarepo_cli.core.errors import ConfigurationError, ProcessExecutionError
from oarepo_cli.services import process
from oarepo_cli.services.repository import ModelInfo


@pytest.fixture
def mock_context(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Mock discover_context() so no real project is needed."""
    context = Mock()
    monkeypatch.setattr("oarepo_cli.cli.repository.discover_context", lambda: context)
    return context


def _fake_process_result(**overrides: object) -> process.ProcessResult:
    defaults: dict[str, object] = {
        "return_code": 0,
        "stdout": "",
        "stderr": "",
        "command": [],
        "cwd": Path(),
        "duration_ms": 0,
    }
    defaults.update(overrides)
    return process.ProcessResult(**defaults)  # type: ignore[arg-type]


# --- repository translations -------------------------------------------


def test_translations_no_args_runs_make_translations(mock_context: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    """`repository translations` (no args) runs make-translations with no extra args."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.translations.run_translations",
        lambda context, **kwargs: calls.append({"context": context, **kwargs}) or _fake_process_result(),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "translations"])

    assert result.exit_code == 0, result.output
    assert calls == [{"context": mock_context, "extra_args": [], "quiet": False}]


def test_translations_compile_delegates_to_invenio_cli(mock_context: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Repository translations compile delegates to invenio-cli translations compile.

    Not make-translations.
    """
    make_translations_calls: list[object] = []
    invenio_cli_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.translations.run_translations",
        lambda *_args, **_kwargs: make_translations_calls.append(True) or _fake_process_result(),
    )
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.invenio_cli.run_invenio_cli",
        lambda context, args, **kwargs: invenio_cli_calls.append({"context": context, "args": list(args), **kwargs}),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "translations", "compile"])

    assert result.exit_code == 0, result.output
    assert make_translations_calls == []
    assert invenio_cli_calls == [{"context": mock_context, "args": ["translations", "compile"], "quiet": False}]


def test_translations_other_args_forwarded_to_make_translations(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Any first arg other than exactly "compile" is forwarded to make-translations.

    Mirrors repository_runner.sh's translations()'s exact-match check.
    """
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.translations.run_translations",
        lambda context, **kwargs: calls.append({"context": context, **kwargs}) or _fake_process_result(),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "translations", "--verbose"])

    assert result.exit_code == 0, result.output
    assert calls == [{"context": mock_context, "extra_args": ["--verbose"], "quiet": False}]


def test_translations_reports_failure_and_exits_1(
    mock_context: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing make-translations run is reported cleanly.

    Exit code 1.
    """
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.translations.run_translations",
        lambda *_args, **_kwargs: _fake_process_result(return_code=1),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "translations"])

    assert result.exit_code == 1
    assert "Translations failed" in result.output


def test_translations_reports_context_discovery_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A context-discovery failure is reported cleanly.

    Exit code 1.
    """
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.discover_context",
        Mock(side_effect=ConfigurationError("pyproject.toml not found")),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "translations"])

    assert result.exit_code == 1


# --- repository index rebuild -------------------------------------------


def test_index_rebuild_delegates_to_service(mock_context: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    """`repository index rebuild` delegates to services.repository.rebuild_index."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.repository.rebuild_index",
        lambda context, **kwargs: calls.append({"context": context, **kwargs}),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "index", "rebuild", "--quiet"])

    assert result.exit_code == 0, result.output
    assert calls == [{"context": mock_context, "quiet": True}]


def test_index_rebuild_reports_error_and_exits_1(
    mock_context: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ProcessExecutionError from rebuild_index is reported cleanly, exit code 1."""
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.repository.rebuild_index",
        Mock(
            side_effect=ProcessExecutionError(
                message="invenio index destroy failed",
                command=["invenio", "index", "destroy"],
                returncode=1,
                stdout=None,
                stderr=None,
            )
        ),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "index", "rebuild"])

    assert result.exit_code == 1
    assert "Index rebuild failed" in result.output


def test_index_rebuild_does_not_swallow_non_oareporerror_exceptions(
    mock_context: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-OARepoError raised by rebuild_index propagates instead of being turned into a clean exit 1.

    Repository.py's command handler only catches `except OARepoError`
    (ProcessExecutionError already subclasses it, so a separate except clause
    for it would be redundant), not a blanket `except Exception`, so unexpected
    bugs surface as real tracebacks.
    """
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.repository.rebuild_index",
        Mock(side_effect=ValueError("boom")),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "index", "rebuild"])

    assert isinstance(result.exception, ValueError)
    assert "Index rebuild failed" not in result.output


# --- repository reset ----------------------------------------------------


def test_reset_cancelled_without_exact_yes(
    mock_context: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anything other than exactly "yes" cancels the reset without error.

    Exit code 0 and without calling reset_repository -- mirrors
    repository_runner.sh's exact-match `[ "$answer" != "yes" ]` check
    (not a fuzzy y/N confirm).
    """
    calls: list[object] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.repository.reset_repository",
        lambda *_args, **_kwargs: calls.append(True),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "reset"], input="no\n")

    assert result.exit_code == 0, result.output
    assert "Reset cancelled" in result.output
    assert calls == []


def test_reset_confirmed_calls_reset_repository(mock_context: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Answering exactly "yes" proceeds with the reset."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.repository.reset_repository",
        lambda context, **kwargs: calls.append({"context": context, **kwargs}),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "reset", "--quiet"], input="yes\n")

    assert result.exit_code == 0, result.output
    assert calls == [{"context": mock_context, "quiet": True}]
    assert "reset completed successfully" in result.output


def test_reset_reports_failure_and_exits_1(
    mock_context: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ProcessExecutionError partway through reset is reported cleanly, exit code 1."""
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.repository.reset_repository",
        Mock(
            side_effect=ProcessExecutionError(
                message="reinstall failed",
                command=["uv", "sync"],
                returncode=1,
                stdout=None,
                stderr=None,
            )
        ),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "reset"], input="yes\n")

    assert result.exit_code == 1
    assert "Reset failed" in result.output


# --- repository info -------------------------------------------------


def test_info_prints_python_version_and_models(mock_context: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Repository info prints the Python version and discovered models.

    Matches repository_runner.sh's show_info()'s exact output format.
    """
    mock_context.python_binary = "/usr/bin/python3.14"
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.repository.get_python_version",
        lambda context: "Python 3.14.4",  # noqa: ARG005
    )
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.repository.list_repository_models",
        lambda context: [  # noqa: ARG005
            ModelInfo(name="my_model", version="1.0.0"),
            ModelInfo(name="other_model", version="unknown"),
        ],
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "info"])

    assert result.exit_code == 0, result.output
    assert result.output == (
        "Python version: /usr/bin/python3.14\nPython 3.14.4\n\nModels:\n  - my_model: 1.0.0\n  - other_model: unknown\n"
    )


def test_info_prints_no_models_found_when_empty(mock_context: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    """No discovered models -> "No models found.", not an empty list/error."""
    mock_context.python_binary = "/usr/bin/python3.14"
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.repository.get_python_version",
        lambda context: "Python 3.14.4",  # noqa: ARG005
    )
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.repository.list_repository_models",
        lambda context: [],  # noqa: ARG005
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "info"])

    assert result.exit_code == 0, result.output
    assert "No models found." in result.output


def test_info_reports_context_discovery_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A context-discovery failure is reported cleanly, exit code 1."""
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.discover_context",
        Mock(side_effect=ConfigurationError("pyproject.toml not found")),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "info"])

    assert result.exit_code == 1
