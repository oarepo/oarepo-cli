# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Unit tests for the top-level `new` command (`cli/installer.py`).

Covers argument parsing/defaults and the upfront validation ported from
`repository_installer.sh`'s `parse_arguments()` (uv/uvx/python binaries
must resolve on PATH, repository name must be non-blank) -- the actual
scaffolding (Step 5.2's `RepositoryInstaller`, not implemented yet) isn't
exercised here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _all_binaries_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every binary lookup succeed by default, so tests exercise only what they intend to."""
    monkeypatch.setattr(
        "oarepo_cli.cli.installer.shutil.which",
        lambda name, path=None: f"/usr/bin/{name}",  # noqa: ARG005
    )


def test_new_uses_defaults() -> None:
    """Only REPOSITORY_NAME given: python/template/version/uv/uvx all take their defaults."""
    result = runner.invoke(app, ["new", "my-repo"])

    assert result.exit_code == 0, result.output
    assert "my-repo" in result.output
    assert "https://github.com/oarepo/nrp-app-copier" in result.output
    assert "rdm-14" in result.output


def test_new_passes_all_options(tmp_path: Path) -> None:
    """Every option overrides its default and is reflected in the confirmation message."""
    config_file = tmp_path / "answers.yaml"
    config_file.write_text("repository_name: my-repo\n")

    result = runner.invoke(
        app,
        [
            "new",
            "--python",
            "python3.12",
            "--template",
            "../local-template",
            "--version",
            "rdm-13",
            "--uv",
            "/opt/uv",
            "--uvx",
            "/opt/uvx",
            "--config",
            str(config_file),
            "my-repo",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "../local-template" in result.output
    assert "rdm-13" in result.output


def test_new_requires_repository_name() -> None:
    """Omitting REPOSITORY_NAME entirely is a usage error (Click's own missing-argument handling)."""
    result = runner.invoke(app, ["new"])

    assert result.exit_code == 2


def test_new_rejects_blank_repository_name() -> None:
    """An explicitly blank name is caught by our own validation (exit 1, not Click's exit 2)."""
    result = runner.invoke(app, ["new", "   "])

    assert result.exit_code == 1
    assert "Repository name is required" in result.output


def test_new_reports_missing_uv(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing `uv` binary is reported before anything else runs."""
    monkeypatch.setattr(
        "oarepo_cli.cli.installer.shutil.which",
        lambda name, path=None: None if name == "uv" else f"/usr/bin/{name}",  # noqa: ARG005
    )

    result = runner.invoke(app, ["new", "my-repo"])

    assert result.exit_code == 1
    assert "--uv" in result.output


def test_new_reports_missing_uvx(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing `uvx` binary is reported."""
    monkeypatch.setattr(
        "oarepo_cli.cli.installer.shutil.which",
        lambda name, path=None: None if name == "uvx" else f"/usr/bin/{name}",  # noqa: ARG005
    )

    result = runner.invoke(app, ["new", "my-repo"])

    assert result.exit_code == 1
    assert "--uvx" in result.output


def test_new_reports_missing_python(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing Python binary is reported."""
    monkeypatch.setattr(
        "oarepo_cli.cli.installer.shutil.which",
        lambda name, path=None: None if name == "python3.14" else f"/usr/bin/{name}",  # noqa: ARG005
    )

    result = runner.invoke(app, ["new", "my-repo"])

    assert result.exit_code == 1
    assert "--python" in result.output


def test_new_rejects_missing_config_file() -> None:
    """--config must point at an existing, readable file (Typer's own exists=True check)."""
    result = runner.invoke(app, ["new", "--config", "does-not-exist.yaml", "my-repo"])

    assert result.exit_code == 2


def test_new_help_lists_all_options() -> None:
    """--help documents every option and the positional repository_name argument."""
    result = runner.invoke(app, ["new", "--help"])

    assert result.exit_code == 0
    for expected in (
        "--python",
        "--template",
        "--version",
        "--uv",
        "--uvx",
        "--config",
        "repository_name",
    ):
        assert expected in result.output
