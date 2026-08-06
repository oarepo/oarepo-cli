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
from oarepo_cli.services.process import ProcessOutputMode


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
            pass
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
            pass
        result = process.run(
            ["pnpm", "add", "-D", "@inveniosoftware/eslint-config-invenio@2"],
            cwd=root,
            check=False,
            output_mode=ProcessOutputMode.INTERACTIVE if not quiet else ProcessOutputMode.CAPTURE,
        )
        if not result.success:
            return result

    # Check if eslint binary exists
    eslint_bin = root / "node_modules" / ".bin" / "eslint"
    if not eslint_bin.exists():
        if not quiet:
            pass
        result = process.run(
            ["pnpm", "install"],
            cwd=root,
            check=False,
            output_mode=ProcessOutputMode.INTERACTIVE if not quiet else ProcessOutputMode.CAPTURE,
        )
        if not result.success:
            return result

    # Write ESLint config
    if not quiet:
        pass
    eslintrc = root / ".eslintrc.yaml"
    eslintrc.write_text(resources.read_text("eslintrc.yaml.tmpl"))

    # Run eslint with --fix
    if not quiet:
        pass

    # Pass directory names as relative paths (matching bash script behavior)
    dir_names = [str(d.relative_to(root)) for d in code_directories]

    result = process.run(
        [str(eslint_bin), "--ext", ".js,.jsx", "--fix", *dir_names],
        cwd=root,
        check=False,
        output_mode=ProcessOutputMode.INTERACTIVE if not quiet else ProcessOutputMode.CAPTURE,
    )
    if not result.success:
        return result

    # Run prettier
    if not quiet:
        pass

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
        output_mode=ProcessOutputMode.INTERACTIVE if not quiet else ProcessOutputMode.CAPTURE,
    )


def run_jstest(
    context: ProjectContext,
    *,
    setup: bool = False,
    service_env: dict[str, str] | None = None,
    extra_args: list[str] | None = None,
    quiet: bool = False,  # noqa: ARG001 -- kept for interface symmetry with run_jslint
) -> process.ProcessResult:
    """Replace the current process with ``invenio webpack run test`` (Jest).

    Mirrors ``library_runner.sh``'s ``run_jstest``. Never returns once the
    real test run starts: nothing needs to happen in this process
    afterward, so a terminal Ctrl+C hits Jest directly and its exit code is
    preserved exactly -- mirrors this module's ``run_jslint`` sibling being
    the exception (multi-step, so it can't do the same, see its own
    docstring) and every other one-shot passthrough elsewhere in this
    codebase (``services.repository.exec_invenio``, etc.). Only the two
    precondition-failure paths below (``setup`` not implemented, missing
    ``invenio`` binary) return a value instead -- they're infrastructure
    errors, not a real test-run outcome, so there's nothing to exec into.

    Unlike ``library``/``repository``'s callers of this function, which
    decide *how* to start Docker services differently (``library``: raw
    docker-services-cli via ``ServicesLifecycleManager``; ``repository``:
    ``invenio-cli services start``, matching ``repository run``/``shell``/
    ``test`` -- see those for why raw docker-services-cli doesn't apply to
    a repository), this function itself doesn't start anything: the caller
    starts services beforehand and passes in whatever connection env vars
    (if any) the subprocess needs.

    Args:
        context: Project context with paths and configuration
        setup: If True, run setup instead of tests
        service_env: Environment variables for connecting to already-started
            services, if any (a repository needs none -- see
            ``services.repository.exec_shell``'s identical rationale)
        extra_args: Additional arguments passed to the test command
        quiet: Unused (kept for interface symmetry with ``run_jslint``)

    Returns:
        A precondition-failure ``ProcessResult`` for the ``setup``/missing-binary
        cases; never returns otherwise

    Raises:
        OSError: If invenio can't be exec'd (not found, not executable, ...)

    """
    from oarepo_cli.core.platform import get_platform_detector

    extra_args = extra_args or []

    if setup:
        # Setting up Jest config involves webpack entry-point discovery and
        # config generation -- not ported from library_runner.sh yet, so
        # this delegates to it instead of duplicating that logic here.
        return process.ProcessResult(
            return_code=1,
            stdout="",
            stderr="jstest setup not implemented - use library_runner.sh for this",
            command=[],
            cwd=context.root_directory,
            duration_ms=0,
        )

    # Get the invenio binary from venv
    platform = get_platform_detector()
    bin_dir = platform.get_venv_bin_dir()
    invenio_path = context.venv_path / bin_dir / "invenio"

    if not invenio_path.exists():
        return process.ProcessResult(
            return_code=1,
            stdout="",
            stderr="invenio command not found in virtual environment",
            command=[],
            cwd=context.root_directory,
            duration_ms=0,
        )

    cmd_env = process.build_subprocess_env(service_env)
    cmd_env["VIRTUAL_ENV"] = str(context.venv_path)
    venv_bin_path = str(context.venv_path / bin_dir)
    cmd_env["PATH"] = f"{venv_bin_path}{os.pathsep}{cmd_env.get('PATH', '')}"

    # Run: invenio webpack run test [extra_args]
    cmd = [str(invenio_path), "webpack", "run", "test", *extra_args]

    os.chdir(context.root_directory)
    os.execve(str(invenio_path), cmd, cmd_env)
    return None
