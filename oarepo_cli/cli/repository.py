# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Repository commands for OARepo CLI."""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003
from typing import Annotated

import typer

from oarepo_cli.cli import js_commands, lint_commands
from oarepo_cli.core.context import discover_context
from oarepo_cli.core.errors import OARepoError
from oarepo_cli.services import invenio_cli, repository, translations
from oarepo_cli.services.local_packages import LocalPackageManager
from oarepo_cli.services.models import ModelManager
from oarepo_cli.services.server import ServerRunner
from oarepo_cli.ui import ConsoleOutput

# Create the repository subcommand group
repository_app = typer.Typer(
    name="repository",
    help="Commands for OARepo repository management",
    no_args_is_help=True,
)

# Create the services subcommand group
services_app = typer.Typer(
    name="services",
    help="Docker services management (delegates to invenio-cli)",
    no_args_is_help=True,
)

# Create the model subcommand group
model_app = typer.Typer(
    name="model",
    help="Record model management (create/update from copier templates)",
    no_args_is_help=True,
)

# Create the local subcommand group
local_app = typer.Typer(
    name="local",
    help="Local, editable package management (tool.uv.sources)",
    no_args_is_help=True,
)

# Create the index subcommand group
index_app = typer.Typer(
    name="index",
    help="Search index management",
    no_args_is_help=True,
)

# Register services, model, local and index as subcommands of repository
repository_app.add_typer(services_app)
repository_app.add_typer(model_app)
repository_app.add_typer(local_app)
repository_app.add_typer(index_app)

# Each services subcommand is a pure passthrough to invenio-cli: extra
# arguments/options are forwarded verbatim, and --help must reach
# invenio-cli itself (producing invenio-cli's own help) rather than being
# intercepted by Typer/Click.
_SERVICES_CONTEXT_SETTINGS = {
    "allow_extra_args": True,
    "allow_interspersed_args": True,
    "ignore_unknown_options": True,
    "help_option_names": [],
}

# `repository run` forwards unrecognized args/options to the underlying
# invenio-cli/invenio run command (e.g. `-p 5001`), like
# repository_runner.sh's run_server()'s extra_options -- but unlike the
# services subcommands above, `--help` should still show oarepo-cli's own
# help (--no-services/--no-celery/--quiet are real options here, not a pure
# passthrough), so help_option_names is left at its default.
_RUN_CONTEXT_SETTINGS = {
    "allow_extra_args": True,
    "allow_interspersed_args": True,
    "ignore_unknown_options": True,
}


@repository_app.callback()
def repository_callback() -> None:
    """Repository command group."""


@services_app.callback()
def services_callback() -> None:
    """Repository services command group."""


@model_app.callback()
def model_callback() -> None:
    """Repository model command group."""


@local_app.callback()
def local_callback() -> None:
    """Repository local package command group."""


@index_app.callback()
def index_callback() -> None:
    """Repository search index command group."""


def _run_services_subcommand(ctx: typer.Context, subcommand: str, *, quiet: bool) -> None:
    """Delegate to ``invenio-cli services <subcommand> [args...]``.

    Mirrors ``repository_runner.sh``'s ``services()`` function: pure
    passthrough, with the subcommand's own exit code propagated exactly
    (not collapsed to 0/1), and any extra arguments/options forwarded
    verbatim to invenio-cli.

    Args:
        ctx: Typer context, used to capture passthrough arguments
        subcommand: One of "setup", "start", "stop", "destroy"
        quiet: If True, suppress real-time subprocess output
    """
    extra_args = ctx.args if ctx.args else []

    try:
        context = discover_context()
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)
        console_err.error(f"\n✗ services {subcommand} failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e

    result = invenio_cli.run_invenio_cli(
        context,
        ["services", subcommand, *extra_args],
        quiet=quiet,
        check=False,
    )
    raise typer.Exit(code=result.return_code)


@services_app.command("setup", context_settings=_SERVICES_CONTEXT_SETTINGS)
def services_setup(
    ctx: typer.Context,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress output from invenio-cli")
    ] = False,
) -> None:
    """Setup Docker services.

    Delegates to ``invenio-cli services setup``. Any extra arguments
    (e.g. ``-N`` for no demo data) are passed through verbatim.
    """
    _run_services_subcommand(ctx, "setup", quiet=quiet)


