# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for ModelManager, against real copier and small local templates.

Unlike most other external-tool integrations in this codebase, copier is
invoked here as an in-process Python library (see services/models.py's
module docstring) rather than shelled out to a subprocess, so
pytest-subprocess's fake_process fixture doesn't apply -- there's no
subprocess to intercept. Instead, these tests run copier for real against
small local template fixtures (fast: no network, no ephemeral uvx
environment to bootstrap), which is both simpler and a more faithful test
than mocking copier's Python API would be.

Two template fixtures are used:
- ``static_template``: a single hidden (``when: false``) ``model_name``
  question and static rendered content. Mirrors the "no config file"
  create_model() call, which only ever supplies ``model_name`` via data --
  copier never writes an answers file when every question is hidden (real,
  observed copier 9.x behaviour), so this fixture is unsuitable for testing
  update_model().
- ``answered_template``: adds a second, *visible* ``greeting`` question, so
  copier records a real ``.copier-answers.yml`` -- needed to exercise
  create_model(config_file=...) and update_model().
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import copier
import pytest

from oarepo_cli.core.config import CliConfig, ModelConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.core.errors import ConfigurationError
from oarepo_cli.services.models import ModelManager
from oarepo_cli.ui import ConsoleOutput

STATIC_COPIER_YML = """\
model_name:
  type: str
  help: Model name
  when: false
"""

ANSWERED_COPIER_YML = """\
model_name:
  type: str
  help: Model name
  when: false

greeting:
  type: str
  default: hello
"""

ANSWERS_FILE_SETTING = '\n_answers_file: "models/{{model_name}}/.copier-answers.yml"\n'

STATIC_TEMPLATE_FILE = 'GREETING = "hello"\n'
ANSWERED_TEMPLATE_FILE = 'GREETING = "{{ greeting }}"\n'


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _write_template(template_dir: Path, copier_yml: str, model_file_content: str) -> None:
    template_dir.mkdir()
    (template_dir / "copier.yml").write_text(copier_yml + ANSWERS_FILE_SETTING)
    model_dir = template_dir / "models" / "{{model_name}}"
    model_dir.mkdir(parents=True)
    (model_dir / "model.py.jinja").write_text(model_file_content)
    # copier does NOT auto-write the answers file -- the template itself
    # must contain a file that renders the special `_copier_answers`
    # context variable (this is the exact mechanism nrp-app-copier/
    # nrp-model-copier use too, via `{{_copier_conf.answers_file}}.copier`).
    (template_dir / "{{_copier_conf.answers_file}}.jinja").write_text(
        "{{ _copier_answers|to_nice_yaml }}\n"
    )
    # copier records the template's commit/ref in the answers file, which
    # update_model() later needs to know what to update *from* -- so, like
    # any real copier template, this one must be a real git repo.
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


@pytest.fixture
def static_template(tmp_path: Path) -> Path:
    """A template with only a hidden model_name question and static content."""
    template_dir = tmp_path / "static_template"
    _write_template(template_dir, STATIC_COPIER_YML, STATIC_TEMPLATE_FILE)
    return template_dir


@pytest.fixture
def answered_template(tmp_path: Path) -> Path:
    """A template with a hidden model_name question plus a real, recorded greeting question."""
    template_dir = tmp_path / "answered_template"
    _write_template(template_dir, ANSWERED_COPIER_YML, ANSWERED_TEMPLATE_FILE)
    return template_dir


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """An empty repository root to render model templates into."""
    root = tmp_path / "repo"
    root.mkdir()
    return root


def make_context(root: Path, template_dir: Path, *, version: str = "") -> ProjectContext:
    config = CliConfig(model=ModelConfig(template_url=str(template_dir), template_version=version))
    return ProjectContext(
        root_directory=root,
        pyproject_path=root / "pyproject.toml",
        venv_path=root / ".venv",
        python_binary=root / ".venv" / "bin" / "python",
        oarepo_version=14,
        config=config,
    )


def test_create_model_renders_local_template(repo_root: Path, static_template: Path) -> None:
    """create_model() renders the template for real, using model_name as data."""
    context = make_context(repo_root, static_template)
    manager = ModelManager(context, ConsoleOutput(quiet=True))

    manager.create_model("my_model")

    rendered = repo_root / "models" / "my_model" / "model.py"
    assert rendered.exists()
    assert rendered.read_text() == 'GREETING = "hello"\n'


def test_create_model_with_config_file_seeds_answers(
    repo_root: Path, answered_template: Path, tmp_path: Path
) -> None:
    """create_model(config_file=...) seeds all answers from that file (model_name included),
    mirroring repository_runner.sh: when a config file is given, -d model_name is NOT also
    passed -- the file must supply model_name itself."""
    config_file = tmp_path / "answers.yml"
    config_file.write_text("model_name: configured_model\ngreeting: hi there\n")

    context = make_context(repo_root, answered_template)
    manager = ModelManager(context, ConsoleOutput(quiet=True))

    manager.create_model("ignored_name", config_file=config_file)

    rendered = repo_root / "models" / "configured_model" / "model.py"
    assert rendered.exists()
    assert rendered.read_text() == 'GREETING = "hi there"\n'
    assert (repo_root / "models" / "configured_model" / ".copier-answers.yml").exists()


