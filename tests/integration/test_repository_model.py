# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for `repository model create`/`repository model update`.

Delegation, argument wiring, and error/exit-code handling are covered here
by mocking `discover_context()`/`ModelManager` (mirroring
test_repository_services.py's approach for the other passthrough-style
repository subcommands) -- copier's own rendering/update behavior is
already covered thoroughly, against real templates, by
test_model_manager.py. `test_model_create_and_update_against_real_template`
additionally drives the full stack once, end to end, against a small local
template, to check the command group is wired up correctly.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app
from oarepo_cli.core.config import CliConfig, ModelConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.core.errors import ConfigurationError
from oarepo_cli.ui.console import ConsoleOutput

if TYPE_CHECKING:
    from pathlib import Path

COPIER_YML = """\
model_name:
  type: str
  help: Model name
  when: false

greeting:
  type: str
  default: hello
"""

ANSWERS_FILE_SETTING = '\n_answers_file: "models/{{model_name}}/.copier-answers.yml"\n'
MODEL_FILE_TEMPLATE = 'GREETING = "{{ greeting }}"\n'


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(  # noqa: S603 - just a test, not a security issue to run the program
        ["git", *args],  # noqa: S607 git is ok
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def local_template(tmp_path: Path) -> Path:
    """Create a small, real, git-tracked copier template (model_name + greeting)."""
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "copier.yml").write_text(COPIER_YML + ANSWERS_FILE_SETTING)
    model_dir = template_dir / "models" / "{{model_name}}"
    model_dir.mkdir(parents=True)
    (model_dir / "model.py.jinja").write_text(MODEL_FILE_TEMPLATE)
    (template_dir / "{{_copier_conf.answers_file}}.jinja").write_text("{{ _copier_answers|to_nice_yaml }}\n")
    _git("init", "-q", cwd=template_dir)
    _git("add", "-A", cwd=template_dir)
    _git(
        "-c",
        "user.email=test@test.com",
        "-c",
        "user.name=test",
        "commit",
        "-q",
        "-m",
        "init",
        cwd=template_dir,
    )
    return template_dir


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """Create an empty, git-tracked repository root to render model templates into."""
    root = tmp_path / "repo"
    root.mkdir()
    _git("init", "-q", cwd=root)
    return root


@pytest.fixture
def mock_context(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Mock discover_context() so no real project is needed.

    Patched in both `cli.repository` (used directly by `model update`) and
    `cli.command_wrapper` (used by the `@with_context_and_console` decorator
    wrapping `model create`) since each module holds its own bound reference
    to the imported function.
    """
    context = Mock()
    monkeypatch.setattr("oarepo_cli.cli.repository.discover_context", lambda: context)
    monkeypatch.setattr("oarepo_cli.cli.command_wrapper.discover_context", lambda: context)
    return context


def _fake_model_manager(calls: list[dict[str, object]]) -> type:
    class FakeModelManager:
        def __init__(self, context: object, console: object) -> None:
            calls.append({"context": context, "console": console})
            self._calls = calls

        def create_model(self, name: str, config_file: object = None) -> None:
            self._calls.append({"method": "create_model", "name": name, "config_file": config_file})

        def update_model(self, name: str, answers_file: object = None) -> None:
            self._calls.append({"method": "update_model", "name": name, "answers_file": answers_file})

    return FakeModelManager


def test_model_create_delegates_to_model_manager(mock_context: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    """`repository model create <name>` constructs a ModelManager and calls create_model()."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("oarepo_cli.cli.repository.ModelManager", _fake_model_manager(calls))

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "model", "create", "my_model"])

    assert result.exit_code == 0, result.output
    assert calls[0]["context"] == mock_context
    assert isinstance(calls[0]["console"], ConsoleOutput)
    assert calls[0]["console"].is_quiet is False
    assert calls[1] == {"method": "create_model", "name": "my_model", "config_file": None}


def test_model_create_passes_config_file_and_quiet(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A given config_file positional arg and --quiet are both forwarded."""
    config_file = tmp_path / "answers.yml"
    config_file.write_text("model_name: my_model\n")

    calls: list[dict[str, object]] = []
    monkeypatch.setattr("oarepo_cli.cli.repository.ModelManager", _fake_model_manager(calls))

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "model", "create", "my_model", str(config_file), "--quiet"])

    assert result.exit_code == 0, result.output
    assert calls[0]["context"] == mock_context
    assert isinstance(calls[0]["console"], ConsoleOutput)
    assert calls[0]["console"].is_quiet is True
    assert calls[1] == {
        "method": "create_model",
        "name": "my_model",
        "config_file": config_file,
    }


def test_model_create_reports_error_and_exits_1(
    mock_context: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ConfigurationError raised by ModelManager is reported cleanly, exit code 1."""

    class RaisingModelManager:
        def __init__(self, context: object, console: object) -> None:
            pass

        def create_model(self, name: str, config_file: object = None) -> None:  # noqa: ARG002
            raise ConfigurationError(f"Missing model config file: {config_file}")

    monkeypatch.setattr("oarepo_cli.cli.repository.ModelManager", RaisingModelManager)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "model", "create", "my_model", "missing.yml"])

    assert result.exit_code == 1
    assert "Error creating model" in result.output


