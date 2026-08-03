# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for `repository local add`/`repository local remove`.

Delegation, argument wiring, and error/exit-code handling are covered here
by mocking `discover_context()`/`LocalPackageManager` (mirroring
test_repository_model.py's approach for the other "thin CLI wrapper over a
service" repository subcommands) -- pyproject.toml read/modify/write
semantics are already covered thoroughly by test_local_packages.py.
`test_local_add_and_remove_against_real_pyproject` and
`test_local_remove_all_against_real_pyproject` additionally drive the full
stack once, end to end, against real pyproject.toml files (with
upgrade_repository mocked out, per test_local_packages.py's own rationale:
no slow external tool involved here to justify a real run).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import pytest
import tomlkit
from typer.testing import CliRunner

from oarepo_cli.cli.main import app
from oarepo_cli.core.config import CliConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.core.errors import ConfigurationError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def mock_context(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Mock discover_context() so no real project is needed."""
    context = Mock()
    monkeypatch.setattr("oarepo_cli.cli.repository.discover_context", lambda: context)
    return context


def _fake_local_package_manager(calls: list[dict[str, object]]) -> type:
    class FakeLocalPackageManager:
        def __init__(self, context: object, *, quiet: bool = False) -> None:
            calls.append({"context": context, "quiet": quiet})
            self._calls = calls

        def add_package(self, path: object) -> None:
            self._calls.append({"method": "add_package", "path": path})

        def remove_package(self, name: str) -> None:
            self._calls.append({"method": "remove_package", "name": name})

        def remove_all_packages(self) -> list[str]:
            self._calls.append({"method": "remove_all_packages"})
            return []

    return FakeLocalPackageManager


def test_local_add_delegates_to_local_package_manager(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`repository local add <path>` constructs a LocalPackageManager and calls add_package()."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.LocalPackageManager", _fake_local_package_manager(calls)
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "local", "add", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert calls[0] == {"context": mock_context, "quiet": False}
    assert calls[1] == {"method": "add_package", "path": tmp_path}


def test_local_add_passes_quiet(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--quiet is forwarded to the LocalPackageManager constructor."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.LocalPackageManager", _fake_local_package_manager(calls)
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "local", "add", str(tmp_path), "--quiet"])

    assert result.exit_code == 0, result.output
    assert calls[0] == {"context": mock_context, "quiet": True}


def test_local_add_reports_error_and_exits_1(
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A ConfigurationError raised by LocalPackageManager is reported cleanly, exit code 1."""

    class RaisingLocalPackageManager:
        def __init__(self, context: object, *, quiet: bool = False) -> None:
            pass

        def add_package(self, path: object) -> None:
            raise ConfigurationError(f"No pyproject.toml in {path}")

    monkeypatch.setattr("oarepo_cli.cli.repository.LocalPackageManager", RaisingLocalPackageManager)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "local", "add", str(tmp_path)])

    assert result.exit_code == 1
    assert "Local package addition failed" in result.output


def test_local_add_reports_context_discovery_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A context-discovery failure (e.g. no pyproject.toml) is reported cleanly, exit code 1."""

    def raise_config_error() -> None:
        raise ConfigurationError("pyproject.toml not found")

    monkeypatch.setattr("oarepo_cli.cli.repository.discover_context", raise_config_error)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "local", "add", "somewhere"])

    assert result.exit_code == 1


def test_local_remove_delegates_to_local_package_manager(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository local remove <name>` constructs a LocalPackageManager and calls
    remove_package()."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.LocalPackageManager", _fake_local_package_manager(calls)
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "local", "remove", "mypkg"])

    assert result.exit_code == 0, result.output
    assert calls[0] == {"context": mock_context, "quiet": False}
    assert calls[1] == {"method": "remove_package", "name": "mypkg"}


def test_local_remove_all_delegates_to_remove_all_packages(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository local remove --all` calls remove_all_packages(), not remove_package()."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.LocalPackageManager", _fake_local_package_manager(calls)
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "local", "remove", "--all"])

    assert result.exit_code == 0, result.output
    assert calls[0] == {"context": mock_context, "quiet": False}
    assert calls[1] == {"method": "remove_all_packages"}


def test_local_remove_neither_name_nor_all_exits_1(
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
) -> None:
    """Neither a name nor --all is an error, not silently a no-op."""
    runner = CliRunner()
    result = runner.invoke(app, ["repository", "local", "remove"])

    assert result.exit_code == 1
    assert "Specify a package name to remove, or --all" in result.output


def test_local_remove_both_name_and_all_exits_1(
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
) -> None:
    """Both a name and --all together is an error, not an implicit choice of one."""
    runner = CliRunner()
    result = runner.invoke(app, ["repository", "local", "remove", "mypkg", "--all"])

    assert result.exit_code == 1
    assert "not both" in result.output


def test_local_remove_reports_error_and_exits_1(
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ConfigurationError raised by LocalPackageManager is reported cleanly, exit code 1."""

    class RaisingLocalPackageManager:
        def __init__(self, context: object, *, quiet: bool = False) -> None:
            pass

        def remove_package(self, name: str) -> None:  # noqa: ARG002
            raise ConfigurationError(f"No local package named '{name}' found in [tool.uv.sources].")

    monkeypatch.setattr("oarepo_cli.cli.repository.LocalPackageManager", RaisingLocalPackageManager)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "local", "remove", "mypkg"])

    assert result.exit_code == 1
    assert "Local package removal failed" in result.output


