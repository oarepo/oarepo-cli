# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Mkdocs documentation scaffolding and build for OARepo library projects."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from oarepo_cli.core.context import ProjectContext

from oarepo_cli.configuration import resources
from oarepo_cli.core.errors import ConfigurationError
from oarepo_cli.services import process
from oarepo_cli.services.process import ProcessOutputMode
from oarepo_cli.services.pyproject_reader import PyProjectReader


class _PageEntry(TypedDict):
    """One entry of docs/pages.json: a nav title and its page location."""

    title: str
    file: str


# Markdown link targets that live in the repo root but get copied to a
# differently-named docs page: [x](LICENSE) works on the GitHub repo view
# but is a dead link in the built site, where only the generated page
# (license.md, which mkdocs rewrites to license.html) exists.
_PAGE_LINK_REWRITES = {
    "LICENSE": "license.md",
    "LICENSE.md": "license.md",
    "CONTRIBUTING.md": "contributing.md",
}


def _rewrite_page_links(content: str) -> str:
    """Rewrite links in a copied root document so they keep working in the built docs.

    Two kinds of links written for the GitHub repo view break differently
    on the rendered site:

    - links to repo-root files (``[x](LICENSE)``) have no build counterpart
      until pointed at the generated page (``license.md``)
    - same-page anchors follow GitHub's slugification, which keeps runs of
      ``--`` for headings like ``a / b``; zensical collapses each run into a
      single ``-``, so every GitHub-style ``#foo--bar`` anchor is missing in
      the built page unless collapsed the same way
    """
    for target, replacement in _PAGE_LINK_REWRITES.items():
        content = re.sub(rf"\]\({re.escape(target)}(#[^)]+)?\)", rf"]({replacement}\1)", content)
    return re.sub(r"\]\(#[^)]*\)", _collapse_slug_hyphens, content)


def _collapse_slug_hyphens(match: re.Match[str]) -> str:
    """Collapse runs of hyphens in one ``](#anchor)`` match, GitHub -> zensical slug."""
    return re.sub(r"-{2,}", "-", match.group(0))


def _render_docs_index_fallback(site_name: str, package_name: str) -> str:
    """Render the fallback home page for projects without a README.md."""
    return (
        resources.read_text("docs-index.md.tmpl")
        .replace("@@SITE_NAME@@", site_name)
        .replace("@@PACKAGE_NAME@@", package_name)
    )


def _render_reference_index(module_path: str, *, module_summary: bool = False) -> str:
    """Render one API reference page for a module from the bundled template.

    Args:
        module_path: Dotted path of the module to document
        module_summary: If True, also render a summary table of submodules
            (used for package/index pages)

    """
    return (
        resources.read_text("docs-reference-index.md.tmpl")
        .replace("@@PACKAGE_NAME@@", module_path)
        .replace("@@MODULE_SUMMARY@@", "\n      summary:\n        modules: true" if module_summary else "")
    )


