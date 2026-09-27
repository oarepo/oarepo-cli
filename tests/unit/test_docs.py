# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Unit tests for the docs service module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services import docs, process


@pytest.fixture
def mock_context(tmp_path: Path) -> Mock:
    """Create a mock ProjectContext with a minimal pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test-lib"\n')
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path
    context.pyproject_path = tmp_path / "pyproject.toml"
    return context


def _fake_run_factory(run_calls: list[list[str]]) -> Mock:
    def fake_run(command: list[str], **kwargs: object) -> Mock:
        run_calls.append(list(command))
        result = Mock(spec=process.ProcessResult)
        result.success = True
        result.return_code = 0
        result.stdout = ""  # no git remote in the fixture -> fallback site_url
        return result

    return fake_run


def test_run_docs_uses_readme_optional_pages_and_module_tree(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test home page from README, optional pages, per-module API pages, and CI browser skip."""
    root = mock_context.root_directory
    (root / "README.md").write_text("# My Lib\n\nHello from the readme.\n")
    (root / "CONTRIBUTING.md").write_text("# How to contribute\n")
    (root / "LICENSE").write_text("MIT license text\n")

    package = root / "test_lib"
    (package / "sub").mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "mod.py").write_text("")
    (package / "_priv.py").write_text("")
    (package / "sub" / "__init__.py").write_text("")
    (package / "sub" / "deep.py").write_text("")

    monkeypatch.setenv("CI", "true")
    run_calls: list[list[str]] = []
    monkeypatch.setattr("oarepo_cli.services.docs.process.run", _fake_run_factory(run_calls))

    result = docs.run_docs(mock_context, quiet=True)

    assert result.success

    # README is the home page; contributing/license pages copied from root
    assert "Hello from the readme." in (root / "docs" / "index.md").read_text()
    assert "How to contribute" in (root / "docs" / "contributing.md").read_text()
    assert "MIT license text" in (root / "docs" / "license.md").read_text()

    # One API page per module, mirroring the package layout; private skipped
    reference = root / "docs" / "reference"
    assert "::: test_lib" in (reference / "index.md").read_text()
    assert "# test_lib.mod" in (reference / "mod.md").read_text()
    assert "# test_lib.sub" in (reference / "sub" / "index.md").read_text()
    assert "# test_lib.sub.deep" in (reference / "sub" / "deep.md").read_text()
    assert not (reference / "_priv.md").exists()
    assert "show_submodules: false" in (reference / "index.md").read_text()

    # Nav: top-level pages flat, API docs section with one entry per module
    mkdocs_yml = (root / "mkdocs.yml").read_text()
    nav_block = mkdocs_yml.split("nav:\n", 1)[1].split("plugins:", 1)[0]
    assert nav_block == (
        "  - Home: index.md\n"
        "  - Contribution: contributing.md\n"
        "  - License: license.md\n"
        "  - API docs:\n"
        "    - test_lib: reference/index.md\n"
        "    - test_lib.mod: reference/mod.md\n"
        "    - test_lib.sub: reference/sub/index.md\n"
        "    - test_lib.sub.deep: reference/sub/deep.md\n"
    )

    # Generated paths are gitignored
    gitignore = (root / ".gitignore").read_text()
    assert "/docs/" in gitignore
    assert "/mkdocs.yml" in gitignore

    # git remote lookup, zensical build, then plain-mkdocs build for llms.txt;
    # no browser in CI
    assert run_calls[0][:2] == ["git", "remote"]
    assert [call[1:3] for call in run_calls[1:]] == [["build", "--clean"], ["build", "--clean"]]
    assert run_calls[2][3:] == ["-d", ".tmp-mkdocs"]
    # site_url falls back to the oarepo org when no git remote is configured
    assert 'site_url: "https://oarepo.github.io/test-lib/"' in mkdocs_yml
    assert "llmstxt" in mkdocs_yml
    assert len(run_calls) == 3

    # Second run after removing a module and CONTRIBUTING.md: stale pages
    # gone, nav regenerated, .gitignore untouched
    (package / "mod.py").unlink()
    (root / "CONTRIBUTING.md").unlink()
    gitignore_before = (root / ".gitignore").read_text()
    run_calls.clear()
    docs.run_docs(mock_context, quiet=True)

    assert not (root / "docs" / "reference" / "mod.md").exists()
    assert not (root / "docs" / "contributing.md").exists()
    mkdocs_yml = (root / "mkdocs.yml").read_text()
    assert "test_lib.mod" not in mkdocs_yml
    assert "Contribution" not in mkdocs_yml
    assert (root / ".gitignore").read_text() == gitignore_before
    assert len(run_calls) == 3


def test_run_docs_fallback_without_readme_or_package(mock_context: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test a project without README.md/package dir: generated home page, single API page."""
    root = mock_context.root_directory

    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr("oarepo_cli.services.docs.process.run", _fake_run_factory([]))

    docs.run_docs(mock_context, quiet=True)

    assert "# OARepo API Reference" in (root / "docs" / "index.md").read_text()
    mkdocs_yml = (root / "mkdocs.yml").read_text()
    assert "  - Home: index.md\n  - API docs: reference/index.md\n" in mkdocs_yml
    assert "- ." in mkdocs_yml  # flat layout: no src/ directory in fixture
    assert "::: test_lib" in (root / "docs" / "reference" / "index.md").read_text()


@pytest.mark.parametrize(
    ("remote_url", "expected"),
    [
        ("git@github.com:nrp-cz/some-repo.git\n", "https://nrp-cz.github.io/some-repo/"),
        ("https://github.com/eosc-cz/other-repo\n", "https://eosc-cz.github.io/other-repo/"),
        ("https://github.com/eosc-cz/other-repo.git\n", "https://eosc-cz.github.io/other-repo/"),
    ],
)
def test_site_url_from_github_remote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, remote_url: str, expected: str
) -> None:
    """GitHub origin remotes (ssh + https) map to <org>.github.io/<repo>."""

    def fake_run(command: list[str], **kwargs: object) -> Mock:
        result = Mock(spec=process.ProcessResult)
        result.success = True
        result.stdout = remote_url
        return result

    monkeypatch.setattr("oarepo_cli.services.docs.process.run", fake_run)

    assert docs._site_url(tmp_path, "fallback") == expected


def test_site_url_fallback_without_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No git remote -> oarepo org + pyproject name."""

    def fake_run(command: list[str], **kwargs: object) -> Mock:
        result = Mock(spec=process.ProcessResult)
        result.success = False
        result.stdout = ""
        return result

    monkeypatch.setattr("oarepo_cli.services.docs.process.run", fake_run)

    assert docs._site_url(tmp_path, "my-lib") == "https://oarepo.github.io/my-lib/"


def test_run_docs_src_layout_package(mock_context: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that packages under src/ are found and mkdocstrings points at src."""
    root = mock_context.root_directory
    package = root / "src" / "test_lib"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "core.py").write_text("")

    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr("oarepo_cli.services.docs.process.run", _fake_run_factory([]))

    docs.run_docs(mock_context, quiet=True)

    assert "# test_lib.core" in (root / "docs" / "reference" / "core.md").read_text()
    assert "- src" in (root / "mkdocs.yml").read_text()
