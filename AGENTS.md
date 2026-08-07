# AGENTS.md

AI coding agent guide for `oarepo-cli` development.

## Project overview

`oarepo-cli` is a Python CLI tool for scaffolding and developing OARepo repositories (Invenio RDM instances) and libraries (Python packages). It replaces legacy bash scripts with a single executable written in Python 3.14.

**Core components:**

- `oarepo_cli/cli/` — Typer-based command implementations (`new`, `repository`, `library`)
- `oarepo_cli/core/` — Configuration, context discovery, error handling, platform detection
- `oarepo_cli/services/` — Business logic (venv, testing, linting, subprocess execution, services lifecycle)
- `oarepo_cli/adapters/` — External tool interfaces
- `oarepo_cli/configuration/` — Constants and bundled configuration templates
- `oarepo_cli/ui/` — Console output formatting

**Important constraints:**

- Python 3.14 only (`requires-python = ">=3.14,<3.15"`)
- Uses CESNET-patched `invenio-cli` from private registry (see `pyproject.toml`)
- Never use `subprocess` with `shell=True` — always pass argument lists
- All source files require SPDX headers and `from __future__ import annotations`

## Repository layout

```
oarepo-cli/
├── oarepo_cli/          # Main package
│   ├── cli/             # Command-line interface layer
│   ├── core/            # Core utilities and abstractions
│   ├── services/        # Business logic and orchestration
│   ├── adapters/        # External tool wrappers
│   ├── configuration/   # Constants and templates
│   └── ui/              # Console output
├── tests/
│   ├── unit/            # Fast, isolated unit tests
│   ├── integration/     # Slower tests hitting real tools
│   ├── testlib/         # Small hand-written fixture library
│   ├── testrepo/        # Generated repository fixture (gitignored)
│   └── conftest.py      # Shared fixtures
├── pyproject.toml       # Project metadata, dependencies, tool config
├── uv.lock              # Dependency lockfile (committed)
├── run.sh               # Dogfooded entry point (uses oarepo-cli itself)
└── ty.toml              # Type checker configuration
```

**Do not manually edit:**

- `uv.lock` — managed by `uv`
- `tests/testrepo/` — generated on-demand by tests
- `.venv/` — managed by `uv`/`run.sh`
- `htmlcov/`, `.coverage`, `.pytest_cache/`, `__pycache__/` — test artifacts

## Environment and setup

This project uses `uv` for dependency management.

**Initial setup:**

```bash
uv sync --all-groups
```

Or use the dogfooded `run.sh` wrapper (creates `.venv` and installs on first use):

```bash
./run.sh check
```

**Python version:** 3.14 exactly (enforced in `pyproject.toml`)

**Dependency groups:**

- `dev` — development tools (ruff)
- `tests` — pytest, pytest-cov, pytest-subprocess, pytest-mock
- `oarepo14` — version detection sentinel (never installed)

## Running the project

The CLI is installed as `oarepo-cli`. During development, run it via `uv`:

```bash
uv run oarepo-cli --help
uv run oarepo-cli new my-repo
uv run oarepo-cli library test
uv run oarepo-cli repository install
```

Or use `run.sh`, which dogfoods the CLI's own `library` commands:

```bash
./run.sh test
./run.sh check
./run.sh format
```

## Tests

**Run all tests:**

```bash
uv run pytest
```

Or via `run.sh`:

```bash
./run.sh test
```

**Run targeted tests during development:**

```bash
# Single file
uv run pytest tests/unit/test_config.py

# Single test
uv run pytest tests/unit/test_config.py::test_default_values_for_all_configs

# By marker
uv run pytest -m "not slow"
uv run pytest -m integration

# By keyword
uv run pytest -k "test_venv"
```

**Pytest markers:**

- `slow` — expensive tests (deselect with `-m "not slow"`)
- `integration` — tests hitting real tools (uv, docker, invenio-cli)
- `characterization` — snapshot tests documenting current behavior

**Test organization:**

- `tests/unit/` — fast, isolated unit tests
- `tests/integration/` — slower tests that spawn real subprocesses
- `tests/testlib/` — small hand-written Python library fixture (committed)
- `tests/testrepo/` — full Invenio RDM repository fixture (generated on-demand, gitignored)

**Fixtures:**

- `testlib_project` — path to committed `tests/testlib/`
- `clean_testlib` — `testlib_project` with cleanup before/after each test
- `testrepo_project` — path to generated repository (session-scoped, creates once)
- `clean_testrepo` — `testrepo_project` with install state reset per test
- `test_context` — pre-configured `ProjectContext` for `testlib`
- `strip_ansi` — function to remove ANSI codes from CLI output

**Coverage:**

Coverage is enabled by default in `pyproject.toml` (`--cov=oarepo_cli`). HTML report written to `htmlcov/`.

Disable coverage for faster iteration:

```bash
uv run pytest --no-cov
```