@services_app.command("start", context_settings=_SERVICES_CONTEXT_SETTINGS)
def services_start(
    ctx: typer.Context,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress output from invenio-cli")
    ] = False,
) -> None:
    """Start Docker services.

    Delegates to ``invenio-cli services start``. Any extra arguments are
    passed through verbatim.
    """
    _run_services_subcommand(ctx, "start", quiet=quiet)


@services_app.command("stop", context_settings=_SERVICES_CONTEXT_SETTINGS)
def services_stop(
    ctx: typer.Context,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress output from invenio-cli")
    ] = False,
) -> None:
    """Stop Docker services.

    Delegates to ``invenio-cli services stop``. Any extra arguments are
    passed through verbatim.
    """
    _run_services_subcommand(ctx, "stop", quiet=quiet)


@services_app.command("destroy", context_settings=_SERVICES_CONTEXT_SETTINGS)
def services_destroy(
    ctx: typer.Context,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress output from invenio-cli")
    ] = False,
) -> None:
    """Destroy Docker services.

    Delegates to ``invenio-cli services destroy``. Any extra arguments are
    passed through verbatim.
    """
    _run_services_subcommand(ctx, "destroy", quiet=quiet)


@repository_app.command()
def install(
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress output from subprocesses (uv, invenio-cli, etc.)",
        ),
    ] = False,
) -> None:
    """Install repository in virtual environment.

    See ``services.repository.install_repository`` for the individual steps.

    Examples:
        $ oarepo-cli repository install
        $ oarepo-cli repository install --quiet

    Exit codes:
        0: Installation successful
        1: Installation failed
    """
    try:
        context = discover_context()
        console = ConsoleOutput(quiet=quiet)

        console.info("\n→ Installing repository...\n")

        repository.install_repository(context, quiet=quiet)

        console.success(
            "\n✓ Repository installed successfully!\n",
            fg=typer.colors.BRIGHT_GREEN,
            bold=True,
        )

    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)  # Always show errors
        console_err.error(f"\n✗ Installation failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e


@repository_app.command()
def upgrade(
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress output from subprocesses (uv, invenio-cli, etc.)",
        ),
    ] = False,
) -> None:
    """Upgrade repository: clean venv/cache and reinstall from scratch.

    Mirrors ``repository_runner.sh``'s ``upgrade_repository`` function:
    1. Removes the virtual environment (if present)
    2. Removes uv.lock (if present)
    3. Cleans the uv cache (``uv cache clean --force``)
    4. Reinstalls the repository (same steps as ``repository install``)

    Examples:
        $ oarepo-cli repository upgrade
        $ oarepo-cli repository upgrade --quiet

    Exit codes:
        0: Upgrade successful
        1: Upgrade failed
    """
    try:
        context = discover_context()
        console = ConsoleOutput(quiet=quiet)

        console.info("\n→ Upgrading repository...\n")

        repository.upgrade_repository(context, quiet=quiet)

        console.success(
            "\n✓ Upgrade completed successfully!\n",
            fg=typer.colors.BRIGHT_GREEN,
            bold=True,
        )

    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)  # Always show errors
        console_err.error(f"\n✗ Upgrade failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e


@model_app.command("create")
def model_create(
    name: Annotated[str, typer.Argument(help="Name of the model to create")],
    config_file: Annotated[
        Path | None,
        typer.Argument(
            help=(
                "Optional YAML file whose content seeds all answers "
                "non-interactively (must supply model_name itself)"
            ),
        ),
    ] = None,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress output from subprocesses (copier, invenio-cli, etc.)",
        ),
    ] = False,
) -> None:
    """Create a new record model from the configured model copier template.

    See ``services.models.ModelManager.create_model`` for the individual steps.

    Examples:
        $ oarepo-cli repository model create my_model
        $ oarepo-cli repository model create my_model model_config.yaml

    Exit codes:
        0: Model created successfully
        1: Model creation failed
    """
    try:
        context = discover_context()
        console = ConsoleOutput(quiet=quiet)
        ModelManager(context, console).create_model(name, config_file=config_file)
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)  # Always show errors
        console_err.error(f"\n✗ Model creation failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e


@model_app.command("update")
def model_update(
    name: Annotated[str, typer.Argument(help="Name of the model to update")],
    answers_file: Annotated[
        Path | None,
        typer.Argument(
            help=(
                "Optional YAML answers file to update from (defaults to the "
                "model's recorded models/<name>/.copier-answers.yml)"
            ),
        ),
    ] = None,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress output from subprocesses (copier, invenio-cli, etc.)",
        ),
    ] = False,
) -> None:
    """Update an existing record model from its recorded (or given) template answers.

    See ``services.models.ModelManager.update_model`` for the individual steps.

    Examples:
        $ oarepo-cli repository model update my_model
        $ oarepo-cli repository model update my_model model_config.yaml

    Exit codes:
        0: Model updated successfully
        1: Model update failed
    """
    try:
        context = discover_context()
        console = ConsoleOutput(quiet=quiet)
        ModelManager(context, console).update_model(name, answers_file=answers_file)
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)  # Always show errors
        console_err.error(f"\n✗ Model update failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e


@local_app.command("add")
def local_add(
    path: Annotated[Path, typer.Argument(help="Path to the local package's own project directory")],
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress output from subprocesses (invenio-cli, etc.)",
        ),
    ] = False,
) -> None:
    r"""Add a local, editable package to \[tool.uv.sources].

    See ``services.local_packages.LocalPackageManager.add_package`` for the
    individual steps.

    Examples:
        $ oarepo-cli repository local add ../my-local-package

    Exit codes:
        0: Package added successfully
        1: Package addition failed
    """
    try:
        context = discover_context()
        console = ConsoleOutput(quiet=quiet)
        LocalPackageManager(context, console).add_package(path)
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)  # Always show errors
        console_err.error(f"\n✗ Local package addition failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e


@local_app.command("remove")
def local_remove(
    name: Annotated[str | None, typer.Argument(help="Name of the local package to remove")] = None,
    all_packages: Annotated[bool, typer.Option("--all", help="Remove all local packages")] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress output from subprocesses (invenio-cli, etc.)",
        ),
    ] = False,
) -> None:
    r"""Remove a local package from \[tool.uv.sources], or all of them with --all.

    See ``services.local_packages.LocalPackageManager.remove_package``/
    ``remove_all_packages`` for the individual steps.

    Examples:
        $ oarepo-cli repository local remove my-package
        $ oarepo-cli repository local remove --all

    Exit codes:
        0: Package(s) removed successfully
        1: Removal failed (e.g. unknown package name, neither/both of a name
           and --all given)
    """
    if name is None and not all_packages:
        console_err = ConsoleOutput(quiet=False)
        console_err.error("\n✗ Specify a package name to remove, or --all.\n", fg=typer.colors.RED)
        raise typer.Exit(1)
    if name is not None and all_packages:
        console_err = ConsoleOutput(quiet=False)
        console_err.error(
            "\n✗ Specify either a package name or --all, not both.\n", fg=typer.colors.RED
        )
        raise typer.Exit(1)

    try:
        context = discover_context()
        console = ConsoleOutput(quiet=quiet)
        manager = LocalPackageManager(context, console)
        if all_packages:
            manager.remove_all_packages()
        elif name is not None:
            manager.remove_package(name)
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)  # Always show errors
        console_err.error(f"\n✗ Local package removal failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e


@repository_app.command("run", context_settings=_RUN_CONTEXT_SETTINGS)
def run_command(
    ctx: typer.Context,
    no_services: Annotated[
        bool,
        typer.Option("--no-services", help="Don't start Docker services first"),
    ] = False,
    no_celery: Annotated[
        bool,
        typer.Option(
            "--no-celery",
            help="Run the venv's own `invenio run` directly, without Celery/invenio-cli",
        ),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress output from starting Docker services",
        ),
    ] = False,
) -> None:
    """Start the repository's development server.

    See ``services.server.ServerRunner.run`` for the individual steps. Any
    extra arguments/options (e.g. ``-p 5001``) are forwarded to the
    underlying ``invenio-cli run``/``invenio run`` command.

    This command replaces the current process (``os.execve``/``os.execvpe``)
    with the server once Docker services are started -- it never returns on
    success, so a terminal Ctrl+C hits invenio-cli/invenio directly, exactly
    as if it had been run directly.

    Examples:
        $ oarepo-cli repository run
        $ oarepo-cli repository run --no-services
        $ oarepo-cli repository run --no-celery -- -p 5001

    Exit codes:
        Whatever invenio-cli/invenio itself exits with, once running
        1: Starting Docker services failed, or project context could not be
           discovered
    """
    try:
        context = discover_context()
        ServerRunner(context, quiet=quiet).run(
            no_services=no_services,
            no_celery=no_celery,
            extra_args=ctx.args,
        )
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)  # Always show errors
        console_err.error(f"\n✗ Failed to start server: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e


@repository_app.command("cli", context_settings=_SERVICES_CONTEXT_SETTINGS)
def cli_command(ctx: typer.Context) -> None:
    """Run an arbitrary invenio-cli command in the repository.

    Pure passthrough to invenio-cli: replaces this process (``os.execve``/
    ``os.execvpe``) with ``invenio-cli <args>``, so ``--help`` reaches
    invenio-cli's own help (not oarepo-cli's), and the exit code is
    preserved exactly.

    Examples:
        $ oarepo-cli repository cli services status
        $ oarepo-cli repository cli --help

    Exit codes:
        Whatever invenio-cli itself exits with
        1: Project context could not be discovered
    """
    try:
        context = discover_context()
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)
        console_err.error(f"\n✗ repository cli failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e

    invenio_cli.exec_invenio_cli(context, ctx.args)


@repository_app.command("invenio", context_settings=_SERVICES_CONTEXT_SETTINGS)
def invenio_command(ctx: typer.Context) -> None:
    """Run an arbitrary bare invenio command in the repository's virtual environment.

    Pure passthrough to the venv's own ``invenio`` binary (not
    ``invenio-cli`` -- see ``repository cli`` for that): replaces this
    process (``os.execve``) with ``invenio <args>``, so ``--help`` reaches
    invenio's own help (not oarepo-cli's), and the exit code is preserved
    exactly.

    Examples:
        $ oarepo-cli repository invenio db upgrade
        $ oarepo-cli repository invenio --help

    Exit codes:
        Whatever invenio itself exits with
        1: Project context could not be discovered
    """
    try:
        context = discover_context()
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)
        console_err.error(f"\n✗ repository invenio failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e

    repository.exec_invenio(context, ctx.args)


@repository_app.command("shell")
def shell_command(
    no_services: Annotated[
        bool,
        typer.Option("--no-services", help="Don't start Docker services first"),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress output from starting Docker services",
        ),
    ] = False,
) -> None:
    """Start an interactive bash shell in the repository's virtual environment.

    Opens a bash shell with the virtual environment activated. By default,
    Docker services are started first (via ``invenio-cli services start``,
    like ``repository run``) -- use ``--no-services`` to skip, e.g. if
    they're already running.

    Unlike ``library shell``, no environment variables are loaded from an
    ``.env-services`` file: a repository resolves its own service
    connection details from ``invenio.cfg``/``.invenio.private`` instead.

    This command replaces the current process (``os.execve``) with the
    shell -- it never returns on success.

    Examples:
        $ oarepo-cli repository shell
        $ oarepo-cli repository shell --no-services

    Exit codes:
        Whatever the shell itself exits with
        1: Starting Docker services failed, or project context could not be
           discovered
    """
    try:
        context = discover_context()

        console = ConsoleOutput(quiet=quiet)
        if not no_services:
            console.info("→ Starting Docker services...\n")
            invenio_cli.run_invenio_cli(context, ["services", "start"], quiet=quiet)

        console.info("→ Starting bash shell in virtual environment...\n")
        console.info("  Type 'exit' or press Ctrl+D to exit the shell.\n")

        repository.exec_shell(context)
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)  # Always show errors
        console_err.error(f"\n✗ repository shell failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e


@repository_app.command("lint")
def lint_command(
    fix: Annotated[
        bool,
        typer.Option(
            "--fix/--no-fix", help="Auto-fix what ruff/ty can fix (default) vs. report only"
        ),
    ] = True,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress output from subprocesses")
    ] = False,
) -> None:
    """Run linters and type checkers on the repository's codebase.

    Runs, in order, stopping at the first failure: ruff check, ruff format,
    a license header check, a ``from __future__ import annotations`` check,
    and ty check, across every module directory declared in
    ``[tool.uv.build-backend]`` (or ``src/``/the flat layout, if used
    instead). Generates ``.ruff.toml`` and ``ty.toml`` config files in the
    project root.

    By default (``--fix``), auto-fixes what ruff and ty can fix (``ruff
    check --fix``, ``ruff format``, ``ty check --fix``) instead of only
    reporting. Use ``--no-fix`` (or ``repository check``, its dedicated
    read-only equivalent) to never modify any file.

    Exit codes:
        Exit code of the first failing check
        1: Project context could not be discovered
    """
    try:
        context = discover_context()
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)
        console_err.error(f"\n✗ repository lint failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e

    lint_commands.run_lint(context, fix=fix, quiet=quiet)


@repository_app.command(
    "format",
    context_settings={
        "allow_extra_args": True,
        "allow_interspersed_args": True,
        "ignore_unknown_options": True,
    },
)
def format_command(
    ctx: typer.Context,
    fix: Annotated[
        bool,
        typer.Option(
            "--fix/--no-fix",
            help="Rewrite files (default) vs. preview-only (`ruff format --check`)",
        ),
    ] = True,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress output from subprocesses")
    ] = False,
) -> None:
    """Format the repository's codebase using ruff.

    By default (``--fix``), runs ``ruff format`` followed by ``ruff check
    --fix``, rewriting files. Use ``--no-fix`` for a preview-only run
    (``ruff format --check``, nothing written) -- or ``repository check``,
    its dedicated read-only equivalent.

    Any additional arguments are passed directly to the ruff invocation(s).

    Examples:
        $ oarepo-cli repository format
        $ oarepo-cli repository format --no-fix

    Exit codes:
        Exit code of the underlying ruff invocation
        1: Project context could not be discovered
    """
    extra_args = ctx.args if ctx.args else []

    try:
        context = discover_context()
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)
        console_err.error(f"\n✗ repository format failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e

    lint_commands.run_format(context, fix=fix, extra_args=extra_args, quiet=quiet)


@repository_app.command("check")
def check_command(
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress output from subprocesses")
    ] = False,
) -> None:
    """Check the repository's codebase without modifying any file.

    The read-only equivalent of ``repository lint``/``repository format``:
    runs ruff check, ruff format --check, a license header check, a
    ``from __future__ import annotations`` check, and ty check -- none of
    them applying fixes. Equivalent to ``repository lint --no-fix``,
    provided as its own command as the safe-for-CI entry point. Still
    generates ``.ruff.toml``/``ty.toml`` config files in the project root
    (that's config generation, not modifying target project source).

    Exit codes:
        Exit code of the first failing check
        1: Project context could not be discovered
    """
    try:
        context = discover_context()
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)
        console_err.error(f"\n✗ repository check failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e

    lint_commands.run_check(context, quiet=quiet)


@repository_app.command("jslint")
def jslint_command(
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress output from subprocesses")
    ] = False,
) -> None:
    """Run ESLint and Prettier on the repository's JavaScript files.

    Installs necessary dependencies if needed
    (``@inveniosoftware/eslint-config-invenio``), generates
    ``.eslintrc.yaml`` configuration, runs eslint with ``--fix`` to
    auto-fix issues, and runs prettier to format code.

    In CI environments (``CI=true``), prettier runs in check mode
    (``--check``) instead of write mode (``--write``).

    Skips entirely if no ``package.json`` is found at the repository root
    (JS assets are optional for a repository).

    Exit codes:
        Exit code of the underlying eslint/prettier invocation
        1: Project context could not be discovered
    """
    try:
        context = discover_context()
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)
        console_err.error(f"\n✗ repository jslint failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e

    js_commands.run_jslint_command(context, quiet=quiet)


@repository_app.command(
    "jstest",
    context_settings={
        "allow_extra_args": True,
        "allow_interspersed_args": True,
        "ignore_unknown_options": True,
    },
)
def jstest_command(
    ctx: typer.Context,
    setup: Annotated[
        bool, typer.Option("--setup", help="Set up Jest configuration instead of running tests")
    ] = False,
    skip_services: Annotated[
        bool, typer.Option("--skip-services", help="Skip starting Docker services")
    ] = False,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress output from subprocesses")
    ] = False,
) -> None:
    """Run JavaScript tests (Jest) via ``invenio webpack``.

    Runs Jest tests through ``invenio webpack run test``, collecting every
    registered ``invenio_assets.webpack`` entry point -- including the
    repository's own (see ``[project.entry-points."invenio_assets.webpack"]``
    in ``pyproject.toml``), same as for a library. Requires the repository
    to already be installed (``repository install``), so its webpack build
    exists.

    Use ``--setup`` to set up the Jest configuration (currently delegates
    to bash script). By default, starts Docker services if needed. Use
    ``--skip-services`` to skip service startup.

    Any additional arguments are passed directly to the test command.

    Exit codes:
        Exit code of the underlying test command
        1: Project context could not be discovered
    """
    extra_args = ctx.args if ctx.args else []

    try:
        context = discover_context()

        console = ConsoleOutput(quiet=quiet)
        if not skip_services:
            console.info("→ Starting Docker services...\n")
            invenio_cli.run_invenio_cli(context, ["services", "start"], quiet=quiet)

        # A repository doesn't need service connection env vars -- it resolves
        # connection details from invenio.cfg/.invenio.private, not from the
        # .env-services file docker-services-cli would write for a library
        js_commands.run_jstest_command(
            context, setup=setup, service_env=None, extra_args=extra_args, quiet=quiet
        )
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)
        console_err.error(f"\n✗ repository jstest failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e


@repository_app.command(
    "test",
    context_settings={
        "allow_extra_args": True,
        "allow_interspersed_args": True,
        "ignore_unknown_options": True,
    },
)
def test_command(
    ctx: typer.Context,
    no_services: Annotated[
        bool,
        typer.Option("--no-services", help="Don't start Docker services first"),
    ] = False,
    with_coverage: Annotated[
        bool, typer.Option("--with-coverage", help="Enable coverage reporting")
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress output from starting Docker services",
        ),
    ] = False,
) -> None:
    """Run the repository's test suite using pytest.

    By default, Docker services are started first (via ``invenio-cli
    services start``, like ``repository run``/``shell``) -- use
    ``--no-services`` to skip, e.g. if they're already running. Unlike
    ``library test``, services are never stopped afterward, matching every
    other ``repository`` command.

    Use ``--with-coverage`` to generate coverage reports (HTML and
    terminal), covering every module directory (see ``repository lint``)
    rather than a single package.

    Any additional arguments are passed directly to pytest.

    This command replaces the current process (``os.execve``) with pytest
    once dependencies are installed -- it never returns on success.

    Examples:
        $ oarepo-cli repository test
        $ oarepo-cli repository test --with-coverage
        $ oarepo-cli repository test --no-services
        $ oarepo-cli repository test -v -k test_specific

    Exit codes:
        Whatever pytest itself exits with
        1: Starting Docker services failed, installing pytest/pytest-cov
           failed, or project context could not be discovered
    """
    pytest_args = ctx.args if ctx.args else []

    try:
        context = discover_context()

        console = ConsoleOutput(quiet=quiet)
        if not no_services:
            console.info("→ Starting Docker services...\n")
            invenio_cli.run_invenio_cli(context, ["services", "start"], quiet=quiet)

        console.info("→ Running tests...\n")
        # run_tests() installs pytest/pytest-cov if missing (can raise
        # ProcessExecutionError, caught below) before exec'ing into pytest --
        # unlike a pure passthrough, there's real pre-exec work here that
        # needs this try/except, so the call stays inside it.
        repository.run_tests(context, pytest_args=pytest_args, coverage=with_coverage, quiet=quiet)
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)  # Always show errors
        console_err.error(f"\n✗ repository test failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e


@repository_app.command("translations", context_settings=_SERVICES_CONTEXT_SETTINGS)
def translations_command(
    ctx: typer.Context,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress output from subprocesses")
    ] = False,
) -> None:
    """Extract, merge and compile translations (BE + JS) via oarepo-tools.

    Mirrors ``repository_runner.sh``'s ``translations()``: ``repository
    translations compile`` delegates to ``invenio-cli translations compile``
    (backend only, no extraction); any other invocation (including no args)
    runs oarepo-tools' ``make-translations``, with all given args forwarded
    to it verbatim.

    Examples:
        $ oarepo-cli repository translations
        $ oarepo-cli repository translations compile

    Exit codes:
        0: Success
        1: Failure (translations compile/make-translations failed, or
           project context could not be discovered)
    """
    try:
        context = discover_context()
        if ctx.args and ctx.args[0] == "compile":
            invenio_cli.run_invenio_cli(context, ["translations", "compile"], quiet=quiet)
        else:
            translations.run_translations(context, extra_args=ctx.args, quiet=quiet).check()
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)
        console_err.error(f"\n✗ Translations failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e


@index_app.command("rebuild")
def index_rebuild(
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress output from subprocesses")
    ] = False,
) -> None:
    """Destroy and rebuild the search index (and custom fields).

    See ``services.repository.rebuild_index`` for the individual steps.

    Exit codes:
        0: Success
        1: Failure (a step failed, or project context could not be discovered)
    """
    try:
        context = discover_context()
        repository.rebuild_index(context, quiet=quiet)
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)
        console_err.error(f"\n✗ Index rebuild failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e


@repository_app.command("reset")
def reset_command(
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress output from subprocesses")
    ] = False,
) -> None:
    """Perform a full reset of the repository: wipe all data, reinstall, and reseed demo data.

    See ``services.repository.reset_repository`` for the individual steps.
    Prompts for confirmation (exactly ``yes``) before proceeding, since this
    **PURGES ALL EXISTING DATA** in your containers, mirroring
    ``repository_runner.sh``'s ``reset_repository()``.

    Examples:
        $ oarepo-cli repository reset

    Exit codes:
        0: Reset completed, or cancelled by the user
        1: Reset failed partway through, or project context could not be
           discovered
    """
    console = ConsoleOutput(quiet=False)
    console.warning("\n⚠️  Performing full reset of the repository...\n")
    console.info("This will remove all data, virtual environment, and reinstall the repository.")
    console.warning("Please make sure that server is not running at the moment\n")
    answer = typer.prompt("Are you sure you want to continue? (yes/no)")
    if answer != "yes":
        console.warning("Reset cancelled.\n")
        raise typer.Exit(0)

    try:
        context = discover_context()
        repository.reset_repository(context, quiet=quiet)
        console.success(
            "\n✓ Repository reset completed successfully.\n",
            fg=typer.colors.BRIGHT_GREEN,
            bold=True,
        )
        console.info(
            "Please run `oarepo-cli repository run` to start the server "
            "and wait for the initial data to be loaded.\n"
        )
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)
        console_err.error(f"\n✗ Reset failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e


@repository_app.command("info")
def info_command() -> None:
    """Show the resolved Python version and discovered record models.

    See ``services.repository.list_repository_models`` for model discovery.

    Exit codes:
        0: Success
        1: Project context could not be discovered
    """
    try:
        context = discover_context()
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)
        console_err.error(f"\n✗ repository info failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e

    typer.echo(f"Python version: {context.python_binary}")
    typer.echo(repository.get_python_version(context))
    typer.echo("")
    typer.echo("Models:")

    models = repository.list_repository_models(context)
    if not models:
        typer.echo("  No models found.")
    else:
        for model in models:
            typer.echo(f"  - {model.name}: {model.version}")