def test_model_create_reports_context_discovery_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A context-discovery failure (e.g. no pyproject.toml) is reported cleanly, exit code 1."""

    def raise_config_error() -> None:
        raise ConfigurationError("pyproject.toml not found")

    monkeypatch.setattr("oarepo_cli.cli.repository.discover_context", raise_config_error)
    monkeypatch.setattr("oarepo_cli.cli.command_wrapper.discover_context", raise_config_error)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "model", "create", "my_model"])

    assert result.exit_code == 1


def test_model_update_delegates_to_model_manager(mock_context: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    """`repository model update <name>` constructs a ModelManager and calls update_model()."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("oarepo_cli.cli.repository.ModelManager", _fake_model_manager(calls))

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "model", "update", "my_model"])

    assert result.exit_code == 0, result.output
    assert calls[0]["context"] == mock_context
    assert isinstance(calls[0]["console"], ConsoleOutput)
    assert calls[0]["console"].is_quiet is False
    assert calls[1] == {"method": "update_model", "name": "my_model", "answers_file": None}


def test_model_update_passes_answers_file_and_quiet(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A given answers_file positional arg and --quiet are both forwarded."""
    answers_file = tmp_path / "answers.yml"
    answers_file.write_text("model_name: my_model\n")

    calls: list[dict[str, object]] = []
    monkeypatch.setattr("oarepo_cli.cli.repository.ModelManager", _fake_model_manager(calls))

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "model", "update", "my_model", str(answers_file), "--quiet"])

    assert result.exit_code == 0, result.output
    assert calls[0]["context"] == mock_context
    assert isinstance(calls[0]["console"], ConsoleOutput)
    assert calls[0]["console"].is_quiet is True
    assert calls[1] == {
        "method": "update_model",
        "name": "my_model",
        "answers_file": answers_file,
    }


def test_model_update_reports_error_and_exits_1(
    mock_context: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ConfigurationError raised by ModelManager is reported cleanly, exit code 1."""

    class RaisingModelManager:
        def __init__(self, context: object, console: object) -> None:
            pass

        def update_model(self, name: str, answers_file: object = None) -> None:  # noqa: ARG002
            raise ConfigurationError(f"Model directory 'models/{name}' does not exist.")

    monkeypatch.setattr("oarepo_cli.cli.repository.ModelManager", RaisingModelManager)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "model", "update", "my_model"])

    assert result.exit_code == 1
    assert "Model update failed" in result.output


@pytest.mark.parametrize(
    "args",
    [
        ["repository", "model", "--help"],
        ["repository", "model", "create", "--help"],
        ["repository", "model", "update", "--help"],
    ],
)
def test_model_help_text(args: list[str]) -> None:
    """--help works for the model group and both subcommands, without a real project."""
    runner = CliRunner()
    result = runner.invoke(app, args)

    assert result.exit_code == 0, result.output
    assert "model" in result.output.lower()


def test_model_create_and_update_against_real_template(
    repo_root: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """End-to-end test for model command group wiring.

    Tests that the `model` command group is wired correctly through to real
    copier, for both create and update, against a small local template.

    A config_file is passed to `create` (seeding all answers, including the
    visible `greeting` question) so copier never needs an interactive
    terminal to confirm it -- see ModelManager's class docstring.
    """
    config = CliConfig(model=ModelConfig(template_url=str(local_template), template_version="HEAD"))
    context = ProjectContext(
        root_directory=repo_root,
        pyproject_path=repo_root / "pyproject.toml",
        venv_path=repo_root / ".venv",
        python_binary=repo_root / ".venv" / "bin" / "python",
        oarepo_version=14,
        config=config,
    )
    monkeypatch.setattr("oarepo_cli.cli.repository.discover_context", lambda: context)
    monkeypatch.setattr("oarepo_cli.cli.command_wrapper.discover_context", lambda: context)

    config_file = tmp_path / "answers.yml"
    config_file.write_text("model_name: my_model\ngreeting: hello\n")

    runner = CliRunner()
    create_result = runner.invoke(
        app,
        ["repository", "model", "create", "my_model", str(config_file), "--quiet"],
        catch_exceptions=False,
    )
    assert create_result.exit_code == 0, create_result.output

    rendered = repo_root / "models" / "my_model" / "model.py"
    assert rendered.exists()
    assert rendered.read_text() == 'GREETING = "hello"\n'

    # copier update only works on git-tracked, clean destinations.
    _git("add", "-A", cwd=repo_root)
    _git(
        "-c",
        "user.email=test@test.com",
        "-c",
        "user.name=test",
        "commit",
        "-q",
        "-m",
        "init",
        cwd=repo_root,
    )

    update_result = runner.invoke(app, ["repository", "model", "update", "my_model", "--quiet"], catch_exceptions=False)
    assert update_result.exit_code == 0, update_result.output
