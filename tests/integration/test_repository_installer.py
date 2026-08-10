# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for RepositoryInstaller and the `oarepo-cli new` command.

This file combines both direct RepositoryInstaller testing (against real
copier and a small local template, mirroring test_model_manager.py's approach)
and end-to-end CLI testing (driving the full stack through
`runner.invoke(app, ["new", ...])`).

copier is invoked as an in-process Python library (see
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
from pathlib import Path
from typing import Any

import copier
import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app
from oarepo_cli.core.errors import ConfigurationError
from oarepo_cli.services.repository_installer import RepositoryInstaller
from oarepo_cli.ui import ConsoleOutput

runner = CliRunner()

COPIER_YML = """\
repository_name:
  type: str
  help: Repository name
  when: false
"""


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(  # noqa: S603 - just a test, not a security issue to run the program
        ["git", *args],  # noqa: S607 git is ok
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def local_template(tmp_path: Path) -> Path:
    """Create a small, real, git-tracked copier template.

    With a hidden repository_name question, a rendered README, and the
    docker/variables layout a real repository template has (needed by
    certificate generation/the docker compose cleanup step).
    """
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


@pytest.fixture
def local_template_with_compose(tmp_path: Path) -> Path:
    """Create a variant of local_template with a docker-compose.yml file.

    For end-to-end tests that verify the transient .env symlink dance
    doesn't delete the real compose file.
    """
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "copier.yml").write_text(COPIER_YML)
    (template_dir / "README.md.jinja").write_text("# {{ repository_name }}\n")
    docker_dir = template_dir / "docker"
    docker_dir.mkdir()
    (docker_dir / "docker-compose.yml").write_text("services: {}\n")
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
    """Skip git initialization by default for most tests.

    Most tests here aren't about git initialization -- skip it (as in CI)
    by default, so only the tests that care about it opt back in.
    """
    monkeypatch.setenv("CI", "true")


# --- Direct RepositoryInstaller tests (service layer) ---


def test_install_renders_local_template(tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Install renders the template for real into ./<name>.

    Uses repository_name as data.
    """
    monkeypatch.chdir(tmp_path)

    target = RepositoryInstaller(ConsoleOutput(quiet=True)).install(
        "my-repo", template=str(local_template), version="HEAD"
    )

    assert target == tmp_path / "my-repo"
    assert (target / "README.md").read_text() == "# my-repo\n"


def test_install_config_file_answers_but_repository_name_always_wins(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Config file seeds answers, but repository_name is always forced to the given name.

    Mirrors repository_installer.sh's unconditional `-d repository_name=`,
    passed even when --data-file is also given (unlike ModelManager's create_model).
    """
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
    """A non-existent config_file raises ConfigurationError.

    The error is raised before copier ever runs.
    """
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
    """VCS ref is only passed to copier for https:// template URLs.

    Never for local paths (mirrors repository_installer.sh's `if [[ "${template}" == https://* ]]`).
    """
    monkeypatch.chdir(tmp_path)
    calls: list[dict[str, Any]] = []
    real_run_copy = copier.run_copy

    def spy_run_copy(*args: Any, **kwargs: Any) -> Any:
        calls.append(kwargs)
        return real_run_copy(*args, **kwargs)

    monkeypatch.setattr("oarepo_cli.services.repository_installer.copier.run_copy", spy_run_copy)

    RepositoryInstaller(ConsoleOutput(quiet=True)).install("my-repo", template=str(local_template), version="some-ref")

    assert calls[0]["vcs_ref"] is None


def test_install_copies_run_script(tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The bundled repository_run.sh is copied to run.sh and made executable.

    Mirrors oarepo_cli/scripts/README.md: "The repository installer will
    automatically copy the repository_run.sh into the run.sh script when
    the repository is installed."
    """
    monkeypatch.chdir(tmp_path)

    target = RepositoryInstaller(ConsoleOutput(quiet=True)).install(
        "my-repo", template=str(local_template), version="HEAD"
    )

    run_script = target / "run.sh"
    bundled_script = Path(__file__).parent.parent.parent / "oarepo_cli" / "scripts" / "repository_run.sh"
    assert run_script.read_text() == bundled_script.read_text()
    assert run_script.stat().st_mode & 0o111, "run.sh is not executable"


def test_install_generates_development_certificates(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Openssl generates a real self-signed cert/key pair under docker/."""
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
    """The docker/.env symlink used for docker compose down is removed afterward."""
    monkeypatch.chdir(tmp_path)

    target = RepositoryInstaller(ConsoleOutput(quiet=True)).install(
        "my-repo", template=str(local_template), version="HEAD"
    )

    assert not (target / "docker" / ".env").is_symlink()
    assert not (target / "docker" / ".env").exists()


def test_install_initializes_git_repository(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Git is initialized with an initial commit without CI set."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CI", raising=False)

    target = RepositoryInstaller(ConsoleOutput(quiet=True)).install(
        "my-repo", template=str(local_template), version="HEAD"
    )

    assert (target / ".git").is_dir()
    log = subprocess.run(
        ["git", "log", "--oneline"],  # noqa: S607 git is ok
        cwd=target,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Initial commit" in log.stdout


def test_install_skips_git_when_ci_env_set(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Git init is skipped entirely when CI is set.

    CI can be set to any non-empty value, not just "true".
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CI", "1")

    target = RepositoryInstaller(ConsoleOutput(quiet=True)).install(
        "my-repo", template=str(local_template), version="HEAD"
    )

    assert not (target / ".git").exists()


def test_install_skips_git_without_git_installed(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Git init is skipped entirely without git on PATH.

    Mirrors repository_installer.sh's `command -v git` check.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr("oarepo_cli.services.repository_installer.shutil.which", lambda _name: None)

    target = RepositoryInstaller(ConsoleOutput(quiet=True)).install(
        "my-repo", template=str(local_template), version="HEAD"
    )

    assert not (target / ".git").exists()


# --- End-to-end CLI tests (full stack through `oarepo-cli new`) ---


def test_new_full_installation_flow(
    tmp_path: Path, local_template_with_compose: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Oarepo-cli new renders the template and generates certificates.

    Cleans up the transient docker/.env symlink (while leaving the template's
    own docker-compose.yml untouched), and initializes git -- all through the
    real CLI entry point, exit code 0.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CI", raising=False)  # exercise real git init too

    result = runner.invoke(
        app,
        ["new", "--template", str(local_template_with_compose), "--version", "HEAD", "my-repo"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    target = tmp_path / "my-repo"
    assert (target / "README.md").read_text() == "# my-repo\n"

    # Certificate files exist
    assert (target / "docker" / "development.crt").read_text().count("BEGIN CERTIFICATE") == 1
    assert (target / "docker" / "development.key").exists()

    # The template's own docker compose file survived the transient .env symlink dance
    assert (target / "docker" / "docker-compose.yml").exists()
    assert not (target / "docker" / ".env").exists()

    # Git repo initialized with an initial commit
    assert (target / ".git").is_dir()
    log = subprocess.run(
        ["git", "log", "--oneline"],  # noqa: S607 git is ok
        cwd=target,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Initial commit" in log.stdout


def test_new_template_variation_vcs_ref_only_for_github_style_urls(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Version is only forwarded to copier as vcs_ref for https:// templates.

    Never for local paths -- exercised through the full CLI, not just
    RepositoryInstaller directly, confirming the CLI layer forwards
    --template/--version correctly.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CI", "true")
    calls: list[dict[str, Any]] = []

    # Local template: real end-to-end run, vcs_ref must come through as None.
    real_run_copy = copier.run_copy

    def spy_run_copy(*args: Any, **kwargs: Any) -> Any:
        calls.append(kwargs)
        return real_run_copy(*args, **kwargs)

    monkeypatch.setattr("oarepo_cli.services.repository_installer.copier.run_copy", spy_run_copy)

    result = runner.invoke(
        app,
        ["new", "--template", str(local_template), "--version", "some-ref", "repo-local"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert calls[0]["vcs_ref"] is None

    # GitHub-style URL: faked (no real network), but confirms the CLI forwards
    # --version as vcs_ref down to copier for an https:// --template.
    calls.clear()

    def fake_run_copy(template: str, dst: Path, **kwargs: Any) -> None:
        calls.append(kwargs)
        (dst / "docker").mkdir(parents=True)

    monkeypatch.setattr("oarepo_cli.services.repository_installer.copier.run_copy", fake_run_copy)

    result = runner.invoke(
        app,
        [
            "new",
            "--template",
            "https://example.com/org/template.git",
            "--version",
            "v2",
            "repo-github",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert calls[0]["vcs_ref"] == "v2"


def test_new_reports_invalid_template_gracefully(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An invalid/nonexistent --template is reported with a clean error message.

    Uses the same "Repository creation failed" message as any other failure,
    not an uncaught traceback. Copier itself raises inconsistent exception
    types here (a bare ValueError for this particular case, not one of its
    own copier.errors.CopierError subclasses), which RepositoryInstaller
    normalizes into ConfigurationError.
    """
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["new", "--template", str(tmp_path / "does-not-exist"), "my-repo"])

    assert result.exit_code == 1
    assert result.exception is not None
    assert isinstance(result.exception, SystemExit)
    assert "✗ Repository creation failed" in result.output
    assert not (tmp_path / "my-repo").exists()


def test_new_reports_missing_python_binary_gracefully(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A --python binary that doesn't resolve on PATH is rejected early.

    Rejected before anything else runs -- exercised with a real,
    definitely-nonexistent path.
    """
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["new", "--python", "/definitely/does/not/exist", "my-repo"])

    assert result.exit_code == 1
    assert "--python" in result.output
    assert not (tmp_path / "my-repo").exists()
