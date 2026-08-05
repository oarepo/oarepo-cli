# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for LocalPackageManager, against real pyproject.toml files.

LocalPackageManager only ever touches a project's pyproject.toml (via
tomlkit) and, on success, calls services.repository.upgrade_repository --
there's no slow external tool (uv, copier, invenio-cli) to run for real
here, so these tests exercise the real tomlkit read/modify/write path
against real tmp_path files and mock out upgrade_repository (a venv-wipe +
reinstall cycle -- with the uv cache clean step skipped here via
clean_cache=False, already covered end to end by
test_repository_upgrade.py), per AGENTS.md's guidance to fake slow external
tools rather than re-run them at this layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import tomlkit

from oarepo_cli.core.config import CliConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.core.errors import ConfigurationError
from oarepo_cli.services.local_packages import LocalPackageManager
from oarepo_cli.ui import ConsoleOutput

if TYPE_CHECKING:
    from pathlib import Path

ROOT_PYPROJECT = """\
# Root project pyproject.toml, hand-commented.
[project]
name = "myrepo"
dependencies = [
    "oarepo>=14.0.0,<15.0.0",
]
requires-python = ">=3.14,<3.15"

[tool.uv.index]
name = "cesnet"
"""


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
    """A repository root with a real, hand-commented pyproject.toml."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text(ROOT_PYPROJECT)
    return root


def make_local_package(tmp_path: Path, name: str, dirname: str | None = None) -> Path:
    """A minimal local package directory with its own pyproject.toml."""
    pkg_dir = tmp_path / (dirname or name)
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


def test_add_package_writes_sources_and_dependency(
    repo_root: Path,
    tmp_path: Path,
    mock_upgrade: list[dict[str, Any]],  # noqa: ARG001 -- fixture prevents a real upgrade
) -> None:
    """add_package() adds a [tool.uv.sources] entry and a dependencies entry."""
    package_dir = make_local_package(tmp_path, "mypkg")
    context = make_context(repo_root)
    manager = LocalPackageManager(context, ConsoleOutput(quiet=True))

    manager.add_package(package_dir)

    document = tomlkit.parse(context.pyproject_path.read_text())
    assert "mypkg" in document["project"]["dependencies"]
    source = document["tool"]["uv"]["sources"]["mypkg"]
    assert source["path"] == "../mypkg"
    assert source["editable"] is True


def test_add_package_triggers_repository_upgrade(
    repo_root: Path, tmp_path: Path, mock_upgrade: list[dict[str, Any]]
) -> None:
    """add_package() unconditionally triggers upgrade_repository, unlike
    ModelManager.create_model()'s conditional reinstall."""
    package_dir = make_local_package(tmp_path, "mypkg")
    context = make_context(repo_root)
    manager = LocalPackageManager(context, ConsoleOutput(quiet=True))

    manager.add_package(package_dir)

    assert len(mock_upgrade) == 1
    assert mock_upgrade[0] == {"context": context, "quiet": True, "clean_cache": False}


def test_add_package_missing_pyproject_raises(
    repo_root: Path, tmp_path: Path, mock_upgrade: list[dict[str, Any]]
) -> None:
    """A path without its own pyproject.toml raises ConfigurationError before any write."""
    context = make_context(repo_root)
    manager = LocalPackageManager(context, ConsoleOutput(quiet=True))
    original_content = context.pyproject_path.read_text()

    with pytest.raises(ConfigurationError, match="No pyproject.toml in"):
        manager.add_package(tmp_path / "does-not-exist")

    assert context.pyproject_path.read_text() == original_content
    assert mock_upgrade == []


def test_add_package_is_idempotent_on_dependencies(
    repo_root: Path,
    tmp_path: Path,
    mock_upgrade: list[dict[str, Any]],  # noqa: ARG001 -- fixture prevents a real upgrade
) -> None:
    """Adding the same package twice doesn't duplicate its dependencies entry."""
    package_dir = make_local_package(tmp_path, "mypkg")
    context = make_context(repo_root)
    manager = LocalPackageManager(context, ConsoleOutput(quiet=True))

    manager.add_package(package_dir)
    manager.add_package(package_dir)

    document = tomlkit.parse(context.pyproject_path.read_text())
    dependencies = list(document["project"]["dependencies"])
    assert dependencies.count("mypkg") == 1


