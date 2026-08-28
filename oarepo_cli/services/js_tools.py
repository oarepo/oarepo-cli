# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""JavaScript linting and testing for OARepo library and repository projects."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oarepo_cli.core.context import ProjectContext

from oarepo_cli.configuration import resources
from oarepo_cli.core.errors import ConfigurationError
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
        return process.ProcessResult(
            return_code=0,
            stdout="No package.json found",
            stderr="",
            command=[],
            cwd=root,
            duration_ms=0,
        )

    # Install ESLint dependency if needed
    result = _ensure_eslint_dependency(package_json_path, root, quiet)
    if not result.success:
        return result

    # Write ESLint config
    eslintrc = root / ".eslintrc.yaml"
    eslintrc.write_text(resources.read_text("eslintrc.yaml.tmpl"))

    # Run eslint with --fix
    eslint_bin = root / "node_modules" / ".bin" / "eslint"
    dir_names = [str(d.relative_to(root)) for d in code_directories]

    # Filter out directories with no JS/JSX files
    dirs_with_js = []
    for dir_name in dir_names:
        dir_path = root / dir_name
        if any(dir_path.rglob("*.js")) or any(dir_path.rglob("*.jsx")):
            dirs_with_js.append(dir_name)

    # If no directories have JS files, skip linting
    if not dirs_with_js:
        return process.ProcessResult(
            return_code=0,
            stdout="No JavaScript files found in code directories",
            stderr="",
            command=[],
            cwd=root,
            duration_ms=0,
        )

    result = process.run(
        [str(eslint_bin), "--ext", ".js,.jsx", "--fix", *dirs_with_js],
        cwd=root,
        check=False,
        output_mode=ProcessOutputMode.INTERACTIVE if not quiet else ProcessOutputMode.CAPTURE,
    )
    if not result.success:
        return result

    # Run prettier
    # Convert dir names back to Path objects for prettier
    dirs_with_js_paths = [root / d for d in dirs_with_js]
    return _run_prettier(root, dirs_with_js_paths, quiet)


def run_repository_jslint(context: ProjectContext, *, quiet: bool = False) -> process.ProcessResult:
    """Run ESLint and Prettier on repository JavaScript files using Invenio's node_modules.

    Unlike library jslint, which installs dependencies in the project root,
    repository jslint uses the node_modules from the Invenio instance assets
    directory. This avoids interfering with Invenio's JavaScript dependency
    locking mechanisms.

    Args:
        context: Project context with paths and configuration
        quiet: If True, suppress progress output

    Returns:
        ProcessResult from the linting commands

    """
    from oarepo_cli.services.repository import lock_assets
    from oarepo_cli.ui import ConsoleOutput

    console = ConsoleOutput(quiet=quiet)
    root = context.root_directory

    # Ensure package.json exists (lock if needed)
    package_json_path = root / "package.json"
    if not package_json_path.exists():
        console.info("-> No package.json found, locking JavaScript dependencies\n")
        lock_assets(context, quiet=quiet)

    if not package_json_path.exists():
        return process.ProcessResult(
            return_code=0,
            stdout="No package.json found and lock_assets did not create one",
            stderr="",
            command=[],
            cwd=root,
            duration_ms=0,
        )

    # Ensure node_modules symlink
    top_level_node_modules = _ensure_repository_node_modules(context, root, quiet=quiet)

    # Write ESLint config
    eslintrc = root / ".eslintrc.yaml"
    eslintrc.write_text(resources.read_text("eslintrc.yaml.tmpl"))

    # Filter code directories to those with JS files
    code_directories = [d for d in context.code_directories if d.name != "tests"]
    dir_names = [str(d.relative_to(root)) for d in code_directories]
    dirs_with_js = _filter_dirs_with_js_files(root, dir_names)

    if not dirs_with_js:
        return process.ProcessResult(
            return_code=0,
            stdout="No JavaScript files found in code directories",
            stderr="",
            command=[],
            cwd=root,
            duration_ms=0,
        )

    # Run eslint
    eslint_bin = top_level_node_modules / ".bin" / "eslint"
    if not eslint_bin.exists():
        return process.ProcessResult(
            return_code=1,
            stdout="",
            stderr="eslint binary not found in node_modules",
            command=[],
            cwd=root,
            duration_ms=0,
        )

    result = process.run(
        [str(eslint_bin), "--ext", ".js,.jsx", "--fix", *dirs_with_js],
        cwd=root,
        check=False,
        output_mode=ProcessOutputMode.INTERACTIVE if not quiet else ProcessOutputMode.CAPTURE,
    )
    if not result.success:
        return result

    # Run prettier
    dirs_with_js_paths = [root / d for d in dirs_with_js]
    return _run_prettier(root, dirs_with_js_paths, quiet)


