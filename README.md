# OARepo CLI

A standalone Python command-line tool for OARepo library and repository development. Replaces the legacy bash scripts (`library_runner.sh`, `repository_runner.sh`, `repository_installer.sh`) with a robust, maintainable CLI built with Python and Typer.

## Overview

`oarepo-cli` provides two main command groups, plus a top-level convenience command:

- **`library`**: Tools for developing OARepo library packages (models, modules, extensions)
- **`repository`**: Tools for managing full OARepo repository instances
- **`repo-install`**: Scaffold a brand-new repository from a copier template (see [Repository Installer](#repository-installer))

The CLI handles virtual environment management, dependency installation, Docker service orchestration, testing, linting, formatting, and more—all while preserving the familiar workflows from the original bash scripts.

### Key Features

- **Zero shell injection risk**: All subprocess calls use explicit argument lists, never `shell=True`
- **Standard Python packaging**: Works with `pyproject.toml` (PEP 621) and uses `uv` for fast dependency resolution
- **Virtual environment management**: Automatic venv creation, validation, and dependency synchronization
- **Docker service integration**: Manages PostgreSQL, OpenSearch, Redis, RabbitMQ, and MinIO via `docker-services-cli`
- **Multi-version support**: Automatically detects OARepo versions from dependency constraints
- **Cross-platform**: Works on macOS, Linux, and Windows with platform-specific optimizations

### Installation

#### For Library Development (Recommended)

The recommended way to use `oarepo-cli` for library development is via the wrapper script. This approach:
- Isolates `oarepo-cli` in a local `.tools/venv` directory per project
- Auto-installs on first run
- Matches the familiar `./run.sh` pattern from the old bash scripts

**Setup:**
```bash
# Copy the wrapper script to your library root
curl -o run.sh https://raw.githubusercontent.com/oarepo/oarepo-cli/main/scripts/library_run.sh
chmod +x ./run.sh

# First run automatically sets up .tools/venv and installs oarepo-cli
./run.sh venv

# All subsequent commands work the same
./run.sh test
./run.sh lint
```

**Update the wrapper's CLI version:**
```bash
./run.sh self-update
```

This removes `.tools/venv` and reinstalls the latest `oarepo-cli` on the next run.

#### Global Installation

For repository management or if you prefer a global installation:

```bash
pip install oarepo-cli
```

Or with `uv`:

```bash
uv pip install oarepo-cli
```

## Library Tools

The `library` subcommand provides development tools for OARepo library packages.

**Note:** All examples below use `./run.sh <command>` (the recommended wrapper script). If you installed `oarepo-cli` globally, use `oarepo-cli library <command>` instead.

### Command Overview

| Command | Description | Key Options |
|---------|-------------|-------------|
| [`venv`](#library-venv) | Set up virtual environment | `--force`, `--no-editable` |
| [`install`](#library-install) | Alias for `venv` | Same as `venv` |
| [`upgrade`](#library-upgrade) | Clean cache and recreate venv | None |
| [`test`](#library-test) | Run pytest tests | `--skip-services`, `--with-coverage` |
| [`start`](#library-start--library-stop) | Start Docker services | None |
| [`stop`](#library-start--library-stop) | Stop Docker services | None |
| [`lint`](#library-lint) | Run linters and type checkers | `--fix` / `--no-fix` (default: `--fix`) |
| [`format`](#library-format) | Format code with ruff | `--fix` / `--no-fix` (default: `--fix`) |
| [`check`](#library-check) | Read-only lint + format | None |
| [`shell`](#library-shell) | Open bash shell in venv | `--skip-services` |
| [`invenio`](#library-invenio) | Run invenio commands | `--skip-services` |
| [`translations`](#library-translations) | Extract/compile translations | None |
| [`license-headers`](#library-license-headers) | Add MIT license headers | None |
| [`jslint`](#library-jslint) | Run ESLint and Prettier | None |
| [`jstest`](#library-jstest) | Run JavaScript tests (Jest) | `setup`, `--skip-services` |
| [`oarepo-versions`](#library-oarepo-versions) | List OARepo and Python versions | None (outputs JSON) |
| [`clean`](#library-clean) | Remove venv and services | None |
| [`services`](#library-services) | Manage Docker services | `setup`, `start`, `stop`, `destroy` |

### `library venv`

Creates or verifies a Python virtual environment and installs all dependencies.

```bash
./run.sh venv
```

**Options:**
- `--force` / `-f`: Recreate venv from scratch (removes existing venv)
- `--no-editable`: Build and install a wheel instead of editable mode (`-e`)
- `--quiet` / `-q`: Suppress output messages

**What it does:**
1. Detects Python version from `requires-python` in `pyproject.toml`
2. Creates `.venv` directory (configurable via `OAREPO_VENV_PATH` or `[tool.oarepo-cli].venv.path`)
3. Installs dependencies using `uv sync` (fast, deterministic)
4. Installs the current project in editable mode (unless `--no-editable`)
5. Validates Python-OARepo version compatibility

**Examples:**
```bash
# Standard setup (editable mode)
./run.sh venv

# Force rebuild
./run.sh venv --force

# Build wheel instead
./run.sh venv --no-editable
```

### `library install`

Alias for `library venv`. Exists for compatibility with the old `./run.sh install` command.

```bash
./run.sh install
```

### `library upgrade`

Cleans the pip cache and recreates the virtual environment from scratch. Useful when dependencies change or you encounter caching issues.

```bash
./run.sh upgrade
```

**What it does:**
1. Runs `uv cache clean` to clear cached packages
2. Removes the existing `.venv` directory
3. Recreates venv and reinstalls all dependencies (equivalent to `venv --force`)

### `library test`

Runs pytest tests with optional coverage and Docker services.

```bash
./run.sh test
```

**Options:**
- `--skip-services`: Skip starting/stopping Docker services (faster for unit tests)
- `--with-coverage`: Generate coverage reports (HTML in `htmlcov/` and terminal output)
- `--quiet` / `-q`: Suppress service start/stop messages

**Additional pytest arguments** can be passed after the options:
```bash
./run.sh test -v tests/unit/
./run.sh test --with-coverage -x -k test_specific
./run.sh test --skip-services tests/unit/test_fast.py
```

**What it does:**
1. Ensures venv exists
2. Starts Docker services (unless `--skip-services`)
3. Runs `pytest` with coverage if requested
4. Stops Docker services (unless `--skip-services`)

### `library start` / `library stop`

Start or stop Docker services for development.

```bash
./run.sh start
./run.sh stop
```

**Services managed:**
- PostgreSQL (database)
- OpenSearch 2 (search engine)
- Redis (cache)
- RabbitMQ (message queue)
- MinIO (S3-compatible object storage)

Configuration is via `[tool.oarepo-cli].services` in `pyproject.toml` or environment variables (`OAREPO_SERVICES_*`).

**Example configuration:**
```toml
[tool.oarepo-cli.services]
db = "postgresql"
search = "opensearch2"
cache = "redis"
mq = "rabbitmq"
s3 = "minio"
```

### `library lint`

Runs linters and type checkers on the codebase. **By default, auto-fixes** what ruff and ty can fix.

```bash
./run.sh lint
```

**Options:**
- `--fix` / `--no-fix`: Auto-fix (default) vs. report-only mode
- `--quiet` / `-q`: Suppress output

**What it does (in order, stops at first failure):**
1. `ruff check --fix` (auto-fixes what it can)
2. `ruff format` (formats code)
3. License header check (read-only, use `license-headers` to fix)
4. `from __future__ import annotations` check (read-only)
5. `ty check --fix` (type checker with auto-fixes)

**Generates config files** in project root:
- `.ruff.toml` (ruff configuration)
- `ty.toml` (ty type checker configuration)

**Examples:**
```bash
# Auto-fix mode (default)
./run.sh lint

# Report-only mode (no modifications)
./run.sh lint --no-fix

# Quiet mode
./run.sh lint --quiet
```

### `library format`

Formats code using ruff. **By default, rewrites files**.

```bash
./run.sh format
```

**Options:**
- `--fix` / `--no-fix`: Rewrite files (default) vs. preview mode
- `--quiet` / `-q`: Suppress output

**What it does:**
- With `--fix` (default): Runs `ruff format` (rewrites files)
- With `--no-fix`: Runs `ruff format --check` (preview only, no changes)

### `library check`

Read-only combination of `lint` + `format` that **never modifies files**. Safe for CI/CD.

```bash
./run.sh check
```

**What it does (equivalent to `lint --no-fix` + `format --no-fix`):**
1. `ruff format --check` (preview formatting)
2. `ruff check` (no `--fix`)
3. License header check
4. `from __future__ import annotations` check
5. `ty check` (no `--fix`)

**Use this command in CI/CD pipelines** to verify code quality without modifying files.

### `library shell`

Opens an interactive bash shell in the project's virtual environment.

```bash
./run.sh shell
```

**Options:**
- `--skip-services`: Don't start Docker services before opening shell

**What it does:**
1. Ensures venv exists
2. Starts Docker services (unless `--skip-services`)
3. Opens bash shell with venv activated
4. On exit, stops Docker services (unless `--skip-services`)

**Example:**
```bash
# Shell with services
./run.sh shell

# Shell without services (faster)
./run.sh shell --skip-services
```

Inside the shell, you can run any command with the venv activated:
```bash
$ python --version
$ pip list
$ pytest tests/
$ invenio --help
```

### `library invenio`

Runs invenio CLI commands in the project's virtual environment.

```bash
./run.sh invenio [OPTIONS] [ARGS]...
```

**Options:**
- `--skip-services`: Don't start Docker services before running command

**Examples:**
```bash
# List invenio commands
./run.sh invenio --help

# Run database migrations
./run.sh invenio db create
./run.sh invenio db upgrade

# Create admin user
./run.sh invenio users create admin@example.com --password 123456 --active
```

### `library translations`

Extracts and compiles translations using `oarepo-tools make-translations`.

```bash
./run.sh translations
```

**What it does:**
1. Ensures venv exists
2. Runs `oarepo-tools make-translations` to extract translatable strings
3. Compiles `.po` files to `.mo` format

### `library license-headers`

Adds MIT license headers to Python files that are missing them.

```bash
./run.sh license-headers
```

**What it does:**
- Scans Python files in source directories
- Adds SPDX license header to files missing it:
  ```python
  # SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
  # SPDX-License-Identifier: MIT
  ```

**Configuration:**
- Organization name: `[tool.oarepo-cli].license.organization` (default: `"CESNET z.s.p.o"`)

### `library jslint`

Runs ESLint and Prettier on JavaScript files.

```bash
./run.sh jslint
```

**What it does:**
1. Ensures venv exists (for invenio webpack context)
2. Runs `invenio webpack create`
3. Runs `npm run lint` and `npm run prettier`

### `library jstest`

Runs JavaScript tests using Jest via invenio webpack.

```bash
./run.sh jstest [OPTIONS]
```

**Options:**
- `setup`: Run webpack setup before tests
- `--skip-services`: Don't start Docker services

**Examples:**
```bash
# Setup and run tests
./run.sh jstest setup

# Just run tests (assume webpack already set up)
./run.sh jstest

# Run without services
./run.sh jstest --skip-services
```

### `library oarepo-versions`

Lists supported OARepo and Python versions as JSON.

```bash
./run.sh oarepo-versions
```

**Output format:**
```json
{
  "oarepo_versions": ["14"],
  "python_versions": ["3.14"],
  "node_versions": ["24"]
}
```

**How OARepo versions are detected:**

The command automatically extracts OARepo major versions from dependency constraints in `pyproject.toml`:

```toml
[project.dependencies]
oarepo = ">=14.0.0,<15.0.0"  # Detected as version 14

[project.optional-dependencies]
dev = ["oarepo>=14.0.0,<15.0.0"]  # Also version 14
tests = ["oarepo>=13.0.0,<14.0.0"]  # Version 13
```

If multiple versions are detected, they are returned sorted **highest-first**: `["14", "13"]`.

**For commands that need a single version** (like `venv`, `test`), the CLI automatically uses the **highest version**. Override with the `OAREPO_VERSION` environment variable:

```bash
OAREPO_VERSION=13 ./run.sh venv
```

**Use in scripts:**
```bash
# Get Python versions as array
python_versions=$(./run.sh oarepo-versions | jq -r '.python_versions[]')

# Get highest OARepo version
oarepo_version=$(./run.sh oarepo-versions | jq -r '.oarepo_versions[0]')
```

### `library clean`

Cleans up the development environment.

```bash
./run.sh clean
```

**What it does:**
1. Stops Docker services (if running)
2. Removes `.venv` directory
3. Removes `.env-services` file

**Warning:** This is a destructive operation. Your virtual environment will need to be recreated with `library venv`.

### `library services`

Manages Docker services with subcommands.

```bash
./run.sh services [COMMAND]
```

**Commands:**
- `setup`: Initialize services (create networks, volumes)
- `start`: Start all services
- `stop`: Stop all services
- `destroy`: Stop services and remove volumes

**Examples:**
```bash
# First-time setup
./run.sh services setup

# Start services
./run.sh services start

# Stop services
./run.sh services stop

# Complete cleanup
./run.sh services destroy
```

## Repository Installer

`repo-install` is a top-level command (not a `repository` subcommand) that scaffolds a
brand-new repository from a copier template, replacing `repository_installer.sh`.

```bash
oarepo-cli repo-install my-repo
```

**Options:**
- `--python <binary>`: Python binary to use (default: `python3.14`)
- `--template <url/path>`: Copier template — a GitHub URL or a local path (default: `https://github.com/oarepo/nrp-app-copier`)
- `--version <ref>`: Template git ref, used when `--template` is a GitHub URL (default: `rdm-14`)
- `--uv <binary>`: `uv` binary to use (default: `uv`)
- `--uvx <binary>`: `uvx` binary to use (default: `uvx`)
- `--config <file>`: Additional copier data file, seeding answers non-interactively

**Current status:** argument parsing and upfront validation only (`uv`/`uvx`/`python` must
resolve on `PATH`, the repository name must be non-blank) — the actual scaffolding (running
copier, generating SSL certificates, Docker compose symlinks, git init) is not implemented yet.

**Exit codes:**
- `0`: Success
- `1`: Invalid input (missing repository name, or `uv`/`uvx`/`python` binary not found)
- `2`: Usage error (missing `REPOSITORY_NAME`, or `--config` file doesn't exist)

## Repository Tools

The `repository` subcommand provides tools for managing full OARepo repository instances.

**Note:** Repository commands are run from within your repository directory and require `oarepo-cli` to be installed globally or accessible via `PATH`.

### Command Overview

| Command | Description | Status |
|---------|-------------|--------|
| [`install`](#repository-install) | Install repository in virtual environment | ✅ Implemented |
| [`upgrade`](#repository-upgrade) | Clean cache and reinstall | ✅ Implemented |
| [`services`](#repository-services) | Manage Docker services | ✅ Implemented |
| [`model`](#repository-model) | Create/update record models | ✅ Implemented |
| [`local`](#repository-local) | Manage local package dependencies | ✅ Implemented |
| [`run`](#repository-run) | Start repository server | ✅ Implemented |
| [`cli`](#repository-cli) | Delegate to invenio-cli | ✅ Implemented |
| [`invenio`](#repository-invenio) | Delegate to the venv's own bare invenio | ✅ Implemented |
| [`shell`](#repository-shell) | Start an interactive shell in the venv | ✅ Implemented |
| [`lint`](#repository-lint) | Run linters and type checkers | ✅ Implemented |
| [`format`](#repository-format) | Format code with ruff | ✅ Implemented |
| [`check`](#repository-check) | Read-only equivalent of `lint`+`format` | ✅ Implemented |
| [`jslint`](#repository-jslint) | Run ESLint and Prettier on JS files | ✅ Implemented |
| [`jstest`](#repository-jstest) | Run JavaScript tests (Jest) | ✅ Implemented |
| [`test`](#repository-test) | Run pytest tests | ✅ Implemented |
| [`translations`](#repository-translations) | Extract/compile translations | ✅ Implemented |
| [`index`](#repository-index-rebuild) | Rebuild search index | ✅ Implemented |
| [`reset`](#repository-reset) | Full reset with confirmation | ✅ Implemented |
| [`info`](#repository-info) | Show Python version and models | ✅ Implemented |

### `repository install`

Installs a repository in its virtual environment, configures Invenio, and prepares for development.

```bash
oarepo-cli repository install
```

**Options:**
- `--quiet` / `-q`: Suppress output from subprocesses (uv, invenio-cli, etc.)

**What it does:**
1. Creates/syncs virtual environment with `uv sync` (reads `pyproject.toml`)
2. Copies translation overlays from `oarepo/collected_translations` to site-packages
3. Resolves instance path (`INVENIO_INSTANCE_PATH` env var, else `<venv>/var/instance` — Invenio's own default, computed directly rather than booting `invenio shell`)
4. Creates instance directory and symlinks `invenio.cfg`
5. Runs `invenio-cli install` (sets up assets, database tables, etc.)
6. Configures local service ports in `.invenio.private` (reads from `variables` file)
7. Compiles backend translations with `invenio-cli translations compile`

**Examples:**
```bash
# Standard installation
oarepo-cli repository install

# Quiet mode (suppress subprocess output)
oarepo-cli repository install --quiet
```

**Exit codes:**
- `0`: Installation successful
- `1`: Installation failed (subprocess error, missing files, etc.)

**Differences from old bash script:**
- Uses `uv sync` instead of `uv pip install` (lockfile-based, deterministic)
- Better error messages (Python exceptions vs. bash set -e)
- No parent-shell environment mutation (writes `.invenio.private` instead)

### `repository upgrade`

Cleans the virtual environment, uv cache, and lockfile, then fully reinstalls the repository.

```bash
oarepo-cli repository upgrade
```

**Options:**
- `--quiet` / `-q`: Suppress output from subprocesses (uv, invenio-cli, etc.)

**What it does:**
1. Removes the virtual environment (`.venv`), if present
2. Removes `uv.lock`, if present
3. Cleans the uv cache with `uv cache clean --force`
4. Reinstalls the repository (same steps as `repository install`)

**Examples:**
```bash
# Standard upgrade
oarepo-cli repository upgrade

# Quiet mode (suppress subprocess output)
oarepo-cli repository upgrade --quiet
```

**Exit codes:**
- `0`: Upgrade successful
- `1`: Upgrade failed (subprocess error, missing files, etc.)

Use this after updating OARepo/RDM version pins, or when the environment needs a clean rebuild.

### `repository services`

Manages the repository's Docker services (database, search, message queue, cache, S3). Each subcommand is a pure passthrough to `invenio-cli services <subcommand>` — any extra arguments or flags are forwarded verbatim, and `--help` reaches invenio-cli's own help for that subcommand rather than oarepo-cli's.

```bash
oarepo-cli repository services setup
oarepo-cli repository services start
oarepo-cli repository services stop
oarepo-cli repository services destroy
```

**Subcommands:**
- `setup`: Setup Docker services (accepts invenio-cli's own flags, e.g. `-N`/`--no-demo-data`, `-f`/`--force`, `--stop-services`)
- `start`: Start Docker services
- `stop`: Stop Docker services
- `destroy`: Destroy Docker services

**Options** (each subcommand):
- `--quiet` / `-q`: Suppress output from invenio-cli

**Examples:**
```bash
# Setup services without demo data
oarepo-cli repository services setup -N

# See invenio-cli's own help for a subcommand
oarepo-cli repository services setup --help
```

**Exit codes:**
- Whatever `invenio-cli services <subcommand>` returns (propagated exactly, not collapsed to 0/1)
- `1`: Project context could not be discovered (e.g. no `pyproject.toml`)

### `repository model`

Creates and updates record models via [copier](https://copier.readthedocs.io/), rendering the configured model template (`[tool.oarepo-cli.model] template_url`/`template_version` in `pyproject.toml`, or the `MODEL_TEMPLATE`/`MODEL_TEMPLATE_VERSION` env vars — default [`nrp-model-copier`](https://github.com/oarepo/nrp-model-copier) @ `rdm-14`) into `models/<name>/`. Template/version are not CLI flags — only configurable via `pyproject.toml`/env vars, matching `repository_runner.sh`.

```bash
oarepo-cli repository model create <name> [config_file]
oarepo-cli repository model update <name> [answers_file]
```

**Subcommands:**
- `create <name> [config_file]`: Renders the model template into `models/<name>/`. If `config_file` (a YAML file) is given, it seeds *all* answers non-interactively and must supply `model_name` itself; if omitted, only `model_name` is passed and the template's own defaults apply. Reinstalls the repository afterwards if a virtual environment already exists (a new model changes `pyproject.toml` entry points/dependencies).
- `update <name> [answers_file]`: Updates an existing model (`models/<name>` must already exist) from its recorded `.copier-answers.yml`, or from `answers_file` if given. Requires a git-tracked, clean repository (copier's own requirement); conflicts are written inline for review via `git diff`.

**Options** (each subcommand):
- `--quiet` / `-q`: Suppress output from subprocesses (copier, invenio-cli, etc.)

**Examples:**
```bash
oarepo-cli repository model create my_model
oarepo-cli repository model create my_model model_config.yaml

oarepo-cli repository model update my_model
oarepo-cli repository model update my_model model_config.yaml
```

**Exit codes:**
- `0`: Model created/updated successfully
- `1`: Model creation/update failed (e.g. missing config file, non-existent model, project context could not be discovered)

### `repository local`

Manages locally-developed packages as editable `[tool.uv.sources]` entries in `pyproject.toml`, for developing a dependency (e.g. a custom `oarepo`/`invenio` extension) alongside the repository. Both subcommands edit `pyproject.toml` in place (preserving comments/formatting/ordering elsewhere in the file) and then trigger a full [`repository upgrade`](#repository-upgrade) — unconditionally, unlike `repository model create`'s conditional reinstall, but *without* clearing the uv cache (unlike a plain `repository upgrade`): a local package's own dependencies haven't changed, so there's nothing stale to purge.

```bash
oarepo-cli repository local add <path>
oarepo-cli repository local remove <name>
oarepo-cli repository local remove --all
```

**Subcommands:**
- `add <path>`: Adds the package at `<path>` (which must contain its own `pyproject.toml`) as an editable local source — `<path>` is resolved relative to the repository root and written to `[tool.uv.sources]`, and the package's name is appended to `[project].dependencies` (skipped if already present). Re-adding an already-present package updates its `[tool.uv.sources]` entry in place.
- `remove <name>`: Removes the named local package from both `[tool.uv.sources]` and `[project].dependencies`.
- `remove --all`: Removes every local package added via `add` in a single repository upgrade (rather than one upgrade per package). Only touches `[tool.uv.sources]` entries with a `path` key — unrelated entries (e.g. the CESNET-patched `invenio-cli`'s own `{ index = "cesnet" }` override) are left untouched. Mutually exclusive with passing a `<name>`.

**Options** (each subcommand):
- `--quiet` / `-q`: Suppress output from subprocesses (invenio-cli, etc.)

**Examples:**
```bash
oarepo-cli repository local add ../my-local-package
oarepo-cli repository local remove my-local-package
oarepo-cli repository local remove --all
```

**Exit codes:**
- `0`: Package(s) added/removed successfully
- `1`: Operation failed (e.g. no `pyproject.toml` at `<path>`, unknown package name, neither/both of a name and `--all` given, project context could not be discovered)

### `repository run`

Starts the repository's development server: starts Docker services (unless `--no-services`), then hands off to either `invenio-cli run` (which manages Celery itself) or, with `--no-celery`, the venv's own `invenio run` directly.

```bash
oarepo-cli repository run
oarepo-cli repository run --no-services
oarepo-cli repository run --no-celery
```

This command **replaces the current process** (`os.execve`/`os.execvpe`) with the server once Docker services are started — it never returns on success, so a terminal Ctrl+C hits invenio-cli/invenio directly, exactly as if it had been run by hand. Docker services are deliberately *not* stopped when the server exits — run `repository services stop` explicitly when done.

**Options:**
- `--no-services`: Don't start Docker services first
- `--no-celery`: Run the venv's own `invenio run` directly, without Celery/invenio-cli
- `--quiet` / `-q`: Suppress output from starting Docker services

Any extra arguments/options (e.g. `-p 5001`) are forwarded to the underlying `invenio-cli run`/`invenio run` command.

**Examples:**
```bash
oarepo-cli repository run
oarepo-cli repository run --no-celery -- -p 5001
```

**Exit codes:**
- Whatever invenio-cli/invenio itself exits with, once running
- `1`: Starting Docker services failed, or project context could not be discovered

### `repository cli`

Pure passthrough to invenio-cli: replaces this process (`os.execve`/`os.execvpe`) with `invenio-cli <args>`, so `--help` reaches invenio-cli's own help (not oarepo-cli's), and the exit code is preserved exactly.

```bash
oarepo-cli repository cli [invenio-cli_args...]
```

**Examples:**
```bash
oarepo-cli repository cli services status
oarepo-cli repository cli --help
```

**Exit codes:**
- Whatever invenio-cli itself exits with
- `1`: Project context could not be discovered

### `repository invenio`

Pure passthrough to the venv's own `invenio` binary (bare invenio, not invenio-cli -- see [`repository cli`](#repository-cli) for that): replaces this process (`os.execve`) with `invenio <args>`, so `--help` reaches invenio's own help (not oarepo-cli's), and the exit code is preserved exactly.

```bash
oarepo-cli repository invenio [invenio_args...]
```

**Examples:**
```bash
oarepo-cli repository invenio db upgrade
oarepo-cli repository invenio --help
```

**Exit codes:**
- Whatever invenio itself exits with
- `1`: Project context could not be discovered

### `repository shell`

Starts an interactive bash shell with the repository's virtual environment activated. By default, Docker services are started first (via `invenio-cli services start`, like [`repository run`](#repository-run)) -- use `--no-services` to skip, e.g. if they're already running. This command replaces the current process (`os.execve`) with the shell -- it never returns on success.

Unlike [`library shell`](#library-shell), no environment variables are loaded from an `.env-services` file: a repository resolves its own service connection details from `invenio.cfg`/`.invenio.private` instead.

```bash
oarepo-cli repository shell
```

**Options:**
- `--no-services`: Don't start Docker services first
- `--quiet` / `-q`: Suppress output from starting Docker services

**Examples:**
```bash
oarepo-cli repository shell
oarepo-cli repository shell --no-services
```

**Exit codes:**
- Whatever the shell itself exits with
- `1`: Starting Docker services failed, or project context could not be discovered

### `repository lint`

Runs linters and type checkers on the repository's codebase -- ruff check, ruff format, a license header check, a `from __future__ import annotations` check, and ty check, in order, stopping at the first failure. Runs across every module directory declared in `[tool.uv.build-backend]` (or `src/`/the flat layout, if used instead). **By default, auto-fixes** what ruff and ty can fix. Functionally identical to [`library lint`](#library-lint) (both share the same underlying implementation), just operating on a repository's own code.

```bash
oarepo-cli repository lint
```

**Options:**
- `--fix` / `--no-fix`: Auto-fix (default) vs. report-only mode
- `--quiet` / `-q`: Suppress output from subprocesses

**Examples:**
```bash
oarepo-cli repository lint
oarepo-cli repository lint --no-fix
```

**Exit codes:**
- Exit code of the first failing check
- `1`: Project context could not be discovered

### `repository format`

Formats the repository's codebase using ruff. **By default, rewrites files**. Functionally identical to [`library format`](#library-format).

```bash
oarepo-cli repository format
```

**Options:**
- `--fix` / `--no-fix`: Rewrite files (default) vs. preview-only mode (`ruff format --check`)
- `--quiet` / `-q`: Suppress output from subprocesses

Any additional arguments are passed directly to the ruff invocation(s).

**Examples:**
```bash
oarepo-cli repository format
oarepo-cli repository format --no-fix
```

**Exit codes:**
- Exit code of the underlying ruff invocation
- `1`: Project context could not be discovered

### `repository check`

Read-only equivalent of [`repository lint`](#repository-lint)/[`repository format`](#repository-format) that **never modifies files**. Safe for CI/CD. Functionally identical to [`library check`](#library-check).

```bash
oarepo-cli repository check
```

**Options:**
- `--quiet` / `-q`: Suppress output from subprocesses

**Exit codes:**
- Exit code of the first failing check
- `1`: Project context could not be discovered

### `repository jslint`

Runs ESLint and Prettier on the repository's JavaScript files. Installs `@inveniosoftware/eslint-config-invenio` if needed, generates `.eslintrc.yaml`, runs eslint with `--fix`, and runs prettier (in check mode under `CI=true`). Skips entirely if no `package.json` is found at the repository root -- the common case, since a repository doesn't commit one there. Functionally identical to [`library jslint`](#library-jslint).

```bash
oarepo-cli repository jslint
```

**Options:**
- `--quiet` / `-q`: Suppress output from subprocesses

**Exit codes:**
- Exit code of the underlying eslint/prettier invocation
- `1`: Project context could not be discovered

### `repository jstest`

Runs JavaScript tests (Jest) via `invenio webpack run test`, collecting every registered `invenio_assets.webpack` entry point -- including the repository's own (see `[project.entry-points."invenio_assets.webpack"]` in `pyproject.toml`), same as for a library. Requires the repository to already be installed ([`repository install`](#repository-install)), so its webpack build exists. Functionally identical to [`library jstest`](#library-jstest).

```bash
oarepo-cli repository jstest [OPTIONS]
```

**Options:**
- `--setup`: Set up Jest configuration instead of running tests (currently delegates to bash script)
- `--skip-services`: Don't start Docker services first
- `--quiet` / `-q`: Suppress output from subprocesses

Any additional arguments are passed directly to the test command.

**Examples:**
```bash
oarepo-cli repository jstest
oarepo-cli repository jstest --skip-services
```

**Exit codes:**
- Exit code of the underlying test command
- `1`: Project context could not be discovered

### `repository test`

Runs the repository's test suite using pytest. By default, Docker services are started first (via `invenio-cli services start`, like [`repository run`](#repository-run)/[`shell`](#repository-shell)) -- use `--no-services` to skip. Unlike [`library test`](#library-test), services are never stopped afterward, matching every other `repository` command.

`--with-coverage` covers every module directory (see [`repository lint`](#repository-lint)) rather than a single package, since a repository's code is typically laid out as several top-level modules. Since a fresh repository has no "tests" extras convention of its own (unlike a library), `pytest`/`pytest-cov` are installed directly into the venv on demand if missing.

```bash
oarepo-cli repository test
```

**Options:**
- `--no-services`: Don't start Docker services first
- `--with-coverage`: Enable coverage reporting (HTML and terminal)
- `--quiet` / `-q`: Suppress output from starting Docker services

Any additional arguments are passed directly to pytest.

**Examples:**
```bash
oarepo-cli repository test
oarepo-cli repository test --with-coverage
oarepo-cli repository test --no-services
oarepo-cli repository test -v -k test_specific
```

**Exit codes:**
- Exit code of the underlying pytest invocation
- `1`: Starting Docker services failed, or project context could not be discovered

### `repository translations`

Extracts, merges and compiles translations (backend + JS) via oarepo-tools, or just compiles backend translations with `compile`.

```bash
oarepo-cli repository translations
oarepo-cli repository translations compile
```

`repository translations compile` delegates to `invenio-cli translations compile` (backend only, no extraction). Any other invocation (including no args) runs oarepo-tools' `make-translations`, with all given args forwarded to it verbatim.

**Options:**
- `--quiet` / `-q`: Suppress output from subprocesses

**Exit codes:**
- `0`: Success
- `1`: Failure (translations compile/make-translations failed, or project context could not be discovered)

### `repository index rebuild`

Destroys and re-creates the search index, then rebuilds all records and custom fields.

```bash
oarepo-cli repository index rebuild
```

**Options:**
- `--quiet` / `-q`: Suppress output from subprocesses

**Exit codes:**
- `0`: Success
- `1`: Failure (a step failed, or project context could not be discovered)

### `repository reset`

Performs a full reset of the repository: destroys Docker services, removes the virtual environment/`uv.lock`/`.invenio.private`, cleans the uv cache, reinstalls the repository, sets up services again, and creates an administration role and a demo user (`user@demo.org`, password from `DEMO_USER_PASSWORD`, default `123456`).

```bash
oarepo-cli repository reset
```

Prompts for confirmation (exactly `yes`) before proceeding, since this **PURGES ALL EXISTING DATA** in your containers. Anything other than exactly `yes` cancels the reset without error.

**Options:**
- `--quiet` / `-q`: Suppress output from subprocesses

**Exit codes:**
- `0`: Reset completed, or cancelled by the user
- `1`: Reset failed partway through, or project context could not be discovered

### `repository info`

Shows the resolved Python version and discovered record models (any directory under `models/` with both `.copier-answers.yml` and `model.py`).

```bash
oarepo-cli repository info
```

**Exit codes:**
- `0`: Success
- `1`: Project context could not be discovered

## Configuration

Configuration is loaded from multiple sources with precedence:

**defaults < pyproject.toml < environment variables < CLI flags**

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OAREPO_VENV_PATH` | Virtual environment path | `.venv` |
| `OAREPO_VERSION` | OARepo major version (override auto-detection) | Auto-detected |
| `OAREPO_BUILD_EDITABLE` | Install in editable mode | `true` |
| `OAREPO_SERVICES_DB` | Database service | `postgresql` |
| `OAREPO_SERVICES_SEARCH` | Search service | `opensearch2` |
| `OAREPO_SERVICES_CACHE` | Cache service | `redis` |
| `OAREPO_SERVICES_MQ` | Message queue service | `rabbitmq` |
| `OAREPO_SERVICES_S3` | Object storage service | `minio` |

### pyproject.toml Configuration

```toml
[tool.oarepo-cli]

[tool.oarepo-cli.venv]
path = ".venv"  # Custom venv path

[tool.oarepo-cli.build]
editable = true  # Editable mode by default

[tool.oarepo-cli.services]
db = "postgresql"
search = "opensearch2"
cache = "redis"
mq = "rabbitmq"
s3 = "minio"

[tool.oarepo-cli.license]
organization = "Your Organization"  # For license headers
```

## Development

This project follows strict development practices:

- **Python 3.14** only (`requires-python = ">=3.14,<3.15"`)
- **Never use `shell=True`** in subprocess calls (security)
- **Use `uv`** for dependency management
- **Test coverage** tracked with pytest-cov
- **Type checking** with `ty`
- **Linting** with `ruff`
- **Pre-commit hooks** for quality checks

### Development Commands

```bash
# Setup development environment
make install-dev

# Run tests
make test

# Run linters and type checkers
make check

# Format code
make format

# See all available targets
make help
```

### Running Tests

```bash
# All tests (unit + integration)
make test

# Unit tests only (fast)
pytest tests/unit/

# Integration tests (slow)
pytest tests/integration/

# Specific test file
pytest tests/unit/test_context.py -v

# With coverage
pytest --cov=oarepo_cli --cov-report=html
```

## Architecture

The codebase is organized by responsibility:

```
oarepo_cli/
├── cli/              # Typer command definitions
│   ├── main.py       # Root app and global options
│   ├── library.py    # Library subcommands
│   └── repository.py # Repository subcommands (Phase 4+)
├── core/             # Core domain models
│   ├── config.py     # Configuration management
│   ├── context.py    # Project context discovery
│   ├── errors.py     # Exception hierarchy
│   └── platform.py   # Platform detection
├── services/         # Business logic services
│   ├── process.py    # Safe subprocess execution
│   ├── venv.py       # Virtual environment management
│   ├── pyproject_reader.py  # TOML parsing
│   ├── version_resolver.py # Version resolution
│   └── ...           # Other services
└── utils/            # Utilities
    └── locks.py      # File locking for concurrency
```

**Design principles:**
- **Single executable**: One `oarepo-cli` command, not multiple scripts
- **No shell injection**: Explicit argument lists, never string interpolation
- **Explicit subprocess management**: No parent environment mutation
- **Standard TOML parsing**: `tomllib` (stdlib), never regex/sed/grep
- **Behavior-preserving**: Same exit codes, stdout/stderr, flag names as bash scripts

For detailed architecture documentation, see [`docs/architecture/`](./docs/architecture/).

## Migration from Bash Scripts

If you're migrating from the old bash scripts:

| Old Command | New Command |
|-------------|-------------|
| `./run.sh venv` | `oarepo-cli library venv` |
| `./run.sh install` | `oarepo-cli library install` |
| `./run.sh test` | `oarepo-cli library test` |
| `./run.sh start` | `oarepo-cli library start` |
| `./run.sh stop` | `oarepo-cli library stop` |
| `./run.sh lint` | `oarepo-cli library lint` |
| `./run.sh format` | `oarepo-cli library format` |
| `./run.sh shell` | `oarepo-cli library shell` |
| `./run.sh oarepo-versions` | `oarepo-cli library oarepo-versions` |
| `./repository_installer.sh NAME` | `oarepo-cli repo-install NAME` (argument validation only so far — see [Repository Installer](#repository-installer)) |

**Breaking changes:**
- `library lint` and `library format` **auto-fix by default** (use `--no-fix` for report-only)
- New `library check` command for read-only validation
- `oarepo-versions` extracts from dependencies, not `[tool.oarepo-cli].version` config
- No `self-update` command (use `pip install --upgrade oarepo-cli`)

See [`docs/architecture/03-migration-guide.md`](./docs/architecture/03-migration-guide.md) for complete migration details.

## License

MIT License - see [LICENSE](LICENSE) for details.

Copyright © 2026 CESNET z.s.p.o.
