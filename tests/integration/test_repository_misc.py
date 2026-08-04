# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for `repository cli`/`invenio`/`shell`/`translations`/`index rebuild`/`reset`/`info`.

Delegation, argument wiring, and error/exit-code handling are covered here
by mocking `discover_context()` and the specific service function/module
each subcommand delegates to (mirroring test_repository_local.py's/
test_repository_run.py's approach for the other "thin CLI wrapper over a
service" repository subcommands) -- the underlying subprocess sequencing
for `index rebuild`/`reset` is already covered by
tests/unit/test_repository_service.py's `rebuild_index`/`reset_repository`
tests, and invenio-cli process replacement is already covered by
test_server_runner.py/test_repository_run.py.
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


# --- repository cli ---------------------------------------------------


def test_cli_delegates_to_exec_invenio_cli(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository cli <args>` execs invenio-cli with the given args verbatim."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.invenio_cli.exec_invenio_cli",
        lambda context, args, **_kwargs: calls.append({"context": context, "args": list(args)}),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "cli", "services", "status"])

    assert result.exit_code == 0, result.output
    assert calls == [{"context": mock_context, "args": ["services", "status"]}]


def test_cli_help_forwarded_to_invenio_cli(
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--help is forwarded to invenio-cli rather than intercepted by Typer/Click."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.invenio_cli.exec_invenio_cli",
        lambda _context, args, **_kwargs: calls.append({"args": list(args)}),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "cli", "--help"])

    assert result.exit_code == 0, result.output
    assert calls == [{"args": ["--help"]}]


def test_cli_reports_context_discovery_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A context-discovery failure is reported cleanly, exit code 1."""
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.discover_context",
        Mock(side_effect=ConfigurationError("pyproject.toml not found")),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "cli", "services", "status"])

    assert result.exit_code == 1


# --- repository invenio -------------------------------------------------


def test_invenio_delegates_to_exec_invenio(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository invenio <args>` execs the bare invenio binary with the given args
    verbatim (not invenio-cli -- see `repository cli` for that)."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.repository.exec_invenio",
        lambda context, args, **_kwargs: calls.append({"context": context, "args": list(args)}),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "invenio", "db", "upgrade"])

    assert result.exit_code == 0, result.output
    assert calls == [{"context": mock_context, "args": ["db", "upgrade"]}]


def test_invenio_help_forwarded_to_invenio(
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--help is forwarded to invenio rather than intercepted by Typer/Click."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.repository.exec_invenio",
        lambda _context, args, **_kwargs: calls.append({"args": list(args)}),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "invenio", "--help"])

    assert result.exit_code == 0, result.output
    assert calls == [{"args": ["--help"]}]


def test_invenio_reports_context_discovery_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A context-discovery failure is reported cleanly, exit code 1."""
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.discover_context",
        Mock(side_effect=ConfigurationError("pyproject.toml not found")),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "invenio", "db", "upgrade"])

    assert result.exit_code == 1


# --- repository shell ----------------------------------------------------


def test_shell_starts_services_by_default_then_execs_shell(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository shell` starts Docker services via invenio-cli (like `repository run`,
    not ServicesLifecycleManager) before exec'ing the shell, by default."""
    services_calls: list[dict[str, object]] = []
    shell_calls: list[object] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.invenio_cli.run_invenio_cli",
        lambda context, args, **kwargs: services_calls.append(
            {"context": context, "args": list(args), **kwargs}
        ),
    )
    monkeypatch.setattr("oarepo_cli.cli.repository.repository.exec_shell", shell_calls.append)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "shell"])

    assert result.exit_code == 0, result.output
    assert services_calls == [
        {"context": mock_context, "args": ["services", "start"], "quiet": False}
    ]
    assert shell_calls == [mock_context]


def test_shell_no_services_skips_starting_services(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--no-services skips starting Docker services but still execs the shell."""
    services_calls: list[object] = []
    shell_calls: list[object] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.invenio_cli.run_invenio_cli",
        lambda *args, **kwargs: services_calls.append((args, kwargs)),
    )
    monkeypatch.setattr("oarepo_cli.cli.repository.repository.exec_shell", shell_calls.append)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "shell", "--no-services"])

    assert result.exit_code == 0, result.output
    assert services_calls == []
    assert shell_calls == [mock_context]


def test_shell_quiet_forwarded_to_services_start(
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--quiet is forwarded to the services-start invenio-cli call."""
    services_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.invenio_cli.run_invenio_cli",
        lambda context, args, **kwargs: services_calls.append(
            {"context": context, "args": list(args), **kwargs}
        ),
    )
    monkeypatch.setattr("oarepo_cli.cli.repository.repository.exec_shell", lambda _context: None)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "shell", "--quiet"])

    assert result.exit_code == 0, result.output
    assert services_calls[0]["quiet"] is True


