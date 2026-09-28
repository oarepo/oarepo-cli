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
from oarepo_cli.core.errors import ConfigurationError
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


def test_run_docs_stages_docs_build(mock_context: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test staging: docs/ untouched, docs-build holds user+generated pages, nav correct."""
    root = mock_context.root_directory
    (root / "README.md").write_text("# My Lib\n\nHome content. See [license](LICENSE) and [x](#a--b).\n")
    (root / "CONTRIBUTING.md").write_text("# How to contribute\n")
    (root / "LICENSE").write_text("MIT license text\n")

    docs_source = root / "docs"
    docs_source.mkdir()
    (docs_source / "guide.md").write_text("# Guide\n")
    package = root / "test_lib"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "mod.py").write_text("")

    monkeypatch.setenv("CI", "true")
    run_calls: list[list[str]] = []
    monkeypatch.setattr("oarepo_cli.services.docs.process.run", _fake_run_factory(run_calls))

    result = docs.run_docs(mock_context, quiet=True)

    assert result.success

    # docs/ untouched; everything staged in docs-build/
    assert (docs_source / "guide.md").read_text() == "# Guide\n"
    build = root / "docs-build"
    assert "# Guide" in (build / "guide.md").read_text()
    index_content = (build / "index.md").read_text()
    assert "Home content." in index_content
    assert "](license.md)" in index_content  # root-file link rewritten
    assert "](#a-b)" in index_content  # GitHub anchor collapsed to zensical slug
    assert "How to contribute" in (build / "contributing.md").read_text()
    assert "MIT license text" in (build / "license.md").read_text()
    assert "# test_lib.mod" in (build / "reference" / "mod.md").read_text()
    assert "summary:\n        modules: true" in (build / "reference" / "index.md").read_text()
    assert not (build / "reference" / "index.md").read_text().startswith("# Guide")

    # Nav: built-ins, then discovered extras, then API section
    mkdocs_yml = (root / "mkdocs.yml").read_text()
    assert "docs_dir: docs-build" in mkdocs_yml
    nav_block = mkdocs_yml.split("nav:\n", 1)[1].split("plugins:", 1)[0]
    assert nav_block == (
        "  - Home: index.md\n"
        "  - Contributing: contributing.md\n"
        "  - License: license.md\n"
        "  - Guide: guide.md\n"
        "  - API docs:\n"
        "    - test_lib: reference/index.md\n"
        "    - test_lib.mod: reference/mod.md\n"
    )

    # Generated dirs gitignored; builds invoked; no browser in CI
    assert "/docs-build/" in (root / ".gitignore").read_text()
    assert [call[1] for call in run_calls] == ["remote", "build", "build"]


def test_run_docs_pages_json_overrides_and_orders(mock_context: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test pages.json: built-in override, extra page ordering, no copies for overridden slots."""
    root = mock_context.root_directory
    (root / "README.md").write_text("# readme should NOT become a page\n")
    (root / "CONTRIBUTING.md").write_text("# contributing guide\n")

    docs_source = root / "docs"
    docs_source.mkdir()
    (docs_source / "intro.md").write_text("# Intro\n")
    (docs_source / "howto.md").write_text("# How To\n")
    (docs_source / "pages.json").write_text(
        '{"pages": [\n  {"title": "Guide", "file": "howto.md"},\n  {"title": "Home", "file": "intro.md"}\n]}\n'
    )

    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr("oarepo_cli.services.docs.process.run", _fake_run_factory([]))

    docs.run_docs(mock_context, quiet=True)

    build = root / "docs-build"
    # Home overridden by intro.md: README copy not produced, intro used in place
    assert (build / "intro.md").read_text() == "# Intro\n"
    assert not (build / "index.md").exists()
    # Contributing not mentioned in pages.json: copied per default rules
    assert "contributing guide" in (build / "contributing.md").read_text()
    # pages.json is not a page
    assert not (build / "pages.json").exists()

    mkdocs_yml = (root / "mkdocs.yml").read_text()
    nav_block = mkdocs_yml.split("nav:\n", 1)[1].split("plugins:", 1)[0]
    # pages.json order honored (Guide before Home); the unmentioned
    # Contributing built-in is appended after json entries
    assert nav_block == (
        "  - Guide: howto.md\n  - Home: intro.md\n  - Contributing: contributing.md\n  - API docs: reference/index.md\n"
    ), nav_block


def test_run_docs_pages_json_errors(mock_context: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test malformed pages.json fails with a clear error."""
    root = mock_context.root_directory
    docs_source = root / "docs"
    docs_source.mkdir()
    (docs_source / "pages.json").write_text('{"pages": [{"title": "Home", "file": "missing.md"}]}')

    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr("oarepo_cli.services.docs.process.run", _fake_run_factory([]))

    with pytest.raises(ConfigurationError, match=r"missing\.md"):
        docs.run_docs(mock_context, quiet=True)


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

    assert "# test_lib.core" in (root / "docs-build" / "reference" / "core.md").read_text()
    mkdocs_yml = (root / "mkdocs.yml").read_text()
    assert "- src" in mkdocs_yml
    assert 'site_url: "https://oarepo.github.io/test-lib/"' in mkdocs_yml


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