@pytest.mark.parametrize(
    "args",
    [
        ["repository", "local", "--help"],
        ["repository", "local", "add", "--help"],
        ["repository", "local", "remove", "--help"],
    ],
)
def test_local_help_text(args: list[str]) -> None:
    """--help works for the local group and both subcommands, without a real project."""
    runner = CliRunner()
    result = runner.invoke(app, args)

    assert result.exit_code == 0, result.output
    assert "[tool.uv.sources]" in result.output


def make_context(root: Path) -> ProjectContext:
    return ProjectContext(
        root_directory=root,
        pyproject_path=root / "pyproject.toml",
        venv_path=root / ".venv",
        python_binary=root / ".venv" / "bin" / "python",
        oarepo_version=14,
        config=CliConfig(),
    )


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "myrepo"\ndependencies = ["oarepo>=14.0.0,<15.0.0"]\n'
    )
    return root


def make_local_package(tmp_path: Path, name: str) -> Path:
    pkg_dir = tmp_path / name
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n')
    return pkg_dir


@pytest.fixture
def mock_upgrade(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Mock services.local_packages.upgrade_repository, recording calls."""
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "oarepo_cli.services.local_packages.upgrade_repository",
        lambda context, **kwargs: calls.append({"context": context, **kwargs}),
    )
    return calls


def test_local_add_and_remove_against_real_pyproject(
    repo_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_upgrade: list[dict[str, Any]],
) -> None:
    """End-to-end: `repository local add`/`remove` are wired correctly through to a real,
    on-disk pyproject.toml, via the real LocalPackageManager."""
    context = make_context(repo_root)
    monkeypatch.setattr("oarepo_cli.cli.repository.discover_context", lambda: context)
    package_dir = make_local_package(tmp_path, "mypkg")

    runner = CliRunner()
    add_result = runner.invoke(
        app, ["repository", "local", "add", str(package_dir), "--quiet"], catch_exceptions=False
    )
    assert add_result.exit_code == 0, add_result.output

    document = tomlkit.parse(context.pyproject_path.read_text())
    assert "mypkg" in document["project"]["dependencies"]
    assert "mypkg" in document["tool"]["uv"]["sources"]

    remove_result = runner.invoke(
        app, ["repository", "local", "remove", "mypkg", "--quiet"], catch_exceptions=False
    )
    assert remove_result.exit_code == 0, remove_result.output

    document = tomlkit.parse(context.pyproject_path.read_text())
    assert "mypkg" not in document["project"]["dependencies"]

    assert len(mock_upgrade) == 2


def test_local_remove_all_against_real_pyproject(
    repo_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_upgrade: list[dict[str, Any]],
) -> None:
    """End-to-end: `repository local remove --all` removes every local package in one go,
    leaving unrelated [tool.uv.sources] entries (e.g. an index override) untouched."""
    context = make_context(repo_root)
    monkeypatch.setattr("oarepo_cli.cli.repository.discover_context", lambda: context)

    document = tomlkit.parse(context.pyproject_path.read_text())
    tool = document.setdefault("tool", tomlkit.table())
    uv = tool.setdefault("uv", tomlkit.table())
    sources = uv.setdefault("sources", tomlkit.table())
    sources["invenio-cli"] = {"index": "cesnet"}
    context.pyproject_path.write_text(tomlkit.dumps(document))

    runner = CliRunner()
    for name in ("pkg-a", "pkg-b"):
        package_dir = make_local_package(tmp_path, name)
        result = runner.invoke(
            app, ["repository", "local", "add", str(package_dir), "--quiet"], catch_exceptions=False
        )
        assert result.exit_code == 0, result.output

    mock_upgrade.clear()

    remove_result = runner.invoke(
        app, ["repository", "local", "remove", "--all", "--quiet"], catch_exceptions=False
    )
    assert remove_result.exit_code == 0, remove_result.output

    document = tomlkit.parse(context.pyproject_path.read_text())
    assert "pkg-a" not in document["project"]["dependencies"]
    assert "pkg-b" not in document["project"]["dependencies"]
    assert "invenio-cli" in document["tool"]["uv"]["sources"]
    assert "pkg-a" not in document["tool"]["uv"]["sources"]
    assert "pkg-b" not in document["tool"]["uv"]["sources"]

    assert len(mock_upgrade) == 1