def _filter_dirs_with_js_files(root: Path, dir_names: list[str]) -> list[str]:
    """Filter directory names to only include those containing JS/JSX files.

    Args:
        root: Project root directory
        dir_names: List of directory names relative to root

    Returns:
        List of directory names that contain at least one .js or .jsx file

    """
    dirs_with_js = []
    for dir_name in dir_names:
        dir_path = root / dir_name
        if any(dir_path.rglob("*.js")) or any(dir_path.rglob("*.jsx")):
            dirs_with_js.append(dir_name)
    return dirs_with_js


def _ensure_repository_node_modules(context: ProjectContext, root: Path, *, quiet: bool) -> Path:
    """Ensure node_modules symlink exists and return its path.

    Args:
        context: Project context
        root: Project root directory
        quiet: If True, suppress output

    Returns:
        Path to the top-level node_modules (symlink or directory)

    """
    from oarepo_cli.services.repository import get_instance_path, install_repository
    from oarepo_cli.ui import ConsoleOutput

    console = ConsoleOutput(quiet=quiet)
    instance_path = get_instance_path(context)
    instance_node_modules = instance_path / "assets" / "node_modules"

    # Ensure instance node_modules exists
    if not instance_node_modules.exists():
        console.info("-> Instance node_modules not found, running repository install\n")
        install_repository(context, quiet=quiet)

    # Create symlink if needed
    top_level_node_modules = root / "node_modules"
    if not top_level_node_modules.exists():
        console.info("-> Creating node_modules symlink\n")
        top_level_node_modules.symlink_to(instance_node_modules)
    elif not top_level_node_modules.is_symlink():
        console.warning("Warning: node_modules exists but is not a symlink - using it as-is")

    return top_level_node_modules


def _ensure_eslint_dependency(package_json_path: Path, root: Path, quiet: bool) -> process.ProcessResult:
    """Ensure ESLint dependency is installed.

    Args:
        package_json_path: Path to package.json
        root: Project root directory
        quiet: If True, suppress output

    Returns:
        ProcessResult from installation commands

    """
    with package_json_path.open() as f:
        package_data = json.load(f)

    dev_deps = package_data.get("devDependencies", {})
    if "@inveniosoftware/eslint-config-invenio" not in dev_deps:
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
        result = process.run(
            ["pnpm", "install"],
            cwd=root,
            check=False,
            output_mode=ProcessOutputMode.INTERACTIVE if not quiet else ProcessOutputMode.CAPTURE,
        )
        if not result.success:
            return result

    return process.ProcessResult(
        return_code=0,
        stdout="",
        stderr="",
        command=[],
        cwd=root,
        duration_ms=0,
    )