def test_shell_reports_context_discovery_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A context-discovery failure is reported cleanly, exit code 1."""
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.discover_context",
        Mock(side_effect=ConfigurationError("pyproject.toml not found")),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "shell"])

    assert result.exit_code == 1


def test_shell_reports_services_start_failure_and_never_execs_shell(
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ProcessExecutionError starting services is reported cleanly, exit code 1, and
    the shell is never exec'd."""
    shell_calls: list[object] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.invenio_cli.run_invenio_cli",
        Mock(
            side_effect=ProcessExecutionError(
                message="invenio-cli services start failed",
                command=["invenio-cli", "services", "start"],
                returncode=1,
                stdout=None,
                stderr=None,
            )
        ),
    )
    monkeypatch.setattr("oarepo_cli.cli.repository.repository.exec_shell", shell_calls.append)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "shell"])

    assert result.exit_code == 1
    assert shell_calls == []


# --- repository translations -------------------------------------------


def test_translations_no_args_runs_make_translations(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository translations` (no args) runs make-translations with no extra args."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.translations.run_translations",
        lambda context, **kwargs: (
            calls.append({"context": context, **kwargs}) or _fake_process_result()
        ),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "translations"])

    assert result.exit_code == 0, result.output
    assert calls == [{"context": mock_context, "extra_args": [], "quiet": False}]


def test_translations_compile_delegates_to_invenio_cli(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository translations compile` delegates to `invenio-cli translations compile`,
    not make-translations."""
    make_translations_calls: list[object] = []
    invenio_cli_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.translations.run_translations",
        lambda *_args, **_kwargs: make_translations_calls.append(True) or _fake_process_result(),
    )
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.invenio_cli.run_invenio_cli",
        lambda context, args, **kwargs: invenio_cli_calls.append(
            {"context": context, "args": list(args), **kwargs}
        ),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "translations", "compile"])

    assert result.exit_code == 0, result.output
    assert make_translations_calls == []
    assert invenio_cli_calls == [
        {"context": mock_context, "args": ["translations", "compile"], "quiet": False}
    ]


def test_translations_other_args_forwarded_to_make_translations(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Any first arg other than exactly "compile" is forwarded to make-translations,
    mirroring repository_runner.sh's translations()'s exact-match check."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.translations.run_translations",
        lambda context, **kwargs: (
            calls.append({"context": context, **kwargs}) or _fake_process_result()
        ),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "translations", "--verbose"])

    assert result.exit_code == 0, result.output
    assert calls == [{"context": mock_context, "extra_args": ["--verbose"], "quiet": False}]


def test_translations_reports_failure_and_exits_1(
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing make-translations run is reported cleanly, exit code 1."""
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.translations.run_translations",
        lambda *_args, **_kwargs: _fake_process_result(return_code=1),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "translations"])

    assert result.exit_code == 1
    assert "Translations failed" in result.output


def test_translations_reports_context_discovery_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A context-discovery failure is reported cleanly, exit code 1."""
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.discover_context",
        Mock(side_effect=ConfigurationError("pyproject.toml not found")),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "translations"])

    assert result.exit_code == 1


# --- repository index rebuild -------------------------------------------


def test_index_rebuild_delegates_to_service(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
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
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-OARepoError raised by rebuild_index propagates instead of being turned
    into a clean "exit 1" -- regression test locking in repository.py's existing,
    narrow except OARepoError (simplified from except (OARepoError,
    ProcessExecutionError) in Step 4.12, since ProcessExecutionError already
    subclasses OARepoError)."""
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
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anything other than exactly "yes" cancels the reset without error, exit code 0,
    and without calling reset_repository -- mirrors repository_runner.sh's exact-match
    `[ "$answer" != "yes" ]` check (not a fuzzy y/N confirm)."""
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


def test_reset_confirmed_calls_reset_repository(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
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


def test_info_prints_python_version_and_models(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository info` prints the Python version and discovered models, matching
    repository_runner.sh's show_info()'s exact output format."""
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
        "Python version: /usr/bin/python3.14\n"
        "Python 3.14.4\n"
        "\n"
        "Models:\n"
        "  - my_model: 1.0.0\n"
        "  - other_model: unknown\n"
    )


def test_info_prints_no_models_found_when_empty(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
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
