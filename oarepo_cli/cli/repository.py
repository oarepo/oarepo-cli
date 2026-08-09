# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Repository commands for OARepo CLI."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from oarepo_cli.core.context import ProjectContext
    from oarepo_cli.ui import ConsoleOutput

import typer

from oarepo_cli.cli import js_commands, lint_commands
from oarepo_cli.cli.command_wrapper import with_context_and_console
from oarepo_cli.core.context import discover_context
from oarepo_cli.core.errors import OARepoError
from oarepo_cli.services import invenio_cli, repository, translations
from oarepo_cli.services.alembic import AlembicManager
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

# Create the alembic subcommand group
alembic_app = typer.Typer(
    name="alembic",
    help="Alembic migration management",
    no_args_is_help=True,
)

# Register services, model, local, index, and alembic as subcommands of repository
repository_app.add_typer(services_app)
repository_app.add_typer(model_app)
repository_app.add_typer(local_app)
repository_app.add_typer(index_app)
repository_app.add_typer(alembic_app)

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


@alembic_app.callback()
def alembic_callback() -> None:
    """Repository alembic migration command group."""


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
    extra_args = ctx.args or []

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
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output from invenio-cli")] = False,
) -> None:
    """Set up Docker services.

    Delegates to ``invenio-cli services setup``. Any extra arguments
    (e.g. ``-N`` for no demo data) are passed through verbatim.
    """
    _run_services_subcommand(ctx, "setup", quiet=quiet)


@services_app.command("start", context_settings=_SERVICES_CONTEXT_SETTINGS)
def services_start(
    ctx: typer.Context,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output from invenio-cli")] = False,
) -> None:
    """Start Docker services.

    Delegates to ``invenio-cli services start``. Any extra arguments are
    passed through verbatim.
    """
    _run_services_subcommand(ctx, "start", quiet=quiet)


@services_app.command("stop", context_settings=_SERVICES_CONTEXT_SETTINGS)
def services_stop(
    ctx: typer.Context,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output from invenio-cli")] = False,
) -> None:
    """Stop Docker services.

    Delegates to ``invenio-cli services stop``. Any extra arguments are
    passed through verbatim.
    """
    _run_services_subcommand(ctx, "stop", quiet=quiet)


@services_app.command("destroy", context_settings=_SERVICES_CONTEXT_SETTINGS)
def services_destroy(
    ctx: typer.Context,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output from invenio-cli")] = False,
) -> None:
    """Destroy Docker services.

    Delegates to ``invenio-cli services destroy``. Any extra arguments are
    passed through verbatim.
    """
    _run_services_subcommand(ctx, "destroy", quiet=quiet)


@with_context_and_console(
    success_message="Repository installed successfully!",
    error_prefix="Error installing repository",
)
def _install_impl(
    context: ProjectContext,
    console: ConsoleOutput,  # noqa: ARG001
    *,
    quiet: bool = False,
) -> None:
    """Implement repository install command.

    Args:
        context: Project context (injected by decorator)
        console: Console output handler (injected by decorator)
        quiet: If True, suppress output from subprocesses (uv, invenio-cli, etc.)

    """
    repository.install_repository(context, quiet=quiet)


@repository_app.command("install", context_settings=_SERVICES_CONTEXT_SETTINGS)
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
    _install_impl(quiet=quiet)


@with_context_and_console(
    success_message="Repository upgraded successfully!",
    error_prefix="Error upgrading repository",
)
def _upgrade_impl(
    context: ProjectContext,
    console: ConsoleOutput,  # noqa: ARG001
    *,
    quiet: bool = False,
) -> None:
    """Implement repository upgrade command.

    Args:
        context: Project context (injected by decorator)
        console: Console output handler (injected by decorator)
        quiet: If True, suppress output from subprocesses (uv, invenio-cli, etc.)

    """
    repository.upgrade_repository(context, quiet=quiet)


@repository_app.command("upgrade", context_settings=_SERVICES_CONTEXT_SETTINGS)
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
    _upgrade_impl(quiet=quiet)


@with_context_and_console(
    success_message="Model created successfully!",
    error_prefix="Error creating model",
)
def _model_create_impl(
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    name: str,
    config_file: Path | None = None,
    quiet: bool = False,  # noqa: ARG001
) -> None:
    """Implement repository model create command.

    Args:
        context: Project context (injected by decorator)
        console: Console output handler (injected by decorator)
        name: Name of the model to create
        config_file: Optional YAML file whose content seeds all answers non-interactively
        quiet: If True, suppress output from subprocesses (copier, invenio-cli, etc.)

    """
    ModelManager(context, console).create_model(name, config_file=config_file)


