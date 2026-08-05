# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""End-to-end tests for the `oarepo-cli new` command.

Unlike test_repository_installer.py (which exercises RepositoryInstaller
directly, mirroring test_model_manager.py's approach for ModelManager),
these tests drive the full stack through the CLI entry point
(`runner.invoke(app, ["new", ...])`), the same way
test_repository_model.py's `test_model_create_and_update_against_real_template`
checks the `model` command group is wired up correctly end to end -- here
confirming argument parsing, validation, RepositoryInstaller delegation,
and error reporting all work together, against a small local template
(fast: no network, no ephemeral uvx environment to bootstrap).
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any

import copier
import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

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
    """A small, real, git-tracked copier template with the docker/ layout (including
    a docker-compose.yml, unlike test_repository_installer.py's fixture) a real
    repository template has."""
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


def test_new_full_installation_flow(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`oarepo-cli new` renders the template, generates certificates, cleans up
    the transient docker/.env symlink (while leaving the template's own
    docker-compose.yml untouched), and initializes git -- all through the
    real CLI entry point, exit code 0."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CI", raising=False)  # exercise real git init too

    result = runner.invoke(
        app,
        ["new", "--template", str(local_template), "--version", "HEAD", "my-repo"],
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
        ["git", "log", "--oneline"], cwd=target, check=True, capture_output=True, text=True
    )
    assert "Initial commit" in log.stdout


def test_new_template_variation_vcs_ref_only_for_github_style_urls(
    tmp_path: Path, local_template: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--version is only forwarded to copier as vcs_ref for https:// (GitHub-style)
    templates, never for local paths -- exercised through the full CLI, not just
    RepositoryInstaller directly (unlike test_repository_installer.py's equivalent
    check), confirming the CLI layer forwards --template/--version correctly."""
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

    def fake_run_copy(template: str, dst: Path, **kwargs: Any) -> None:  # noqa: ARG001
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


def test_new_reports_invalid_template_gracefully(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An invalid/nonexistent --template is reported with the same clean
    "Repository creation failed" message as any other failure, not an
    uncaught traceback -- copier itself raises inconsistent exception types
    here (a bare ValueError for this particular case, not one of its own
    copier.errors.CopierError subclasses), which RepositoryInstaller
    normalizes into ConfigurationError."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["new", "--template", str(tmp_path / "does-not-exist"), "my-repo"])

    assert result.exit_code == 1
    assert result.exception is not None
    assert isinstance(result.exception, SystemExit)
    assert "✗ Repository creation failed" in result.output
    assert not (tmp_path / "my-repo").exists()


def test_new_reports_missing_python_binary_gracefully(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A --python binary that doesn't resolve on PATH is rejected before anything
    else runs -- exercised with a real, definitely-nonexistent path (unlike
    test_installer_cli.py's equivalent unit test, which mocks shutil.which)."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["new", "--python", "/definitely/does/not/exist", "my-repo"])

    assert result.exit_code == 1
    assert "--python" in result.output
    assert not (tmp_path / "my-repo").exists()