def test_add_package_normalizes_name(
    repo_root: Path,
    tmp_path: Path,
    mock_upgrade: list[dict[str, Any]],  # noqa: ARG001 -- fixture prevents a real upgrade
) -> None:
    """The package's [project].name is canonicalized (PEP 503), matching uv's own behavior."""
    package_dir = make_local_package(tmp_path, "My_Package", dirname="my_package")
    context = make_context(repo_root)
    manager = LocalPackageManager(context, ConsoleOutput(quiet=True))

    manager.add_package(package_dir)

    document = tomlkit.parse(context.pyproject_path.read_text())
    assert "my-package" in document["project"]["dependencies"]
    assert "my-package" in document["tool"]["uv"]["sources"]


def test_add_package_path_relative_to_root_outside_root(
    repo_root: Path,
    tmp_path: Path,
    mock_upgrade: list[dict[str, Any]],  # noqa: ARG001 -- fixture prevents a real upgrade
) -> None:
    """A package living outside the project root gets a walk_up-relative path."""
    sibling_root = tmp_path / "siblings"
    sibling_root.mkdir()
    package_dir = make_local_package(sibling_root, "mypkg")
    context = make_context(repo_root)
    manager = LocalPackageManager(context, ConsoleOutput(quiet=True))

    manager.add_package(package_dir)

    document = tomlkit.parse(context.pyproject_path.read_text())
    source_path = document["tool"]["uv"]["sources"]["mypkg"]["path"]
    assert (repo_root / source_path).resolve() == package_dir.resolve()


def test_add_package_preserves_existing_formatting(
    repo_root: Path,
    tmp_path: Path,
    mock_upgrade: list[dict[str, Any]],  # noqa: ARG001 -- fixture prevents a real upgrade
) -> None:
    """Existing comments/tables in pyproject.toml survive the tomlkit round trip."""
    package_dir = make_local_package(tmp_path, "mypkg")
    context = make_context(repo_root)
    manager = LocalPackageManager(context, ConsoleOutput(quiet=True))

    manager.add_package(package_dir)

    content = context.pyproject_path.read_text()
    assert "# Root project pyproject.toml, hand-commented." in content
    assert '[tool.uv.index]\nname = "cesnet"' in content


def _add_local_source(pyproject_path: Path, name: str, path: str) -> None:
    document = tomlkit.parse(pyproject_path.read_text())
    document["project"]["dependencies"].append(name)
    tool = document.setdefault("tool", tomlkit.table())
    uv = tool.setdefault("uv", tomlkit.table())
    sources = uv.setdefault("sources", tomlkit.table())
    source = tomlkit.inline_table()
    source["path"] = path
    source["editable"] = True
    sources[name] = source
    pyproject_path.write_text(tomlkit.dumps(document))


def test_remove_package_removes_sources_and_dependency(
    repo_root: Path,
    mock_upgrade: list[dict[str, Any]],  # noqa: ARG001 -- fixture prevents a real upgrade
) -> None:
    """remove_package() removes both the [tool.uv.sources] entry and the dependency."""
    _add_local_source(repo_root / "pyproject.toml", "mypkg", "../mypkg")
    context = make_context(repo_root)
    manager = LocalPackageManager(context, ConsoleOutput(quiet=True))

    manager.remove_package("mypkg")

    document = tomlkit.parse(context.pyproject_path.read_text())
    assert "mypkg" not in document["project"]["dependencies"]
    assert "tool" not in document or "sources" not in document.get("tool", {}).get("uv", {})


def test_remove_package_triggers_repository_upgrade(
    repo_root: Path, mock_upgrade: list[dict[str, Any]]
) -> None:
    """remove_package() also unconditionally triggers upgrade_repository."""
    _add_local_source(repo_root / "pyproject.toml", "mypkg", "../mypkg")
    context = make_context(repo_root)
    manager = LocalPackageManager(context, ConsoleOutput(quiet=True))

    manager.remove_package("mypkg")

    assert mock_upgrade == [{"context": context, "quiet": True, "clean_cache": False}]


def test_remove_package_leaves_other_sources_untouched(
    repo_root: Path,
    mock_upgrade: list[dict[str, Any]],  # noqa: ARG001 -- fixture prevents a real upgrade
) -> None:
    """Removing one local package doesn't disturb other [tool.uv.sources] entries."""
    _add_local_source(repo_root / "pyproject.toml", "mypkg", "../mypkg")
    _add_local_source(repo_root / "pyproject.toml", "otherpkg", "../otherpkg")
    context = make_context(repo_root)
    manager = LocalPackageManager(context, ConsoleOutput(quiet=True))

    manager.remove_package("mypkg")

    document = tomlkit.parse(context.pyproject_path.read_text())
    assert "otherpkg" in document["project"]["dependencies"]
    assert "otherpkg" in document["tool"]["uv"]["sources"]
    assert "mypkg" not in document["tool"]["uv"]["sources"]