def _run_prettier(root: Path, code_directories: list[Path], quiet: bool) -> process.ProcessResult:
    """Run Prettier on JavaScript files.

    Args:
        root: Project root directory
        code_directories: List of directories to lint
        quiet: If True, suppress output

    Returns:
        ProcessResult from prettier command

    """
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
    quiet: bool = False,
) -> process.ProcessResult:
    """Replace the current process with ``pnpm test`` (Jest) in the assets dir.

    Runs Jest via ``pnpm -C <instance-assets> test`` rather than the more
    obvious ``invenio webpack run test``. We deliberately bypass ``invenio
    webpack run`` because it *swallows the npm script's exit code*: when Jest
    fails, pnpm exits non-zero (``ELIFECYCLE  Test failed``), but ``invenio
    webpack run`` prints "Executed NPM script" and returns 0 regardless.
    Since this function ``os.execve``s and thereby inherits the child's exit
    code verbatim, going through invenio made a *failing* JS suite report
    success -- so CI would stay green on red tests. ``pnpm`` propagates
    Jest's real exit code. Verified end-to-end against a real repository; the
    swallowing hit ``library`` and ``repository`` identically, since both
    callers funnel through this one passthrough (a library was never any
    safer here -- the bug was just never exercised with a failing test).

    Never returns once the real test run starts: nothing needs to happen in
    this process afterward, so a terminal Ctrl+C hits Jest directly and its
    exit code is preserved exactly -- mirrors this module's ``run_jslint``
    sibling being the exception (multi-step, so it can't do the same, see its
    own docstring) and every other one-shot passthrough elsewhere in this
    codebase (``services.repository.exec_invenio``, etc.). Only the ``setup``
    path (which delegates to ``setup_jstests``) and the missing-``pnpm``
    precondition below return a value instead -- they're setup/infrastructure
    outcomes, not a real test-run outcome, so there's nothing to exec into.

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
        setup: If True, generate the Jest configuration instead of running tests
        service_env: Environment variables for connecting to already-started
            services, if any (a repository needs none -- see
            ``services.repository.exec_shell``'s identical rationale)
        extra_args: Additional arguments passed to the test command
        quiet: If True, suppress progress output during setup

    Returns:
        A ``ProcessResult`` for the ``setup``/missing-binary cases; never
        returns otherwise (successful test runs ``os.execve`` into Jest)

    Raises:
        OSError: If pnpm can't be exec'd (not found, not executable, ...)

    """
    from oarepo_cli.core.platform import get_platform_detector
    from oarepo_cli.services.repository import get_instance_path

    extra_args = extra_args or []

    if setup:
        return setup_jstests(context, quiet=quiet)

    # Resolve pnpm from PATH -- it isn't a venv binary (it's the system/Node
    # package manager, same one setup_jstests shells out to). We exec pnpm
    # rather than `invenio webpack run test` on purpose: see the note in this
    # function's docstring -- `invenio webpack run` returns 0 even when the
    # underlying Jest run fails, which would hide failing tests from CI.
    pnpm_path = shutil.which("pnpm")
    if pnpm_path is None:
        return process.ProcessResult(
            return_code=1,
            stdout="",
            stderr="pnpm command not found on PATH",
            command=[],
            cwd=context.root_directory,
            duration_ms=0,
        )

    # jest.config.js / setupTests.js and the `test` npm script all live in the
    # instance's assets dir (written there by setup_jstests), so run pnpm with
    # that as its working directory.
    assets_path = get_instance_path(context) / "assets"

    bin_dir = get_platform_detector().get_venv_bin_dir()
    cmd_env = process.build_subprocess_env(service_env)
    cmd_env["VIRTUAL_ENV"] = str(context.venv_path)
    venv_bin_path = str(context.venv_path / bin_dir)
    cmd_env["PATH"] = f"{venv_bin_path}{os.pathsep}{cmd_env.get('PATH', '')}"

    # `pnpm -C <assets> test [extra_args]`: pnpm forwards args after the
    # script name straight to Jest (no `--` separator -- unlike npm, pnpm
    # passes a literal `--` through to the script, which Jest would then read
    # as "end of options" and treat following flags as positional paths).
    cmd = [pnpm_path, "-C", str(assets_path), "test", *extra_args]

    os.chdir(context.root_directory)
    os.execve(pnpm_path, cmd, cmd_env)  # noqa S606 no shell is ok here, replacing the process
    return None