**External dependencies:**

Integration tests require:

- `uv` / `uvx` on PATH
- Docker (for services tests)
- `git` (for repository scaffolding tests)

**Parallel execution:**

Not currently configured. Run serially.

## Code quality

**Format code:**

```bash
./run.sh format
```

**Lint (auto-fix):**

```bash
./run.sh lint
```

**Check (read-only, for CI):**

```bash
./run.sh check
```

This runs:

1. Ruff linting (read-only)
2. Ruff formatting check (read-only)
3. License header check (read-only)
4. `from __future__ import annotations` check (read-only)
5. `ty` type checking

All checks must pass before completing a task.

**Available commands:**

| Command | Description |
|---------|-------------|
| `./run.sh check` | Run all checks in read-only mode (CI-safe) |
| `./run.sh format` | Format code with ruff (rewrites files) |
| `./run.sh lint` | Run ruff + ty with auto-fixes |
| `./run.sh test` | Run pytest with coverage |

Or via the CLI itself:

```bash
uv run oarepo-cli library check
uv run oarepo-cli library format
uv run oarepo-cli library lint
```

## Coding conventions

**File headers:**

Every `.py` file must start with:

```python
# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

from __future__ import annotations
```

**Imports:**

- Use `from __future__ import annotations` in all files
- Use `TYPE_CHECKING` guard for imports only needed for type hints
- Group: stdlib, third-party, first-party (ruff enforces this)

**Subprocess execution:**

- Never use `shell=True`
- Always pass command as a list/sequence
- Use `oarepo_cli.services.process.run()` for most subprocess needs
- Use `oarepo_cli.services.process.exec_replace()` for terminal replacement (e.g., shells)

**Type hints:**

- Use type hints for all function signatures
- Use `Path` from `pathlib`, not strings for file paths
- Prefer `collections.abc` types (`Sequence`, `Mapping`) over concrete types

**Error handling:**

- Raise `OARepoError` subclasses for domain errors (see `core/errors.py`)
- Use `ProcessExecutionError` for subprocess failures
- Use `ValidationError` for configuration/input validation
- Provide actionable error messages

**Testing:**

- No test classes — use plain `test_*` functions
- Use fixtures for shared setup
- Name tests descriptively: `test_<what>_<when>_<expected>`
- Mock external tools in unit tests; use real tools in integration tests
- Do not use `pytest.raises(Exception)` — always specify the exact exception type

**Docstrings:**

- All public functions/classes require docstrings
- Use Google-style docstrings for consistency
- Explain *what* and *why*, not *how* (code shows how)

**CLI commands:**

- Use Typer decorators and type hints
- Put command implementations in `cli/*.py`
- Delegate business logic to `services/*.py`
- Use `@with_context_and_console` decorator for common patterns
- Follow existing patterns: quiet mode, error handling, exit codes

## Architecture and design constraints

**Layering:**

```
cli/ → services/ → core/
  ↓       ↓          ↓
 ui/   adapters/  configuration/
```

- `cli/` calls `services/`, never the reverse
- `services/` contains business logic, not CLI concerns
- `core/` is foundation utilities (config, context, errors, platform)
- `adapters/` wraps external tools (not yet heavily used)
- `configuration/` provides constants and templates
- `ui/` handles console output formatting

**Context and configuration:**