def test_remove_package_normalizes_name(
    repo_root: Path,
    mock_upgrade: list[dict[str, Any]],  # noqa: ARG001 -- fixture prevents a real upgrade
) -> None:
    """remove_package() canonicalizes its name argument the same way add_package() does."""
    _add_local_source(repo_root / "pyproject.toml", "my-package", "../my_package")
    context = make_context(repo_root)
    manager = LocalPackageManager(context, ConsoleOutput(quiet=True))

    manager.remove_package("My_Package")

    document = tomlkit.parse(context.pyproject_path.read_text())
    assert "my-package" not in document["project"]["dependencies"]


def test_remove_package_unknown_name_raises(
    repo_root: Path, mock_upgrade: list[dict[str, Any]]
) -> None:
    """Removing a package that was never added raises ConfigurationError, no write attempted."""
    context = make_context(repo_root)
    manager = LocalPackageManager(context, ConsoleOutput(quiet=True))
    original_content = context.pyproject_path.read_text()

    with pytest.raises(ConfigurationError, match="No local package named 'mypkg'"):
        manager.remove_package("mypkg")

    assert context.pyproject_path.read_text() == original_content
    assert mock_upgrade == []


def test_remove_package_upgrade_false_skips_upgrade(
    repo_root: Path, mock_upgrade: list[dict[str, Any]]
) -> None:
    """remove_package(upgrade=False) still removes the entries, but doesn't upgrade."""
    _add_local_source(repo_root / "pyproject.toml", "mypkg", "../mypkg")
    context = make_context(repo_root)
    manager = LocalPackageManager(context, ConsoleOutput(quiet=True))

    manager.remove_package("mypkg", upgrade=False)

    document = tomlkit.parse(context.pyproject_path.read_text())
    assert "mypkg" not in document["project"]["dependencies"]
    assert mock_upgrade == []


def test_list_local_packages_excludes_non_path_sources(
    repo_root: Path,
    tmp_path: Path,
    mock_upgrade: list[dict[str, Any]],  # noqa: ARG001 -- fixture prevents a real upgrade
) -> None:
    """list_local_packages() only returns [tool.uv.sources] entries with a path key,
    excluding e.g. an index-based override like invenio-cli's CESNET registry pin."""
    document = tomlkit.parse((repo_root / "pyproject.toml").read_text())
    tool = document.setdefault("tool", tomlkit.table())
    uv = tool.setdefault("uv", tomlkit.table())
    sources = uv.setdefault("sources", tomlkit.table())
    sources["invenio-cli"] = {"index": "cesnet"}
    (repo_root / "pyproject.toml").write_text(tomlkit.dumps(document))

    context = make_context(repo_root)
    manager = LocalPackageManager(context, ConsoleOutput(quiet=True))
    manager.add_package(make_local_package(tmp_path, "mypkg"))

    names = manager.list_local_packages()

    assert names == ["mypkg"]


def test_remove_all_packages_removes_everything_in_one_upgrade(
    repo_root: Path, mock_upgrade: list[dict[str, Any]]
) -> None:
    """remove_all_packages() removes every local source and triggers exactly one upgrade,
    regardless of how many packages were removed."""
    _add_local_source(repo_root / "pyproject.toml", "pkg-a", "../pkg-a")
    _add_local_source(repo_root / "pyproject.toml", "pkg-b", "../pkg-b")
    context = make_context(repo_root)
    manager = LocalPackageManager(context, ConsoleOutput(quiet=True))

    removed = manager.remove_all_packages()

    assert sorted(removed) == ["pkg-a", "pkg-b"]
    document = tomlkit.parse(context.pyproject_path.read_text())
    assert "pkg-a" not in document["project"]["dependencies"]
    assert "pkg-b" not in document["project"]["dependencies"]
    assert "tool" not in document or "sources" not in document.get("tool", {}).get("uv", {})
    assert len(mock_upgrade) == 1


def test_remove_all_packages_with_none_present_skips_upgrade(
    repo_root: Path, mock_upgrade: list[dict[str, Any]]
) -> None:
    """remove_all_packages() is a no-op (no upgrade triggered) when there's nothing to remove."""
    context = make_context(repo_root)
    manager = LocalPackageManager(context, ConsoleOutput(quiet=True))

    removed = manager.remove_all_packages()

    assert removed == []
    assert mock_upgrade == []
