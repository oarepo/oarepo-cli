# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Mkdocs documentation scaffolding and build for OARepo library projects."""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oarepo_cli.core.context import ProjectContext

from oarepo_cli.configuration import resources
from oarepo_cli.services import process
from oarepo_cli.services.process import ProcessOutputMode
from oarepo_cli.services.pyproject_reader import PyProjectReader

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


def _scaffold_docs(context: ProjectContext) -> None:
    """Generate the docs scaffold, regenerating every file on each run.

    Every generated file is fully rewritten (unlike the shared docs.yaml
    workflow, which writes only missing files) so the docs always match the
    project's current state:

    - docs/index.md is a copy of the project's README.md (or a minimal
      generated fallback page when there is no README)
    - docs/contributing.md exists iff CONTRIBUTING.md does
    - docs/license.md exists iff LICENSE or LICENSE.md does
    - docs/reference/ holds one mkdocstrings page per Python module,
      mirroring the package layout
    - mkdocs.yml gets a nav matching the pages that actually exist

    The whole docs/ directory is deleted and recreated so removed modules or
    pages never linger as stale copies.

    Args:
        context: Project context with paths and configuration

    """
    pyproject_data = PyProjectReader().read(context.pyproject_path)
    package_name = pyproject_data.name.replace("-", "_")
    site_name = "OARepo API Reference"
    root = context.root_directory
    site_url = _site_url(root, pyproject_data.name)
    mkdocstrings_path = "src" if (root / "src").is_dir() else "."

    docs_dir = root / "docs"
    shutil.rmtree(docs_dir, ignore_errors=True)
    docs_dir.mkdir()

    files: dict[Path, str] = {}
    top_pages = [("Home", "index.md")]

    readme = root / "README.md"
    if readme.exists():
        files[docs_dir / "index.md"] = _rewrite_page_links(readme.read_text(encoding="utf-8"))
    else:
        files[docs_dir / "index.md"] = _render_docs_index_fallback(site_name, package_name)

    contributing = root / "CONTRIBUTING.md"
    if contributing.exists():
        files[docs_dir / "contributing.md"] = _rewrite_page_links(contributing.read_text(encoding="utf-8"))
        top_pages.append(("Contributing", "contributing.md"))

    license_file = next((candidate for name in ("LICENSE.md", "LICENSE") if (candidate := root / name).exists()), None)
    if license_file is not None:
        # Copied to a .md page regardless of the source extension: mkdocs
        # only builds Markdown files, and a bare LICENSE renders as Markdown.
        files[docs_dir / "license.md"] = _rewrite_page_links(license_file.read_text(encoding="utf-8"))
        top_pages.append(("License", "license.md"))

    api_files, api_nav = _api_doc_pages(root, package_name, docs_dir)
    files.update(api_files)

    # llmstxt sections mirror the nav: one glob-listing per top-level page,
    # API docs covered by the whole reference tree
    section_lines = [f"        {title}:\n          - {page}" for title, page in top_pages]
    section_lines.append("        API docs:\n          - reference/**/*.md")
    llmstxt_sections = "\n".join(section_lines)

    files[root / "mkdocs.yml"] = _render_mkdocs_yml(
        site_name, site_url, mkdocstrings_path, _render_nav(top_pages, api_nav), llmstxt_sections
    )

    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


_GENERATED_GITIGNORE_ENTRIES = ("/docs/", "/mkdocs.yml")


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
        1. (Re)generate the docs scaffold (docs/index.md from README.md,
           contributing/license pages, per-module API pages and mkdocs.yml)
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
