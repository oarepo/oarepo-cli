# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for RepositoryInstaller, against real copier and a small local template.

Mirrors test_model_manager.py's approach for ModelManager: copier is
invoked as an in-process Python library (see
services/repository_installer.py's module docstring), so these tests run
copier for real against a small local template fixture (fast: no network,
no ephemeral uvx environment to bootstrap) rather than mocking copier's
Python API. openssl/git/docker are all real, fast, side-effect-free
invocations for a repository that's never actually started -- `docker
compose down` fails fast and harmlessly without a running daemon or
compose file present, matching the shell script's own `|| true`.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any

import copier
import pytest

from oarepo_cli.core.errors import ConfigurationError
from oarepo_cli.services.repository_installer import RepositoryInstaller
from oarepo_cli.ui import ConsoleOutput

if TYPE_CHECKING:
    from pathlib import Path

COPIER_YML = """\
repository_name:
  type: str
  help: Repository name
  when: false
"""


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def local_template(tmp_path: Path) -> Path:
    """A small, real, git-tracked copier template: a hidden repository_name
    question, a rendered README, and the docker/variables layout a real
    repository template has (needed by certificate generation/the docker
    compose cleanup step)."""
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "copier.yml").write_text(COPIER_YML)
    (template_dir / "README.md.jinja").write_text("# {{ repository_name }}\n")
    docker_dir = template_dir / "docker"
    docker_dir.mkdir()
    (docker_dir / ".gitkeep").write_text("")
    (template_dir / "variables").write_text("INVENIO_UI_PORT=5000\n")

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


@pytest.fixture(autouse=True)
def _skip_git_init_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Most tests here aren't about git initialization -- skip it (as in CI) by
    default, so only the tests that care about it opt back in."""
    monkeypatch.setenv("CI", "true")


def test_install_renders_local_template(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """install() renders the template for real into ./<name>, using repository_name as data."""
    monkeypatch.chdir(tmp_path)

    target = RepositoryInstaller(ConsoleOutput(quiet=True)).install(
        "my-repo", template=str(local_template), version="HEAD"
    )

    assert target == tmp_path / "my-repo"
    assert (target / "README.md").read_text() == "# my-repo\n"


def test_install_config_file_answers_but_repository_name_always_wins(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A --config data file seeds answers, but repository_name is always forced to the
    given name -- mirrors repository_installer.sh's unconditional `-d repository_name=`,
    passed even when --data-file is also given (unlike ModelManager's create_model)."""
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "answers.yml"
    config_file.write_text("repository_name: wrong-name\n")

    target = RepositoryInstaller(ConsoleOutput(quiet=True)).install(
        "my-repo", template=str(local_template), version="HEAD", config_file=config_file
    )

    assert target == tmp_path / "my-repo"
    assert (target / "README.md").read_text() == "# my-repo\n"


def test_install_missing_config_file_raises(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-existent config_file raises ConfigurationError before copier ever runs."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ConfigurationError, match="Missing repository config file"):
        RepositoryInstaller(ConsoleOutput(quiet=True)).install(
            "my-repo",
            template=str(local_template),
            version="HEAD",
            config_file=tmp_path / "does-not-exist.yml",
        )


def test_template_url_handling_vcs_ref_only_for_github_urls(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """vcs_ref is only passed to copier for https:// template URLs, never for local paths
    (mirrors repository_installer.sh's `if [[ "${template}" == https://* ]]`)."""
    monkeypatch.chdir(tmp_path)
    calls: list[dict[str, Any]] = []
    real_run_copy = copier.run_copy

    def spy_run_copy(*args: Any, **kwargs: Any) -> Any:
        calls.append(kwargs)
        return real_run_copy(*args, **kwargs)

    monkeypatch.setattr("oarepo_cli.services.repository_installer.copier.run_copy", spy_run_copy)

    RepositoryInstaller(ConsoleOutput(quiet=True)).install(
        "my-repo", template=str(local_template), version="some-ref"
    )

    assert calls[0]["vcs_ref"] is None


def test_install_generates_development_certificates(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """openssl generates a real self-signed cert/key pair under docker/."""
    monkeypatch.chdir(tmp_path)

    target = RepositoryInstaller(ConsoleOutput(quiet=True)).install(
        "my-repo", template=str(local_template), version="HEAD"
    )

    cert = target / "docker" / "development.crt"
    key = target / "docker" / "development.key"
    assert cert.exists()
    assert key.exists()
    assert "BEGIN CERTIFICATE" in cert.read_text()


def test_install_removes_transient_env_symlink(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The docker/.env symlink used for `docker compose down` is removed again afterward."""
    monkeypatch.chdir(tmp_path)

    target = RepositoryInstaller(ConsoleOutput(quiet=True)).install(
        "my-repo", template=str(local_template), version="HEAD"
    )

    assert not (target / "docker" / ".env").is_symlink()
    assert not (target / "docker" / ".env").exists()


def test_install_initializes_git_repository(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without CI set, git is initialized with an initial commit."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CI", raising=False)

    target = RepositoryInstaller(ConsoleOutput(quiet=True)).install(
        "my-repo", template=str(local_template), version="HEAD"
    )

    assert (target / ".git").is_dir()
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=target, check=True, capture_output=True, text=True
    )
    assert "Initial commit" in log.stdout


def test_install_skips_git_when_ci_env_set(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With CI set (to any non-empty value, not just "true"), git init is skipped entirely."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CI", "1")

    target = RepositoryInstaller(ConsoleOutput(quiet=True)).install(
        "my-repo", template=str(local_template), version="HEAD"
    )

    assert not (target / ".git").exists()


def test_install_skips_git_without_git_installed(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without git on PATH, git init is skipped entirely (mirrors repository_installer.sh's
    `command -v git` check)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr("oarepo_cli.services.repository_installer.shutil.which", lambda _name: None)

    target = RepositoryInstaller(ConsoleOutput(quiet=True)).install(
        "my-repo", template=str(local_template), version="HEAD"
    )

    assert not (target / ".git").exists()