def setup_jstests(context: ProjectContext, *, quiet: bool = False) -> process.ProcessResult:
    """Generate the Jest configuration for a project's JavaScript tests.

    Port of ``library_runner.sh``'s ``setup_jstests``: creates the webpack
    project, writes ``jest.config.js``/``setupTests.js`` into the Invenio
    instance's ``assets/`` directory, and installs the webpack + Jest
    dependencies. ``invenio webpack``/``collect`` are pure asset operations
    (no DB/search), so no service connection env is threaded here.

    Works for both ``library`` and ``repository`` projects: it discovers the
    package's own ``invenio_assets.webpack`` entry points, which a repository
    has just as a library does. Verified end-to-end against a real repository
    (it was originally ported for libraries only, but nothing here is
    library-specific).

    Args:
        context: Project context with paths and configuration
        quiet: If True, suppress subprocess output

    Returns:
        A success ``ProcessResult`` once setup completes

    Raises:
        ProcessExecutionError: If any setup subprocess fails

    """
    from oarepo_cli.services.pyproject_reader import PyProjectReader
    from oarepo_cli.services.repository import _run_invenio, get_instance_path
    from oarepo_cli.ui import ConsoleOutput

    console = ConsoleOutput(quiet=quiet)
    root = context.root_directory
    assets_path = get_instance_path(context) / "assets"

    console.info("-> Creating webpack project\n")
    _run_invenio(context, ["webpack", "clean", "create"], quiet=quiet)

    # Work around the Invenio RSPack "packages field missing or empty" error.
    _patch_pnpm_workspace(assets_path / "pnpm-workspace.yaml")
    # Plain "jest": `invenio webpack run test <args>` forwards <args> via pnpm's
    # own trailing-arg appending, so a bash-style `$@` (as in the old
    # library_runner.sh) is a dead no-op under pnpm's `sh -c`.
    _ensure_npm_script(assets_path / "package.json", "test", "jest")

    console.info("-> Generating jest.config.js\n")
    package_name = PyProjectReader().read(context.pyproject_path).name
    entries = _get_webpack_entries(context, package_name)
    if not entries:
        raise ConfigurationError(
            f"No 'invenio_assets.webpack' entry points found for '{package_name}', so there is "
            "nothing to test and jest.config.js cannot be generated. Ensure the package declares "
            'a webpack bundle (see [project.entry-points."invenio_assets.webpack"] in pyproject.toml).'
        )

    # Paths embedded into jest.config.js are normalized to POSIX (forward
    # slashes): a Windows backslash path in a JS string literal would be read
    # as escape sequences (e.g. "C:\Users" -> invalid "\U"). Node/Jest accept
    # forward slashes on every platform.
    coverage_roots = ",\n    ".join(f'"**{e[1:]}/**/*.{{js,jsx}}"' for e in entries)
    test_roots = ", ".join(f'"{Path(os.path.realpath(assets_path / e)).as_posix()}"' for e in entries)

    jest_config = (
        resources.read_text("jest.config.js.tmpl")
        .replace("@@COVERAGE_ROOTS@@", coverage_roots)
        .replace("@@TEST_ROOTS@@", test_roots)
        .replace("@@ASSETS_PATH@@", assets_path.as_posix())
        .replace("@@ROOT_DIR@@", root.as_posix())
    )
    (assets_path / "jest.config.js").write_text(jest_config)
    (assets_path / "setupTests.js").write_text(resources.read_text("setupTests.js.tmpl"))

    console.info("-> Installing webpack and Jest dependencies\n")
    _run_invenio(context, ["collect"], quiet=quiet)
    _run_invenio(context, ["webpack", "install"], quiet=quiet)

    dev_deps = _get_rdm_dev_deps(context)
    if dev_deps:
        process.run(
            ["pnpm", "add", "-C", str(assets_path), "-w", "-D", *dev_deps],
            cwd=root,
            check=True,
            output_mode=ProcessOutputMode.CAPTURE if quiet else ProcessOutputMode.INTERACTIVE,
        )

    console.success("✓ Jest setup complete\n")
    return process.ProcessResult(return_code=0, stdout="", stderr="", command=[], cwd=root, duration_ms=0)


