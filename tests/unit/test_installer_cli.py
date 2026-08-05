# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Unit tests for the top-level `new` command (`cli/installer.py`).

Covers argument parsing/defaults, the upfront validation ported from
`repository_installer.sh`'s `parse_arguments()` (uv/uvx/python binaries
must resolve on PATH, repository name must be non-blank), and delegation
to `RepositoryInstaller` -- mocked here the same way
test_repository_model.py mocks `ModelManager` for `repository model
create`, since the actual scaffolding is already covered against a real
local template by tests/integration/test_repository_installer.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app
from oarepo_cli.core.errors import ConfigurationError

if TYPE_CHECKING:
    from oarepo_cli.ui import ConsoleOutput

runner = CliRunner()


@pytest.fixture(autouse=True)
def _all_binaries_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every binary lookup succeed by default, so tests exercise only what they intend to."""
    monkeypatch.setattr(
        "oarepo_cli.cli.installer.shutil.which",
        lambda name, path=None: f"/usr/bin/{name}",  # noqa: ARG005
    )


def _fake_repository_installer(calls: list[dict[str, object]]) -> type:
    class FakeRepositoryInstaller:
        def __init__(self, console: ConsoleOutput) -> None:
            calls.append({"console": console})

        def install(
            self,
            name: str,
            *,
            template: str,
            version: str,
            config_file: Path | None = None,
        ) -> Path:
            calls.append(
                {
                    "method": "install",
                    "name": name,
                    "template": template,
                    "version": version,
                    "config_file": config_file,
                }
            )
            return Path(name)

    return FakeRepositoryInstaller


def test_new_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only REPOSITORY_NAME given: python/template/version/uv/uvx all take their defaults,
    and RepositoryInstaller.install() is called with them."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.installer.RepositoryInstaller", _fake_repository_installer(calls)
    )

    result = runner.invoke(app, ["new", "my-repo"])

    assert result.exit_code == 0, result.output
    assert "my-repo" in result.output
    assert calls[1] == {
        "method": "install",
        "name": "my-repo",
        "template": "https://github.com/oarepo/nrp-app-copier",
        "version": "rdm-14",
        "config_file": None,
    }


def test_new_passes_all_options(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every option overrides its default and is forwarded to RepositoryInstaller.install()."""
    config_file = tmp_path / "answers.yaml"
    config_file.write_text("repository_name: my-repo\n")

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.installer.RepositoryInstaller", _fake_repository_installer(calls)
    )

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
    assert calls[1] == {
        "method": "install",
        "name": "my-repo",
        "template": "../local-template",
        "version": "rdm-13",
        "config_file": config_file,
    }


def test_new_reports_installer_error_and_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ConfigurationError raised by RepositoryInstaller is reported cleanly, exit code 1."""
    config_file = tmp_path / "answers.yaml"
    config_file.write_text("repository_name: my-repo\n")

    class RaisingRepositoryInstaller:
        def __init__(self, console: ConsoleOutput) -> None:  # noqa: ARG002
            pass

        def install(
            self,
            name: str,  # noqa: ARG002
            *,
            template: str,  # noqa: ARG002
            version: str,  # noqa: ARG002
            config_file: Path | None = None,
        ) -> Path:
            raise ConfigurationError(f"Missing repository config file: {config_file}")

    monkeypatch.setattr("oarepo_cli.cli.installer.RepositoryInstaller", RaisingRepositoryInstaller)

    result = runner.invoke(app, ["new", "my-repo", "--config", str(config_file)])

    assert result.exit_code == 1
    assert "Repository creation failed" in result.output


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