- Use `ProjectContext` (from `core/context.py`) to represent discovered project state
- Use `CliConfig` (from `core/config.py`) for environment variables and pyproject.toml settings
- Always discover context from the current directory (don't hardcode paths)
- Pass `ProjectContext` explicitly; avoid globals

**Subprocess execution:**

- Use `services/process.py::run()` for all subprocess calls
- Use `ProcessOutputMode.CAPTURE` for silent execution
- Use `ProcessOutputMode.FORWARD` for visible real-time output
- Use `ProcessOutputMode.INTERACTIVE` for interactive commands (shells)
- Handle `ProcessExecutionError` at the CLI layer, not in services

**Services lifecycle:**

- Docker services are managed via `ServicesLifecycleManager`
- Services are started/stopped automatically by test orchestrator
- Connection details written to `.env-services`

**Do not:**

- Use `shell=True` in subprocess calls (security risk, harder to debug)
- Introduce parallel implementations of existing abstractions
- Hardcode paths or Python binaries (use context discovery)
- Add unnecessary dependencies
- Create test classes (use plain functions)
- Weaken tests to make them pass
- Skip failing tests without understanding root cause

## Dependencies

**Add a runtime dependency:**

```bash
uv add <package>
```

**Add a dev dependency:**

```bash
uv add --group dev <package>
```

**Add a test dependency:**

```bash
uv add --group tests <package>
```

**Remove a dependency:**

```bash
uv remove <package>
```

**Update lockfile after manual edits:**

```bash
uv lock
```

**Guidelines:**

- Justify new runtime dependencies (prefer stdlib or existing deps)
- Do not manually edit `uv.lock`
- Commit lockfile changes with dependency declaration changes
- Use explicit version constraints in `pyproject.toml` when needed

## Testing expectations for changes

**For bug fixes:**

1. Reproduce the issue if practical
2. Add or identify a regression test that fails before the fix
3. Implement the minimal correct fix
4. Verify the regression test passes
5. Run broader tests in the affected area

**For new features:**

1. Follow existing architecture and patterns
2. Add tests covering expected behavior and edge cases
3. Run targeted tests during development
4. Run full validation before completion

**For refactoring:**

1. Ensure tests pass before starting
2. Make incremental changes
3. Run tests after each logical step
4. Verify behavior is unchanged

**Do not:**

- Add artificial tests for purely mechanical changes
- Skip or remove failing tests
- Weaken test assertions to make them pass
- Test private implementation details (test public interfaces)

## Agent workflow

**Standard workflow for autonomous agents:**

1. **Read before modifying:** Understand relevant code, tests, and architecture
2. **Check for nested `AGENTS.md`:** None currently exist, but check if added
3. **Identify the smallest change:** Solve the task with minimal, focused modifications
4. **Preserve existing behavior:** Don't change APIs or behavior unless explicitly required
5. **Implement the change:** Follow existing patterns and conventions
6. **Add or update tests:** Ensure new code is tested; update tests if behavior changed
7. **Run targeted tests:** Iterate with fast feedback (`pytest tests/unit/test_specific.py`)
8. **Run code quality checks:** `./run.sh check` or `uv run oarepo-cli library check`
9. **Run broader tests:** `./run.sh test` or appropriate subset before completion
10. **Review the diff:** Check for unintended changes, formatting issues, missing files

**Do not:**

- Refactor unrelated code while solving a specific task
- Change file locations or names without explicit requirement
- Modify generated files (`.venv`, `uv.lock` manually, coverage reports)
- Add comments that merely restate the code

## Validation before completion

**Mandatory checks (in order):**

1. **Format check:** `./run.sh format`
2. **Lint check:** `./run.sh check`
3. **Targeted tests:** Run tests for affected modules
4. **Full test suite:** `./run.sh test` (or `uv run pytest`)

**Conditional checks:**

- If editing integration tests, ensure Docker is available and no containers are running apart from the docker-services-cli ones. If there are, ask user to stop them first.
- If changing CLI commands, test `--help` output
- If modifying context discovery, test both library and repository projects

**Exit cleanly if:**

- All checks pass
- No unintended file changes in `git diff`
- Test coverage did not decrease

## Git and diff hygiene

**Do:**

- Keep changes narrowly scoped to the task
- Preserve existing formatting outside modified areas
- Review `git diff` before completion
- Never commit `uv.lock`

**Do not:**

- Modify unrelated files
- Discard user changes
- Rewrite git history
- Commit generated files (`.venv`, `__pycache__`, `htmlcov`, `.coverage`, `.pytest_cache`, `uv.lock`)
- Create commits or branches unless explicitly asked
- Mass-format unrelated code
- Commit on the main branch or rdm-* or maint-* branches

**Generated/cache files (never commit):**

- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- `.ruff_cache/`
- `htmlcov/`
- `.coverage`, `.coverage.*`
- `coverage.xml`
- `junit.xml`
- `tests/testrepo/` (generated by tests)
- `oarepo-tmp/` (temporary working directory)
- `uv.lock`

## Safety and destructive operations

**Potentially destructive operations:**

- Deleting files or directories
- `repository reset` (destroys repository data)
- `repository services destroy` (destroys Docker volumes)
- `library upgrade` (deletes and recreates venv)
- Modifying `pyproject.toml` dependency declarations
- Any operation that runs `docker compose down -v`

**Do not run destructive operations unless:**

- Explicitly required by the user's task
- Part of test cleanup (in fixture teardown)
- Clearly documented in the command implementation

## Agent decision rules

**Core principles:**

- **Minimal change:** Prefer the smallest correct fix over comprehensive rewrites
- **Root causes:** Fix root causes rather than masking symptoms
- **Backward compatibility:** Preserve it unless explicitly told otherwise
- **Reuse abstractions:** Search for existing patterns before creating new ones
- **No speculation:** Don't introduce abstractions or features not yet needed
- **No silent changes:** Don't change public behavior without explicit discussion
- **Respect tests:** Treat tests as specifications; don't weaken them to pass
- **Verify failures:** Understand why tests fail before removing/skipping them
- **Search first:** Before inventing utilities, search the codebase for existing solutions
- **Update docs:** When public behavior or workflows change, update relevant documentation

**When stuck:**

1. Re-read the relevant code and tests
2. Run targeted tests to isolate the issue
3. Check for similar patterns elsewhere in the codebase
4. Ask the user for clarification if the requirement is ambiguous