def test_create_model_missing_config_file_raises(repo_root: Path, static_template: Path) -> None:
    """A non-existent config_file raises ConfigurationError before copier ever runs."""
    context = make_context(repo_root, static_template)
    manager = ModelManager(context, ConsoleOutput(quiet=True))

    with pytest.raises(ConfigurationError, match="Missing model config file"):
        manager.create_model("my_model", config_file=repo_root / "does-not-exist.yml")


def test_create_model_reinstalls_when_venv_exists(
    repo_root: Path, static_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If a venv already exists, the repository is reinstalled after model creation."""
    (repo_root / ".venv").mkdir()

    calls: list[tuple[ProjectContext, dict[str, Any]]] = []
    monkeypatch.setattr(
        "oarepo_cli.services.models.install_repository",
        lambda context, **kwargs: calls.append((context, kwargs)),
    )

    context = make_context(repo_root, static_template)
    manager = ModelManager(context, ConsoleOutput(quiet=True))

    manager.create_model("my_model")

    assert len(calls) == 1
    assert calls[0][0] is context
    assert calls[0][1] == {"quiet": True}


def test_create_model_skips_reinstall_without_venv(
    repo_root: Path, static_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without an existing venv, no reinstall is attempted."""
    calls: list[tuple[ProjectContext, dict[str, Any]]] = []
    monkeypatch.setattr(
        "oarepo_cli.services.models.install_repository",
        lambda context, **kwargs: calls.append((context, kwargs)),
    )

    context = make_context(repo_root, static_template)
    manager = ModelManager(context, ConsoleOutput(quiet=True))

    manager.create_model("my_model")

    assert calls == []


def test_template_url_handling_vcs_ref_only_for_github_urls(
    repo_root: Path, static_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """vcs_ref is only passed to copier for github:// template URLs, never for local paths
    (mirrors repository_runner.sh's `if [[ "${MODEL_TEMPLATE}" == https://* ]]`)."""
    calls: list[dict[str, Any]] = []
    real_run_copy = copier.run_copy

    def spy_run_copy(*args: Any, **kwargs: Any) -> Any:
        calls.append(kwargs)
        return real_run_copy(*args, **kwargs)

    monkeypatch.setattr("oarepo_cli.services.models.copier.run_copy", spy_run_copy)

    # Local template path: vcs_ref must be None even though template_version is set.
    context = make_context(repo_root, static_template, version="some-ref")
    ModelManager(context, ConsoleOutput(quiet=True)).create_model("my_model")

    assert calls[0]["vcs_ref"] is None


def test_update_model_calls_copier_update_correctly(
    repo_root: Path, answered_template: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """update_model() calls copier.run_update() with the right destination, answers
    file (relative to repo root, matching create_model()'s recorded location),
    conflict/unsafe/overwrite settings, and succeeds against a real, git-tracked
    project -- i.e. the wiring is correct. copier's own 3-way-merge update
    semantics (what specifically changes on disk for a given template diff) are
    that library's concern, not re-tested here.

    copier only supports updating git-tracked, clean subprojects, matching real
    usage (a real OARepo repository is always its own git repo -- see
    repository_installer.sh's `git init` step), so repo_root is committed here,
    like a real user's workflow would be.
    """
    config_file = tmp_path / "answers.yml"
    config_file.write_text("model_name: my_model\ngreeting: hello\n")

    context = make_context(repo_root, answered_template, version="HEAD")
    manager = ModelManager(context, ConsoleOutput(quiet=True))
    manager.create_model("my_model", config_file=config_file)

    _git("init", "-q", cwd=repo_root)
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

    calls: list[dict[str, Any]] = []
    real_run_update = copier.run_update

    def spy_run_update(*args: Any, **kwargs: Any) -> Any:
        calls.append(kwargs)
        return real_run_update(*args, **kwargs)

    monkeypatch.setattr("oarepo_cli.services.models.copier.run_update", spy_run_update)

    manager.update_model("my_model")

    assert len(calls) == 1
    assert calls[0]["answers_file"] == Path("models/my_model/.copier-answers.yml")
    assert calls[0]["vcs_ref"] == "HEAD"
    assert calls[0]["conflict"] == "inline"
    assert calls[0]["unsafe"] is True
    assert calls[0]["overwrite"] is True


def test_update_model_missing_model_dir_raises(repo_root: Path, static_template: Path) -> None:
    """update_model() on a model that was never created raises ConfigurationError."""
    context = make_context(repo_root, static_template)
    manager = ModelManager(context, ConsoleOutput(quiet=True))

    with pytest.raises(ConfigurationError, match="does not exist"):
        manager.update_model("never_created")


def test_update_model_missing_answers_file_raises(
    repo_root: Path, answered_template: Path, tmp_path: Path
) -> None:
    """An explicitly given answers_file that doesn't exist raises ConfigurationError."""
    config_file = tmp_path / "answers.yml"
    config_file.write_text("model_name: my_model\ngreeting: hello\n")

    context = make_context(repo_root, answered_template)
    manager = ModelManager(context, ConsoleOutput(quiet=True))
    manager.create_model("my_model", config_file=config_file)

    with pytest.raises(ConfigurationError, match="does not exist"):
        manager.update_model("my_model", answers_file=repo_root / "missing.yml")
