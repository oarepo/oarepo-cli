# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""JavaScript linting and testing for OARepo library projects."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oarepo_cli.core.context import ProjectContext

from oarepo_cli.configuration import resources
from oarepo_cli.services import process


def run_jslint(context: ProjectContext, *, quiet: bool = False) -> process.ProcessResult:
    """Run ESLint and Prettier on JavaScript files.

    Mirrors ``library_runner.sh``'s ``run_jslint``: installs necessary
    dependencies if needed, generates .eslintrc.yaml config, runs eslint
    with --fix, and runs prettier.

    Note: Unlike other commands, jslint excludes the tests/ directory from
    code_directories, matching the bash script's behavior.

    Args:
        context: Project context with paths and configuration
        quiet: If True, suppress progress output

    Returns:
        ProcessResult from the linting commands
    """
    root = context.root_directory
    # Exclude tests directory for jslint, matching bash script behavior
    code_directories = [d for d in context.code_directories if d.name != "tests"]

    # Check if package.json exists
    package_json_path = root / "package.json"
    if not package_json_path.exists():
        if not quiet:
            print("No package.json found, skipping JavaScript linting.")
        return process.ProcessResult(
            return_code=0,
            stdout="No package.json found",
            stderr="",
            command=[],
            cwd=root,
            duration_ms=0,
        )

    # Check if @inveniosoftware/eslint-config-invenio is in devDependencies
    with package_json_path.open() as f:
        package_data = json.load(f)

    dev_deps = package_data.get("devDependencies", {})
    if "@inveniosoftware/eslint-config-invenio" not in dev_deps:
        if not quiet:
            print("Adding @inveniosoftware/eslint-config-invenio to dev dependencies...")
        result = process.run(
            ["pnpm", "add", "-D", "@inveniosoftware/eslint-config-invenio@2"],
            cwd=root,
            check=False,
            interactive=not quiet,
        )
        if not result.success:
            return result

    # Check if eslint binary exists
    eslint_bin = root / "node_modules" / ".bin" / "eslint"
    if not eslint_bin.exists():
        if not quiet:
            print("Installing ESLint...")
        result = process.run(
            ["pnpm", "install"],
            cwd=root,
            check=False,
            interactive=not quiet,
        )
        if not result.success:
            return result

    # Write ESLint config
    if not quiet:
        print("Copying ESLint configuration files...")
    eslintrc = root / ".eslintrc.yaml"
    eslintrc.write_text(resources.read_text("eslintrc.yaml.tmpl"))

    # Run eslint with --fix
    if not quiet:
        print("Running ESLint...")

    # Pass directory names as relative paths (matching bash script behavior)
    dir_names = [str(d.relative_to(root)) for d in code_directories]

    result = process.run(
        [str(eslint_bin), "--ext", ".js,.jsx", "--fix", *dir_names],
        cwd=root,
        check=False,
        interactive=not quiet,
    )
    if not result.success:
        return result

    # Run prettier
    if not quiet:
        print("Running Prettier...")

    # Check if we're in CI
    is_ci = os.environ.get("CI", "false").lower() == "true"
    prettier_flag = "--check" if is_ci else "--write"

    prettier_bin = root / "node_modules" / ".bin" / "prettier"

    # Build prettier patterns: append /**/*.{js,jsx} to each directory
    # Matching bash: "${code_directories[@]/%//**/*.{js,jsx}}"
    prettier_patterns = [f"{d.relative_to(root)}/**/*.{{js,jsx}}" for d in code_directories]

    return process.run(
        [str(prettier_bin), prettier_flag, *prettier_patterns],
        cwd=root,
        check=False,
        interactive=not quiet,
    )


def run_jstest(
    context: ProjectContext,
    *,
    setup: bool = False,
    skip_services: bool = False,
    extra_args: list[str] | None = None,
    quiet: bool = False,
) -> process.ProcessResult:
    """Run JavaScript tests (Jest) via invenio webpack.

    Mirrors ``library_runner.sh``'s ``run_jstest``: either sets up Jest
    configuration (setup=True) or runs tests via ``invenio webpack run test``.

    Args:
        context: Project context with paths and configuration
        setup: If True, run setup instead of tests
        skip_services: If True, skip starting Docker services
        extra_args: Additional arguments passed to the test command
        quiet: If True, suppress progress output

    Returns:
        ProcessResult from the test command
    """
    extra_args = extra_args or []

    if setup:
        # For now, delegate setup to the bash script's logic or implement it later
        # This is a complex operation involving webpack entry discovery and Jest config generation
        return process.ProcessResult(
            return_code=1,
            stdout="",
            stderr="jstest setup not yet implemented - use library_runner.sh for now",
            command=[],
            cwd=context.root_directory,
            duration_ms=0,
        )

    # Run tests via invenio shell command
    venv_python = context.venv_path / "bin" / "python"

    # Build invenio command
    cmd = [str(venv_python), "-m", "invenio", "webpack", "run", "test", *extra_args]

    # Handle --skip-services flag
    if not skip_services:
        # Would need to start services here, but that's handled by the test orchestrator
        # For now, just run the command
        pass

    return process.run(
        cmd,
        cwd=context.root_directory,
        check=False,
        interactive=not quiet,
    )