def _marked_result(output: str, marker: str) -> str:
    """Extract the marker-prefixed result line from ``invenio shell`` output.

    The scripts print their result on a ``<marker>...`` line so it can be
    picked out of the app-boot logging invenio shell also writes to stdout.
    """
    line = next((line for line in output.splitlines() if line.startswith(marker)), "")
    return line[len(marker) :]


def _get_webpack_entries(context: ProjectContext, package_name: str) -> list[str]:
    """Discover the package's ``invenio_assets.webpack`` entry-point root dirs.

    The bundle objects' ``.entry`` resolves against ``current_app``, so
    ``webpack_entries.py`` runs inside ``invenio shell`` (live app context).
    The distribution name is passed via an environment variable.
    """
    from oarepo_cli.services.repository import run_invenio_shell

    out = run_invenio_shell(
        context,
        resources.read_text("webpack_entries.py"),
        env={"OAREPO_PACKAGE": package_name},
    ).stdout
    return [e for e in _marked_result(out, _ENTRIES_MARKER).split(",") if e]


def _get_rdm_dev_deps(context: ProjectContext) -> list[str]:
    """Read invenio-rdm-records' Jest devDependencies as ``name@version`` specs.

    Runs ``rdm_dev_deps.py`` in ``invenio shell`` -- it only reads a bundled
    ``package.json`` (no app needed), but setup already boots the app for
    other steps, so reusing the one shell primitive is simpler than a second.
    """
    from oarepo_cli.services.repository import run_invenio_shell

    out = run_invenio_shell(context, resources.read_text("rdm_dev_deps.py")).stdout
    return _marked_result(out, _DEV_DEPS_MARKER).split()


def _ensure_npm_script(package_file: Path, name: str, script: str) -> None:
    """Add an npm script to ``package.json`` if it isn't already defined.

    ``invenio webpack create`` currently writes a real (merged) ``package.json``
    into the instance, but guard against it being a symlink into the installed
    package all the same -- writing through it would inject our script into the
    shared ``invenio-assets`` copy in site-packages (see ``_patch_pnpm_workspace``
    for the same LinkStorage hazard).
    """
    data = json.loads(package_file.read_text())
    scripts = data.setdefault("scripts", {})
    if name not in scripts:
        scripts[name] = script
        if package_file.is_symlink():
            package_file.unlink()
        package_file.write_text(json.dumps(data, indent=2))


def _patch_pnpm_workspace(workspace_file: Path) -> None:
    """Ensure ``pnpm-workspace.yaml`` has a ``packages`` key (RSPack workaround).

    Stock ``invenio-assets`` ships ``pnpm-workspace.yaml`` without a
    ``packages:`` key, which makes pnpm v10 reject the workspace-root
    ``pnpm add -w`` in ``setup_jstests`` with "packages field missing or
    empty". Append ``packages: []`` when it's absent. Edited as text (not via
    a YAML library) so oarepo-cli needs no PyYAML dependency.

    Crucially, ``invenio webpack create`` **symlinks** this file into the
    instance's ``assets/`` dir straight from the installed ``invenio-assets``
    package (pywebpack ``LinkStorage``). Writing through that symlink with
    ``Path.write_text`` would mutate the shared, pip-installed template in
    ``site-packages`` -- a side effect that leaks into every instance sharing
    the venv and silently vanishes on reinstall. So if the target is a
    symlink, replace it with a real, instance-local copy (preserving the
    upstream contents we just read) instead of following it.
    """
    text = workspace_file.read_text() if workspace_file.exists() else ""
    if "packages:" in text:
        return
    if workspace_file.is_symlink():
        workspace_file.unlink()
    text = (text.rstrip() + "\n" if text.strip() else "") + "packages: []\n"
    workspace_file.write_text(text)


# Prefixes the discovery scripts print their result on, so the caller can pick
# it out of invenio shell's own logging on stdout. Kept in sync with the
# ``MARKER`` constants in webpack_entries.py / rdm_dev_deps.py.
_ENTRIES_MARKER = "OAREPO_WEBPACK_ENTRIES:"
_DEV_DEPS_MARKER = "OAREPO_RDM_DEV_DEPS:"