@model_app.command("create")
def model_create(
    name: Annotated[str, typer.Argument(help="Name of the model to create")],
    config_file: Annotated[
        Path | None,
        typer.Argument(
            help=(
                "Optional YAML file whose content seeds all answers non-interactively (must supply model_name itself)"
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
    _model_create_impl(name=name, config_file=config_file, quiet=quiet)


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
        console_err.error("\n✗ Specify either a package name or --all, not both.\n", fg=typer.colors.RED)
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
        typer.Option("--fix/--no-fix", help="Auto-fix what ruff/ty can fix (default) vs. report only"),
    ] = True,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output from subprocesses")] = False,
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
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output from subprocesses")] = False,
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
    extra_args = ctx.args or []

    try:
        context = discover_context()
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)
        console_err.error(f"\n✗ repository format failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e

    lint_commands.run_format(context, fix=fix, extra_args=extra_args, quiet=quiet)


@repository_app.command("check")
def check_command(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output from subprocesses")] = False,
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
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output from subprocesses")] = False,
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

    js_commands.run_repository_jslint_command(context, quiet=quiet)


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
    setup: Annotated[bool, typer.Option("--setup", help="Set up Jest configuration instead of running tests")] = False,
    skip_services: Annotated[bool, typer.Option("--skip-services", help="Skip starting Docker services")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output from subprocesses")] = False,
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
    extra_args = ctx.args or []

    try:
        context = discover_context()

        console = ConsoleOutput(quiet=quiet)
        if not skip_services:
            console.info("→ Starting Docker services...\n")
            invenio_cli.run_invenio_cli(context, ["services", "start"], quiet=quiet)

        # A repository doesn't need service connection env vars -- it resolves
        # connection details from invenio.cfg/.invenio.private, not from the
        # .env-services file docker-services-cli would write for a library
        js_commands.run_jstest_command(context, setup=setup, service_env=None, extra_args=extra_args, quiet=quiet)
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
    ],
    with_coverage: Annotated[bool, typer.Option("--with-coverage", help="Enable coverage reporting")],
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress output from starting Docker services",
        ),
    ],
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
    pytest_args = ctx.args or []

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
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output from subprocesses")] = False,
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
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output from subprocesses")] = False,
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
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output from subprocesses")] = False,
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
            "Please run `oarepo-cli repository run` to start the server and wait for the initial data to be loaded.\n"
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


@with_context_and_console(
    start_message="Initializing Alembic support...",
    error_prefix="Error initializing Alembic",
)
def _alembic_init_impl(
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    quiet: bool = False,  # noqa: ARG001 (used by decorator to control console output)
) -> None:
    """Initialize Alembic support for the repository.

    Initializes Alembic support in the common/alembic directory including creating
    migrations and setting up the database schema. After completion, instructs the
    user to review the generated migration files.

    Args:
        context: Project context (injected by decorator)
        console: Console output handler (injected by decorator)
        quiet: Suppress command output (passed from CLI, used by decorator)

    """
    from pathlib import Path

    manager = AlembicManager(context, console)
    manager.init(Path("common/alembic"), verify_model_entrypoint=False)


@with_context_and_console(
    start_message="Creating alembic migration...",
    error_prefix="Error creating alembic migration",
)
def _alembic_revision_impl(
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    message: str,
    quiet: bool = False,  # noqa: ARG001 (used by decorator to control console output)
) -> bool:
    """Create an Alembic revision for the repository.

    Creates an Alembic revision with the given message in the common/alembic directory.

    Args:
        context: Project context (injected by decorator)
        console: Console output handler (injected by decorator)
        message: Revision message to use
        quiet: Suppress command output (passed from CLI, used by decorator)

    Returns:
        bool: True if revision was created successfully, False otherwise

    """
    from pathlib import Path

    manager = AlembicManager(context, console)
    return manager.revision(message=message, alembic_path=Path("common/alembic"))


@alembic_app.command("init")
def alembic_init(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Initialize Alembic support for the repository.

    This command initializes Alembic support in the common/alembic directory and
    performs the following steps:
    1. Checks for the required 'invenio_db.models' entrypoint in pyproject.toml
    2. Creates the 'common/alembic' directory if it doesn't exist
    3. Adds the 'invenio_db.alembic' entrypoint to pyproject.toml if missing
    4. Checks if alembic is already initialized (exits early if 2+ migrations exist)
    5. Syncs the project to register entrypoints (uv pip install --no-deps -e .)
    6. Restarts Docker services to ensure clean database state
    7. Verifies alembic state is clean (no uncommitted database changes)
    8. Creates initial branch migration if no Python files exist in common/alembic/
    9. Runs 'invenio alembic upgrade heads' to apply base migrations
    10. Creates migration for initial database tables

    After completion, you should carefully review the generated migration file
    to ensure it contains only the intended table changes for your models.

    The 'invenio_db.models' entrypoint is required for Alembic support and should
    point to your database models module. If it's missing, the command will exit
    with an error and provide an example configuration.

    Note: This command requires Docker services to be available and will restart
    them to ensure a clean database state.

    Example:
        oarepo-cli repository alembic init
        oarepo-cli repository alembic init --quiet

    """
    _alembic_init_impl(quiet=quiet)


@alembic_app.command("revision")
def alembic_revision(
    message: Annotated[str, typer.Argument(help="Revision message")],
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Add a new Alembic revision.

    This command performs the following steps:

    1. If there is no alembic support yet, print message and exit 1
    2. Restarts Docker services to ensure clean database state
    3. Performs alembic upgrade heads
    4. Creates alembic migration in common/alembic

    After completion, you should carefully review the generated migration file
    to ensure it contains only the intended table changes for your models.

    Example:
        oarepo-cli repository alembic revision "Add user table"

    """
    if not _alembic_revision_impl(message=message, quiet=quiet):
        raise typer.Exit(1)


@with_context_and_console(
    start_message="Applying pending migrations...",
    error_prefix="Error applying migrations",
)
def _alembic_apply_impl(
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    quiet: bool = False,  # noqa: ARG001 (used by decorator to control console output)
) -> None:
    """Apply all pending Alembic migrations.

    Runs 'invenio alembic upgrade heads' to apply all pending migrations to the database.
    Restarts Docker services to ensure a clean state before applying migrations.

    Args:
        context: Project context (injected by decorator)
        console: Console output handler (injected by decorator)
        quiet: Suppress command output (passed from CLI, used by decorator)

    """
    manager = AlembicManager(context, console)
    manager.apply()


@alembic_app.command("apply")
def alembic_apply(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Apply all pending Alembic migrations.

    This command upgrades the database to the latest migration head by running
    'invenio alembic upgrade heads'. It restarts Docker services to ensure a clean
    state before applying migrations.

    Use this command when:
    - You have new migration files and want to apply them to the database
    - The database schema is out of sync with the latest migrations
    - You want to ensure all pending migrations are applied

    Note: This command requires Docker services to be available and will restart
    them to ensure a clean database state.

    Example:
        oarepo-cli repository alembic apply
        oarepo-cli repository alembic apply --quiet

    """
    _alembic_apply_impl(quiet=quiet)


@with_context_and_console(
    start_message="Stamping database...",
    error_prefix="Error stamping database",
)
def _alembic_stamp_impl(
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    revision: str,
    quiet: bool = False,  # noqa: ARG001 (used by decorator to control console output)
) -> None:
    """Stamp the database with a specific revision.

    Sets the current database schema version to the specified revision without
    actually running any migration scripts. This is useful when migrations have
    been applied manually or externally and you need to sync the database state
    with the codebase.

    Args:
        context: Project context (injected by decorator)
        console: Console output handler (injected by decorator)
        revision: The revision identifier to stamp (e.g., 'head', 'base', or a specific revision ID)
        quiet: Suppress command output (passed from CLI, used by decorator)

    """
    manager = AlembicManager(context, console)
    manager.stamp(revision)


@alembic_app.command("stamp")
def alembic_stamp(
    revision: Annotated[str, typer.Argument(help="Revision to stamp (e.g., 'head', 'base', or specific revision ID)")],
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Stamp the database with a specific revision.

    This command sets the current database schema version to the specified revision
    without actually running any migration scripts. The database schema remains unchanged,
    but Alembic will recognize it as being at the specified revision.

    Common use cases:
    - Syncing database state after manual schema changes
    - Marking the database as already having certain migrations applied
    - Resetting the migration history without dropping tables
    - Setting the database to 'base' (no migrations) or 'head' (latest migration)

    Common revision identifiers:
    - 'head' - The latest migration
    - 'base' - No migrations applied
    - A specific revision ID (e.g., 'abc123def456')

    Warning: Use this command with caution. Stamping the database with an incorrect
    revision can lead to inconsistencies between the actual schema and what Alembic
    believes has been applied.

    Example:
        oarepo-cli repository alembic stamp head
        oarepo-cli repository alembic stamp base
        oarepo-cli repository alembic stamp abc123def456

    """
    _alembic_stamp_impl(revision=revision, quiet=quiet)


def _alembic_check_impl(
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    sql: bool = False,
) -> int:
    """Check for pending database migrations.

    Runs the check_migrations.py script to compare the current database schema
    against the model metadata and detect any pending migrations.

    Args:
        context: Project context with paths and configuration
        console: Console output handler
        sql: If True, output SQL statements instead of JSON

    Returns:
        Exit code: 0 if no migrations needed, 1 if pending migrations detected

    """
    manager = AlembicManager(context, console)
    return manager.check(sql=sql)


@alembic_app.command("check")
def alembic_check(
    sql_mode: Annotated[
        bool,
        typer.Option("--sql", help="Output SQL statements instead of JSON"),
    ] = False,
) -> None:
    """Check for pending database migrations.

    Compares the current database schema against the model metadata to detect
    any pending migrations that haven't been applied yet.

    Exit codes:
        0: No pending migrations (database is up to date)
        1: Pending migrations detected or error occurred

    Examples:
        # Check for pending migrations (JSON output)
        oarepo-cli repository alembic check

        # Check and see SQL statements for pending migrations
        oarepo-cli repository alembic check sql

    """
    try:
        context = discover_context()
    except OARepoError as e:
        console_err = ConsoleOutput(quiet=False)
        console_err.error(f"\n✗ Failed to discover project context: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e

    exit_code = _alembic_check_impl(context, ConsoleOutput(quiet=False), sql=bool(sql_mode))
    raise typer.Exit(code=exit_code)
