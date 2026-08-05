# OARepo CLI

`oarepo-cli` is a command-line tool for scaffolding and developing OARepo repositories and libraries. It replaces the previous `library_runner.sh`, `repository_runner.sh`, and `repository_installer.sh` scripts with a single executable.

It provides three things:

- **`new`** — scaffold a brand-new repository from a copier template
- **`repository`** — manage an existing repository instance (install, run, test, models, ...)
- **`library`** — develop an OARepo library package (models, modules, extensions)

## Table of Contents

- [New Repository](#new-repository)
- [Repository Tools](#repository-tools)
- [Library Development Tools](#library-development-tools)
- [Configuration](#configuration)
- [Exit Codes](#exit-codes)
- [License](#license)

## New Repository

`oarepo-cli new` scaffolds a new repository from a [copier](https://copier.readthedocs.io/) template into `./<name>`.

```bash
oarepo-cli new my-repo
```

| Option | Description | Default |
|---|---|---|
| `--template <url/path>` | Copier template — a GitHub URL or a local path | `https://github.com/oarepo/nrp-app-copier` |
| `--version <ref>` | Template git ref, used only when `--template` is a GitHub URL | `rdm-14` |
| `--config <file>` | YAML data file seeding all answers non-interactively | — |
| `--python <binary>` | Python binary; only checked for existence, not otherwise used | `python3.14` |
| `--uv <binary>` / `--uvx <binary>` | `uv`/`uvx` binaries; only checked for existence, not otherwise used | `uv` / `uvx` |

What it does:
1. Renders the template into `./<name>`
2. Generates a self-signed development TLS certificate/key pair (`docker/development.crt`/`.key`)
3. Clears out any stale Docker containers left over from a previous attempt at the same name
4. Initializes a git repository with an initial commit (skipped in CI, or if git isn't installed)

## Repository Tools

Commands for managing an existing repository instance, run from inside the repository directory.

| Command | Description |
|---|---|
| [`install`](#repository-install) | Install the repository into its virtual environment |
| [`upgrade`](#repository-upgrade) | Clean and fully reinstall |
| [`services`](#repository-services) | Manage Docker services (`setup`/`start`/`stop`/`destroy`) |
| [`model`](#repository-model) | Create/update record models |
| [`local`](#repository-local) | Manage local (editable) package dependencies |
| [`run`](#repository-run) | Start the development server |
| [`shell`](#repository-shell) | Open a shell in the virtual environment |
| [`cli`](#repository-cli--repository-invenio) | Passthrough to `invenio-cli` |
| [`invenio`](#repository-cli--repository-invenio) | Passthrough to the venv's own `invenio` |
| [`lint`](#repository-lint--format--check) | Run linters and type checkers |
| [`format`](#repository-lint--format--check) | Format code with ruff |
| [`check`](#repository-lint--format--check) | Read-only lint + format, for CI |
| [`jslint`](#repository-jslint--jstest) | Run ESLint and Prettier |
| [`jstest`](#repository-jslint--jstest) | Run JavaScript tests (Jest) |
| [`test`](#repository-test) | Run the pytest suite |
| [`translations`](#repository-translations) | Extract/compile translations |
| [`index rebuild`](#repository-index-rebuild) | Rebuild the search index |
| [`reset`](#repository-reset) | Full reset (**destroys all data**) |
| [`info`](#repository-info) | Show the resolved Python version and models |

Every command accepts `--quiet`/`-q` to suppress subprocess output; only additional options are listed below.

### `repository install`

Installs the repository into its virtual environment and configures Invenio.

```bash
oarepo-cli repository install
```

1. Syncs the virtual environment with `uv sync`
2. Copies the translation overlay into site-packages
3. Resolves and creates the Invenio instance directory, symlinking `invenio.cfg`
4. Runs `invenio-cli install` (assets, database tables, etc.)
5. Writes local service ports to `.invenio.private`
6. Compiles backend translations

### `repository upgrade`

Removes the virtual environment, `uv.lock`, and uv cache, then reinstalls from scratch. Use after changing OARepo/RDM version pins or when the environment needs a clean rebuild.

```bash
oarepo-cli repository upgrade
```

### `repository services`

Passthrough to `invenio-cli services <subcommand>`: extra arguments/flags are forwarded verbatim, and `--help` shows invenio-cli's own help.

```bash
oarepo-cli repository services setup
oarepo-cli repository services start
oarepo-cli repository services stop
oarepo-cli repository services destroy
```

### `repository model`

Creates and updates record models via copier, rendering the model template into `models/<name>/`. The template/version are configured in `pyproject.toml` (`[tool.oarepo-cli.model]`) or via `OAREPO_MODEL_TEMPLATE_URL`/`OAREPO_MODEL_TEMPLATE_VERSION` — not as CLI flags.

```bash
oarepo-cli repository model create <name> [config_file]
oarepo-cli repository model update <name> [answers_file]
```

- `create <name> [config_file]`: renders the template into `models/<name>/`. If `config_file` (YAML) is given, it seeds all answers and must include `model_name` itself; otherwise only `model_name` is passed and the template's own defaults apply. Reinstalls the repository afterward if a virtual environment already exists.
- `update <name> [answers_file]`: updates an existing model from its recorded `.copier-answers.yml`, or from `answers_file` if given. Requires a clean, git-tracked repository; conflicts are written inline for review via `git diff`.

### `repository local`

Manages locally-developed packages as editable `[tool.uv.sources]` entries in `pyproject.toml` — for developing a dependency (e.g. a custom extension) alongside the repository. Both subcommands edit `pyproject.toml` in place and trigger a full [`repository upgrade`](#repository-upgrade) (without clearing the uv cache).

```bash
oarepo-cli repository local add <path>
oarepo-cli repository local remove <name>
oarepo-cli repository local remove --all
```

- `add <path>`: adds the package at `<path>` (which must have its own `pyproject.toml`) as an editable source and appends it to `[project].dependencies`. Re-adding an already-present package updates its entry in place.
- `remove <name>` / `remove --all`: removes one or all local packages from `[tool.uv.sources]`/`[project].dependencies`. `--all` only touches entries added via `add` and upgrades once for all of them.

### `repository run`

Starts the development server: starts Docker services (unless `--no-services`), then replaces the current process with `invenio-cli run` (or, with `--no-celery`, the venv's own `invenio run` directly). A terminal Ctrl+C hits invenio/invenio-cli directly. Services are **not** stopped when the server exits — run [`repository services stop`](#repository-services) explicitly.

```bash
oarepo-cli repository run
oarepo-cli repository run --no-celery -- -p 5001
```

| Option | Description |
|---|---|
| `--no-services` | Don't start Docker services first |
| `--no-celery` | Run the venv's own `invenio run` directly, without Celery/invenio-cli |

Extra arguments (e.g. `-p 5001`) are forwarded to the underlying `invenio-cli run`/`invenio run`.

### `repository shell`

Opens an interactive bash shell with the virtual environment activated, resolving service connection details from `invenio.cfg`/`.invenio.private`. Replaces the current process — it never returns.

```bash
oarepo-cli repository shell
oarepo-cli repository shell --no-services
```

| Option | Description |
|---|---|
| `--no-services` | Don't start Docker services first |

### `repository cli` / `repository invenio`

Pure passthroughs that replace the current process, so `--help` and the exit code are exactly the wrapped tool's own. `cli` runs `invenio-cli`; `invenio` runs the venv's own bare `invenio` binary directly.

```bash
oarepo-cli repository cli services status
oarepo-cli repository invenio db upgrade
```

### `repository lint` / `format` / `check`

Runs ruff, a license-header check, a `from __future__ import annotations` check, and `ty`, across every module directory declared in `[tool.uv.build-backend]` (or `src/`, if used instead).

```bash
oarepo-cli repository lint
oarepo-cli repository format
oarepo-cli repository check
```

- `lint` runs everything in order, stopping at the first failure, and **auto-fixes by default** (`--no-fix` for report-only).
- `format` runs ruff format only, and **rewrites files by default** (`--no-fix` for `ruff format --check`).
- `check` is the read-only equivalent of both combined (never modifies files) — the exit code is that of the first failing check. Still generates `.ruff.toml`/`ty.toml` config files in the project root.

### `repository jslint` / `jstest`

`jslint` runs ESLint and Prettier on the repository's JavaScript files (skipped if no `package.json` exists at the root). `jstest` runs Jest via `invenio webpack run test`, across every registered `invenio_assets.webpack` entry point; it requires the repository to already be [installed](#repository-install).

```bash
oarepo-cli repository jslint
oarepo-cli repository jstest
```

| Option | Description |
|---|---|
| `--setup` (`jstest` only) | Not implemented — set up Jest config via `library_runner.sh jstest setup` instead |
| `--skip-services` (`jstest` only) | Don't start Docker services first |

### `repository test`

Runs the pytest suite. Docker services are started first unless `--no-services` (unlike other commands, they are never stopped afterward). `pytest`/`pytest-cov` are installed on demand if missing, since a fresh repository has no "tests" extra of its own.

```bash
oarepo-cli repository test
oarepo-cli repository test --with-coverage
oarepo-cli repository test -v -k test_specific
```

| Option | Description |
|---|---|
| `--no-services` | Don't start Docker services first |
| `--with-coverage` | Enable coverage reporting (HTML + terminal), across every module directory |

Extra arguments are passed directly to pytest.

### `repository translations`

```bash
oarepo-cli repository translations          # extract, merge, compile (backend + JS)
oarepo-cli repository translations compile  # backend only, via invenio-cli
```

### `repository index rebuild`

Destroys and re-creates the search index, then rebuilds all records and custom fields.

```bash
oarepo-cli repository index rebuild
```

### `repository reset`

Destroys Docker services, removes the virtual environment/`uv.lock`/`.invenio.private`, cleans the uv cache, reinstalls, sets up services again, and creates a demo admin user (`user@demo.org`, password from `DEMO_USER_PASSWORD`, default `123456`).

```bash
oarepo-cli repository reset
```

Prompts for confirmation (exactly `yes`) since this **purges all existing data** in your containers. Anything else cancels without error.

### `repository info`

Shows the resolved Python version and discovered record models.

```bash
oarepo-cli repository info
```

## Library Development Tools

Commands for developing an OARepo library package, run from inside the library directory.

| Command | Description |
|---|---|
| [`venv`](#library-venv--install--upgrade) | Set up the virtual environment |
| [`install`](#library-venv--install--upgrade) | Alias for `venv` |
| [`upgrade`](#library-venv--install--upgrade) | Clean and recreate the venv |
| [`test`](#library-test) | Run pytest tests |
| [`start`](#library-start--stop) / `stop` | Start/stop Docker services |
| [`lint`](#library-lint--format--check) | Run linters and type checkers |
| [`format`](#library-lint--format--check) | Format code with ruff |
| [`check`](#library-lint--format--check) | Read-only lint + format, for CI |
| [`shell`](#library-shell) | Open a shell in the venv |
| [`invenio`](#library-invenio) | Run invenio commands in the venv |
| [`translations`](#library-translations) | Extract/compile translations |
| [`license-headers`](#library-license-headers) | Add SPDX/MIT license headers |
| [`jslint`](#library-jslint--jstest) | Run ESLint and Prettier |
| [`jstest`](#library-jslint--jstest) | Run JavaScript tests (Jest) |
| [`oarepo-versions`](#library-oarepo-versions) | List detected OARepo/Python versions (JSON) |
| [`clean`](#library-clean) | Remove the venv and services |

Every command accepts `--quiet`/`-q` to suppress subprocess output; only additional options are listed below.

### `library venv` / `install` / `upgrade`

`venv` (aliased as `install`) creates or verifies the virtual environment and syncs dependencies; `upgrade` stops services, cleans the uv cache, and recreates the venv from scratch.

```bash
oarepo-cli library venv
oarepo-cli library venv --force
oarepo-cli library upgrade
```

| Option | Description |
|---|---|
| `--force` / `-f` (`venv` only) | Recreate the venv from scratch |
| `--no-editable` (`venv` only) | Install as a built wheel instead of editable mode |

### `library test`

```bash
oarepo-cli library test
oarepo-cli library test --with-coverage -x -k test_specific
```

| Option | Description |
|---|---|
| `--skip-services` | Don't start/stop Docker services |
| `--with-coverage` | Enable coverage reporting (HTML + terminal) |

Extra arguments are passed directly to pytest.

### `library start` / `stop`

Starts or stops the Docker services (PostgreSQL, OpenSearch, Redis, RabbitMQ, MinIO) configured via `[tool.oarepo-cli.services]` or `OAREPO_SERVICES_*`, writing connection details to `.env-services`.

```bash
oarepo-cli library start
oarepo-cli library stop
```

### `library lint` / `format` / `check`

Runs ruff, a license-header check, a `from __future__ import annotations` check, and `ty` on the library's source.

```bash
oarepo-cli library lint
oarepo-cli library format
oarepo-cli library check
```

- `lint` runs everything in order, stopping at the first failure, and **auto-fixes by default** (`--no-fix` for report-only). The license-header and future-annotations checks never modify files — use [`license-headers`](#library-license-headers) for those.
- `format` runs ruff format only, and **rewrites files by default** (`--no-fix` for `ruff format --check`).
- `check` is the read-only equivalent of both combined — safe for CI.

### `library shell`

Opens an interactive bash shell with the venv activated and `.env-services` loaded. Replaces the current process.

```bash
oarepo-cli library shell
oarepo-cli library shell --skip-services
```

| Option | Description |
|---|---|
| `--skip-services` | Don't start Docker services first |

### `library invenio`

Runs invenio CLI commands in the venv, with `.env-services` loaded.

```bash
oarepo-cli library invenio db upgrade
oarepo-cli library invenio users create admin@example.com --password 123456 --active
```

| Option | Description |
|---|---|
| `--skip-services` | Don't start Docker services first |

### `library translations`

Extracts and compiles translations via `oarepo-tools make-translations`. Extra arguments are forwarded to it verbatim.

```bash
oarepo-cli library translations
```

### `library license-headers`

Adds an SPDX/MIT license header to any Python file that doesn't already have one.

```bash
oarepo-cli library license-headers
oarepo-cli library license-headers --organization "My Organization"
```

| Option | Description | Default |
|---|---|---|
| `--organization` / `-o` | Organization name in the header | `[tool.oarepo-cli.license].organization`, or `CESNET z.s.p.o` |

### `library jslint` / `jstest`

`jslint` runs ESLint and Prettier on JavaScript files (skipped if no `package.json` exists). `jstest` runs Jest via `invenio webpack run test`.

```bash
oarepo-cli library jslint
oarepo-cli library jstest
```

| Option | Description |
|---|---|
| `--setup` (`jstest` only) | Not implemented — set up Jest config via `library_runner.sh jstest setup` instead |
| `--skip-services` (`jstest` only) | Don't start Docker services first |

### `library oarepo-versions`

Prints the OARepo/Python/Node versions detected from `pyproject.toml`'s dependency constraints, as JSON:

```bash
$ oarepo-cli library oarepo-versions
{"oarepo_versions": ["14"], "python_versions": ["3.14"], "node_versions": ["24"]}
```

OARepo major versions are extracted from `oarepo` constraints in `[project].dependencies`/`[project.optional-dependencies]`, sorted highest-first. Commands that need a single version (`venv`, `test`, ...) use the highest one; override with `OAREPO_VERSION`.

### `library clean`

Stops services, then removes the virtual environment, `uv.lock`, and `.env-services`. Idempotent.

```bash
oarepo-cli library clean
```

## Configuration

Settings are resolved with this precedence: **defaults < `pyproject.toml` < environment variables < CLI flags.**

| Environment Variable | `pyproject.toml` key | Default |
|---|---|---|
| `OAREPO_VENV_PATH` | `[tool.oarepo-cli.venv].path` | `.venv` |
| `OAREPO_VERSION` | *(none — auto-detected from dependencies)* | auto-detected |
| `OAREPO_PYTHON_BINARY` | `[tool.oarepo-cli.python].binary` | auto-detected |
| `OAREPO_BUILD_EDITABLE` | `[tool.oarepo-cli.build].editable` | `true` |
| `OAREPO_TEST_COVERAGE` | `[tool.oarepo-cli.test].coverage` | `false` |
| `OAREPO_TEST_SKIP_SERVICES` | `[tool.oarepo-cli.test].skip_services` | `false` |
| `OAREPO_SERVICES_SKIP` | `[tool.oarepo-cli.services].skip` | `false` |
| `OAREPO_SERVICES_DB` | `[tool.oarepo-cli.services].db` | `postgresql` |
| `OAREPO_SERVICES_SEARCH` | `[tool.oarepo-cli.services].search` | `opensearch` |
| `OAREPO_SERVICES_CACHE` | `[tool.oarepo-cli.services].cache` | `redis` |
| `OAREPO_SERVICES_MQ` | `[tool.oarepo-cli.services].mq` | `rabbitmq` |
| `OAREPO_SERVICES_S3` | `[tool.oarepo-cli.services].s3` | `minio` |
| `OAREPO_MODEL_TEMPLATE_URL` | `[tool.oarepo-cli.model].template_url` | `https://github.com/oarepo/nrp-model-copier` |
| `OAREPO_MODEL_TEMPLATE_VERSION` | `[tool.oarepo-cli.model].template_version` | `rdm-14` |
| `OAREPO_TRANSLATIONS_OVERLAY` | `[tool.oarepo-cli.translations].overlay_dir` | auto-detected |
| `OAREPO_CELERY_POOL_TYPE` | `[tool.oarepo-cli.celery].pool_type` | `threads` |
| `OAREPO_CELERY_CONCURRENCY` | `[tool.oarepo-cli.celery].concurrency` | `10` |
| `OAREPO_LICENSE_ORG` | `[tool.oarepo-cli.license].organization` | `CESNET z.s.p.o` |
| `DEMO_USER_PASSWORD` | `[tool.oarepo-cli.security].demo_user_password` | `123456` |

Example `pyproject.toml`:

```toml
[tool.oarepo-cli.venv]
path = ".venv"

[tool.oarepo-cli.services]
db = "postgresql"
search = "opensearch"
cache = "redis"
mq = "rabbitmq"
s3 = "minio"

[tool.oarepo-cli.license]
organization = "Your Organization"
```

## Exit Codes

- **`0`** — success.
- **`1`** — a failure, e.g. a subprocess exited non-zero, or the project context couldn't be discovered (no `pyproject.toml`).
- **`2`** — a usage error (missing/invalid arguments or options), reported before anything runs.
- Passthrough commands (`repository cli`/`invenio`/`services <subcommand>`, `repository run`'s server) exit with whatever the wrapped tool itself returns, not collapsed to `0`/`1`.

`repository reset` is the one exception: `0` covers both a completed reset and the user cancelling the confirmation prompt.

## License

MIT License — see [LICENSE](LICENSE) for details.

Copyright © 2026 CESNET z.s.p.o.