def _site_url(root: Path, project_name: str) -> str:
    """Derive the GitHub Pages URL from the project's git remote.

    Parses the ``origin`` remote (e.g. ``git@github.com:nrp-cz/some-repo.git``
    or ``https://github.com/eosc-cz/some-repo``) so docs deploy under
    ``https://<org>.github.io/<repo>/`` for any GitHub organization, not
    just ``oarepo``. Falls back to the project name in the ``oarepo`` org
    when there is no GitHub remote.

    Args:
        root: Project root directory
        project_name: [project].name from pyproject.toml (fallback repo name)

    Returns:
        Absolute GitHub Pages URL with a trailing slash

    """
    org, repo = "oarepo", project_name
    result = process.run(["git", "remote", "get-url", "origin"], cwd=root, check=False)
    if result.success and (match := re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", result.stdout.strip())):
        org, repo = match.groups()
    return f"https://{org}.github.io/{repo}/"


def _render_mkdocs_yml(site_name: str, site_url: str, mkdocstrings_path: str, nav: str, llmstxt_sections: str) -> str:
    """Render mkdocs.yml from the bundled template."""
    return (
        resources.read_text("mkdocs.yml.tmpl")
        .replace("@@SITE_NAME@@", site_name)
        .replace("@@SITE_URL@@", site_url)
        .replace("@@MKDOCSTRINGS_PATH@@", mkdocstrings_path)
        .replace("@@NAV@@", nav)
        .replace("@@LLMSTXT_SECTIONS@@", llmstxt_sections)
    )


def _cli_tool_path(name: str) -> str:
    """Resolve a tool binary installed alongside oarepo-cli.

    Args:
        name: Console script name (e.g. "zensical")

    Returns:
        Absolute path to the binary if found next to the current
        interpreter, otherwise the bare name (resolved via PATH).

    """
    candidate = Path(sys.executable).parent / name
    return str(candidate) if candidate.exists() else name


def _is_ci() -> bool:
    """Detect CI environment via the conventional CI env var.

    Returns:
        True if the CI environment variable is set to a truthy value

    """
    return os.environ.get("CI", "").lower() not in ("", "0", "false", "no")


def _api_doc_pages(root: Path, package_name: str, docs_dir: Path) -> tuple[dict[Path, str], list[tuple[str, str]]]:
    """Generate one API page per Python module of the package.

    Pages mirror the package's directory layout under docs/reference/ (a
    module ``pkg.sub.mod`` gets ``reference/sub/mod.md``) so the nav reads
    like the source tree instead of inlining every class/function into a
    single page. Private members (``_``-prefixed, except ``__init__.py``)
    get no page. A project whose package directory can't be found falls back
    to a single ``::: <package>`` page.

    Args:
        root: Project root directory
        package_name: Import name of the top-level package
        docs_dir: Target docs directory

    Returns:
        Tuple of (page files to write, nav entries as (title, docs-relative
        page) pairs, package landing page first)

    """
    package_root = root / "src" / package_name
    if not package_root.is_dir():
        package_root = root / package_name
    if not package_root.is_dir():
        return {docs_dir / "reference" / "index.md": _render_reference_index(package_name)}, [
            (package_name, "reference/index.md")
        ]

    files: dict[Path, str] = {}
    nav: list[tuple[str, str]] = []
    for py_file in sorted(package_root.rglob("*.py")):
        parts = py_file.relative_to(package_root).with_suffix("").parts
        if any(part.startswith("_") and part != "__init__" for part in parts):
            continue  # private modules and __pycache__ get no docs page

        if py_file.name == "__init__.py":
            module_parts = parts[:-1]
            page = Path("reference", *module_parts, "index.md")
            dotted = ".".join((package_name, *module_parts))
            # Package pages list their submodules as a summary table
            # (summary.modules), replacing the old show_submodules inlining.
            files[docs_dir / page] = _render_reference_index(dotted, module_summary=True)
        else:
            page = Path("reference", *parts).with_suffix(".md")
            dotted = ".".join((package_name, *parts))
            files[docs_dir / page] = _render_reference_index(dotted)
        nav.append((dotted, page.as_posix()))

    if not files:
        # Namespace package without any .py files -- still need a landing page
        files[docs_dir / "reference" / "index.md"] = _render_reference_index(package_name)
        nav.append((package_name, "reference/index.md"))

    return files, nav


_BUILTIN_TITLES = ("Home", "Contributing", "License")
_PAGES_JSON = "pages.json"
_SITE_NAME = "OARepo API Reference"


def _load_pages_json(docs_source_dir: Path) -> list[_PageEntry]:
    """Load nav overrides/additions from the user-authored docs/pages.json.

    Schema:
        {"pages": [{"title": "Home", "file": "index.md"}, ...]}

    Built-in titles (Home/Contributing/License) override the otherwise
    generated copies; any other title adds an extra nav page. Files are
    paths relative to docs/ and must exist there.

    Args:
        docs_source_dir: The user-authored docs/ directory

    Returns:
        List of page entries in file order; empty when no pages.json exists

    Raises:
        ConfigurationError: On malformed JSON, wrong keys, or a file not
            found inside docs/

    """
    pages_file = docs_source_dir / _PAGES_JSON
    if not pages_file.exists():
        return []

    try:
        data = json.loads(pages_file.read_text(encoding="utf-8"))
        entries = data["pages"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ConfigurationError(
            f'Invalid {_PAGES_JSON}: expected an object with a "pages" list of {{"title", "file"}} entries ({e})'
        ) from e

    pages: list[_PageEntry] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict) or "title" not in entry or "file" not in entry:
            raise ConfigurationError(f"Invalid {_PAGES_JSON} entry #{i + 1}: needs both 'title' and 'file' keys")
        file = entry["file"]
        if not (docs_source_dir / file).is_file():
            raise ConfigurationError(
                f"{docs_source_dir / file} not found (from {_PAGES_JSON} entry '{entry['title']}')"
            )
        pages.append({"title": entry["title"], "file": file})
    return pages


def _render_nav(pages: list[tuple[str, str]], api_children: list[tuple[str, str]]) -> str:
    """Render the mkdocs nav block.

    Args:
        pages: Top-level pages as (title, page) pairs before the API section
        api_children: API pages as (dotted module title, page) pairs;
            collapsed into a single "API docs" entry when there is only one

    Returns:
        Indented nav lines ready to substitute into mkdocs.yml.tmpl

    """
    lines = [f"  - {title}: {page}" for title, page in pages]
    if len(api_children) == 1:
        lines.append(f"  - API docs: {api_children[0][1]}")
    else:
        lines.append("  - API docs:")
        lines.extend(f"    - {title}: {page}" for title, page in api_children)
    return "\n".join(lines)


def _builtin_page(title: str, root: Path, build_dir: Path, files: dict[str, str], package_name: str) -> str | None:
    """Resolve a built-in nav page: user file at its slot wins, else stage a generated copy.

    Returns:
        The build-dir-relative page path, or None when the source (repo-root
        file, README, LICENSE...) does not exist

    """
    filename = {"Home": "index.md", "Contributing": "contributing.md", "License": "license.md"}[title]
    if (build_dir / filename).exists():
        return filename
    if title == "Home":
        readme = root / "README.md"
        files[filename] = (
            _rewrite_page_links(readme.read_text(encoding="utf-8"))
            if readme.exists()
            else _render_docs_index_fallback(_SITE_NAME, package_name)
        )
        return filename
    if title == "Contributing" and (root / "CONTRIBUTING.md").exists():
        files[filename] = _rewrite_page_links((root / "CONTRIBUTING.md").read_text(encoding="utf-8"))
        return filename
    if (
        title == "License"
        and (
            license_source := next(
                (candidate for name in ("LICENSE.md", "LICENSE") if (candidate := root / name).exists()), None
            )
        )
        is not None
    ):
        # Copied to a .md page regardless of the source extension: mkdocs
        # only builds Markdown files, and a bare LICENSE renders as Markdown.
        files[filename] = _rewrite_page_links(license_source.read_text(encoding="utf-8"))
        return filename
    return None


def _resolve_nav_pages(
    root: Path,
    build_dir: Path,
    files: dict[str, str],
    package_name: str,
    pages_json: list[_PageEntry],
) -> list[tuple[str, str]]:
    """Assemble nav (title, page) pairs before the API section.

    With pages.json: entries in json order (built-in titles override their
    slot's page), then built-ins not mentioned, in their default order.
    Without: Home, Contributing, License (when available), then every other
    top-level docs/*.md discovered automatically.
    """
    nav_pages: list[tuple[str, str]] = [(entry["title"], entry["file"]) for entry in pages_json]
    mentioned = {entry["title"] for entry in pages_json if entry["title"] in _BUILTIN_TITLES}

    for title in _BUILTIN_TITLES:
        if title in mentioned:
            continue
        if (file := _builtin_page(title, root, build_dir, files, package_name)) is not None:
            nav_pages.append((title, file))

    if not pages_json:
        nav_pages.extend(_discover_extra_pages(build_dir, {page for _, page in nav_pages}))
    return nav_pages


def _scaffold_docs(context: ProjectContext) -> None:
    """Stage the mkdocs build input in docs-build/.

    Layout:
        - docs/ holds only user-authored documentation (never written to by
          this command)
        - docs-build/ is fully generated and gitignored: wiped and rebuilt
          on every run by copying docs/ first, then filling in whatever the
          project provides - README.md as index.md (fallback page when
          neither exists), CONTRIBUTING.md as contributing.md, LICENSE(.md)
          as license.md, and one mkdocstrings page per Python module in
          reference/
        - mkdocs.yml is rendered with a nav from docs/pages.json when that
          file exists (built-in titles Home/Contributing/License override
          the generated copies; other titles add pages in the given order);
          without pages.json, built-ins come first and extra docs/ pages
          follow, discovered automatically

    A user file already present at a generated page's location wins: no
    generated copy overwrites anything that came from docs/.

    Args:
        context: Project context with paths and configuration

    """
    pyproject_data = PyProjectReader().read(context.pyproject_path)
    package_name = pyproject_data.name.replace("-", "_")
    site_name = _SITE_NAME
    root = context.root_directory
    site_url = _site_url(root, pyproject_data.name)
    mkdocstrings_path = "src" if (root / "src").is_dir() else "."

    docs_source = root / "docs"
    build_dir = root / "docs-build"
    shutil.rmtree(build_dir, ignore_errors=True)
    build_dir.mkdir()
    if docs_source.is_dir():
        shutil.copytree(docs_source, build_dir, dirs_exist_ok=True)

    files: dict[str, str] = {}  # build-dir-relative page -> content to write
    pages_json = _load_pages_json(docs_source)
    nav_pages = _resolve_nav_pages(root, build_dir, files, package_name, pages_json)

    # Link rewriting (GitHub anchors/root-file links) for pages that came
    # from docs/ -- generated copies above are already rewritten
    for md_file in build_dir.rglob("*.md"):
        rel = md_file.relative_to(build_dir).as_posix()
        if rel not in files:
            md_file.write_text(_rewrite_page_links(md_file.read_text(encoding="utf-8")), encoding="utf-8")

    api_files, api_nav = _api_doc_pages(root, package_name, build_dir)
    for path, content in api_files.items():
        files[path.relative_to(build_dir).as_posix()] = content

    for rel_path, content in files.items():
        out = build_dir / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")

    # pages.json is not a documentation page
    (build_dir / _PAGES_JSON).unlink(missing_ok=True)

    # llmstxt sections mirror the nav: one glob-listing per top-level page,
    # API docs covered by the whole reference tree
    section_lines = [f"        {title}:\n          - {page}" for title, page in nav_pages]
    section_lines.append("        API docs:\n          - reference/**/*.md")
    llmstxt_sections = "\n".join(section_lines)

    (root / "mkdocs.yml").write_text(
        _render_mkdocs_yml(site_name, site_url, mkdocstrings_path, _render_nav(nav_pages, api_nav), llmstxt_sections),
        encoding="utf-8",
    )


def _discover_extra_pages(build_dir: Path, already_in_nav: set[str]) -> list[tuple[str, str]]:
    """Find extra top-level docs/*.md pages not in the nav yet (no pages.json).

    Args:
        build_dir: Staged docs-build directory
        already_in_nav: Build-dir-relative pages already in the nav

    Returns:
        (title, page) pairs, alphabetically; title from the page's first
        Markdown heading, falling back to the capitalized file name

    """
    pages: list[tuple[str, str]] = []
    for page in sorted(build_dir.glob("*.md")):
        rel = page.name
        if rel in already_in_nav or rel.startswith("_"):
            continue
        heading = re.search(r"^# (.+)$", page.read_text(encoding="utf-8"), re.MULTILINE)
        title = heading.group(1).strip() if heading else page.stem.replace("-", " ").title()
        pages.append((title, rel))
    return pages


_GENERATED_GITIGNORE_ENTRIES = ("/docs-build/", "/mkdocs.yml")


def _gitignore_generated_files(context: ProjectContext) -> list[str]:
    """Add generated docs paths to .gitignore.

    Everything under docs/ plus mkdocs.yml is regenerated on every build, so
    it should not be committed; each entry is appended only when no
    .gitignore line already covers it exactly.

    Args:
        context: Project context with paths and configuration

    Returns:
        List of gitignore entries appended during this run

    """
    gitignore_path = context.root_directory / ".gitignore"
    existing_lines: set[str] = set()
    if gitignore_path.exists():
        existing_lines = {line.strip() for line in gitignore_path.read_text(encoding="utf-8").splitlines()}

    entries = [entry for entry in _GENERATED_GITIGNORE_ENTRIES if entry not in existing_lines]
    if not entries:
        return []

    prefix = "" if not gitignore_path.exists() else ("\n" if not _ends_with_newline(gitignore_path) else "")
    with gitignore_path.open("a", encoding="utf-8") as fh:
        fh.write(prefix + "# Auto-generated docs scaffold (regenerated by `oarepo-cli library docs`)\n")
        fh.write("\n".join(entries) + "\n")

    return entries


def _ends_with_newline(path: Path) -> bool:
    """Check whether a file ends with a newline so appends don't glue lines.

    Args:
        path: File to inspect

    Returns:
        True if the file is empty or its last byte is a newline

    """
    content = path.read_bytes()
    return not content or content.endswith(b"\n")


def _build_llms_txt(root: Path, *, quiet: bool) -> None:
    """Generate llms.txt/llms-full.txt via a second, plain-mkdocs build.

    Zensical cannot run the mkdocs-llmstxt plugin yet (it silently drops
    unknown plugins), so the plugin only takes effect in a classic mkdocs
    build. The build runs into a throwaway directory and just the two
    llms*.txt artifacts are copied into the real site output.

    Args:
        root: Project root directory (and cwd for the mkdocs build)
        quiet: If True, suppress real-time subprocess output

    """
    tmp_dir = root / ".tmp-mkdocs"
    try:
        result = process.run(
            [_cli_tool_path("mkdocs"), "build", "--clean", "-d", ".tmp-mkdocs"],
            cwd=root,
            check=False,
            # INTERACTIVE, not FORWARD: FORWARD currently never displays
            # the output it captures (see process.py's no-op FORWARD block).
            output_mode=ProcessOutputMode.CAPTURE if quiet else ProcessOutputMode.INTERACTIVE,
        )
        if not result.success:
            return  # llms.txt is best-effort; never fail the docs build over it

        docs_output = root / "build" / "docs"
        for name in ("llms.txt", "llms-full.txt"):
            artifact = tmp_dir / name
            if artifact.exists():
                shutil.copy2(artifact, docs_output / name)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def run_docs(context: ProjectContext, *, quiet: bool = False) -> process.ProcessResult:
    """Scaffold, build, and (locally) open the API documentation.

    Steps:
        1. Stage docs-build/ (user docs/ + generated copies of README/
           CONTRIBUTING/LICENSE + per-module API pages) and mkdocs.yml
        2. Add the generated paths to .gitignore
        3. Build the documentation into build/docs with zensical
        4. Generate llms.txt/llms-full.txt with a plain-mkdocs build
        5. Open the built docs in a browser unless running in CI

    Args:
        context: Project context with paths and configuration
        quiet: If True, suppress real-time subprocess output

    Returns:
        ProcessResult from the zensical build command

    """
    root = context.root_directory
    _scaffold_docs(context)
    _gitignore_generated_files(context)

    result = process.run(
        [_cli_tool_path("zensical"), "build", "--clean"],
        cwd=root,
        check=False,
        output_mode=ProcessOutputMode.INTERACTIVE if not quiet else ProcessOutputMode.CAPTURE,
    )

    if result.success:
        _build_llms_txt(root, quiet=quiet)

    if result.success and not _is_ci():
        # ponytail: macOS "open" / Linux "xdg-open" only, no Windows start fallback
        # (os.startfile) - add when a Windows user needs it.
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        process.run([opener, str(root / "build" / "docs" / "index.html")], cwd=root, check=False)

    return result
