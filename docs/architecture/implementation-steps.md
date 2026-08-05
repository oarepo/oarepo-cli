# OARepo CLI Implementation Steps

## Overview

This document provides a step-by-step implementation plan for the OARepo CLI Python application. Each step is designed to be:
- **Self-contained**: Completes a logical unit of functionality
- **Test-driven**: Ends with implemented and passing tests
- **Verifiable**: Can be independently validated before proceeding
- **Incremental**: Builds on previous steps without requiring future knowledge

## Usage

Track progress by updating the status flags:
- `[ ]` - Not started
- `[~]` - In progress
- `[x]` - Completed (code + tests passing)
- `[!]` - Blocked or requires attention

---

## Roadmap

Per-phase deliverable. Steps within a phase can often be parallelized; see each phase below for the detailed, verifiable checklist. Phases are worked in order, with no fixed schedule.

| Phase | Deliverable |
|-------|-------------|
| 0: Project Setup & Infrastructure | Project scaffolding, tooling (ruff, ty, pytest), and pre-commit hooks in place |
| 1: Core Domain Models | pyproject.toml parsing, version resolution, config loading, and context discovery working |
| 2: Virtual Environment Management | `oarepo-cli --help` matches shell script structure; venvs created/managed via `uv` with lock-file concurrency protection |
| 3: Library Commands | All library commands functional, passing characterization tests |
| 4: Repository Commands | All repository commands functional |
| 5: Repository Installer | `oarepo-cli new <name>` works identically to the shell script |
| 6: Hardening & Polish | Signal handling, structured logging, benchmarks, and full characterization parity |
| 7: Release Preparation | CI/CD pipeline live; v1.0.0 tagged and published |

---

## Phase 0: Project Setup & Infrastructure

### Step 0.1: Initialize Project Structure
**Goal**: Create basic project layout with tooling configured.

- [x] Create directory structure (`oarepo_cli/`, `tests/`, `docs/`)
- [x] Initialize `pyproject.toml` with Poetry/pip configuration
- [x] Configure `ruff` for linting and formatting
- [x] Configure `mypy` or `ty` for type checking
- [x] Configure `pytest` with coverage settings
- [x] Add pre-commit hooks for ruff, mypy/ty
- [x] Create `.gitignore` and basic CI workflow file

**Deliverables**:
- [x] Project scaffolding committed to git
- [x] `make` targets or scripts for common operations (test, lint, format)
- [x] Pre-commit hooks installed and working

**Tests**:
- [x] `pytest --co` shows no errors
- [x] `ruff check .` passes with zero issues
- [x] `ty check oarepo_cli/` (or mypy) passes with zero errors
- [x] `pre-commit run --all-files` succeeds

---

### Step 0.2: Core Error Handling System
**Goal**: Establish exception hierarchy and error handling patterns.

- [x] Define `core/errors.py` with base `OARepoError` class
- [x] Create specific exceptions: `ConfigurationError`, `VersionMismatchError`, `ProcessExecutionError`, `FileNotFoundError`, `ValidationError`, `LockAcquisitionError`
- [x] Implement exit code constants for each exception type
- [x] Add `ProcessExecutionError` with command, returncode, stdout, stderr attributes
- [x] Create utility function `safe_run()` that wraps process execution with consistent error handling

**Deliverables**:
- [x] Complete exception hierarchy in `core/errors.py`
- [x] Documented error handling patterns

**Tests** (`tests/core/test_errors.py`):
- [x] Test each exception type can be raised and caught
- [x] Test `ProcessExecutionError` formats message correctly
- [x] Test `safe_run()` raises on non-zero exit codes
- [x] Test `safe_run()` returns result on success
- [x] Test custom exit codes are preserved

---

### Step 0.3: Platform Detection Utilities
**Goal**: Abstract platform-specific behavior.

- [x] Implement `core/platform.py` with `PlatformDetector` class
- [x] Methods: `is_macos()`, `is_linux()`, `is_windows()`, `get_venv_bin_dir()`, `get_venv_python()`, `needs_dyld_fix()`, `get_celery_pool_recommendation()`
- [x] Add platform-specific test fixtures

**Deliverables**:
- [x] Platform detection utilities
- [x] Centralized platform logic

**Tests** (`tests/core/test_platform.py`):
- [x] Test platform detection methods return correct values
- [x] Test `get_venv_bin_dir()` returns `bin` on Unix, `Scripts` on Windows
- [x] Test `get_celery_pool_recommendation()` returns `threads` on macOS

---

### Step 0.4: Process Execution Helper
**Goal**: Provide a single, safe way to run subprocesses, used directly by every service.

Subprocess execution has exactly one real implementation (the stdlib `subprocess` module), so it's exposed as plain module-level functions rather than a `Protocol`/`ABC` with constructor-injected implementations — a swappable interface only pays for itself once there's a second real implementation to swap in. The functions centralize real, non-trivial logic that's worth not duplicating at every call site: never `shell=True`, UTF-8 decoding, timeout → `TimeoutExceeded` translation with partial-output capture, env-dict merging, optional output streaming.

For unit-level tests, call `run()`/`stream()`/`get_output()` directly against real, trivial, always-available commands (`echo`, `true`, `false`, `python3 -c`) — no fixture needed. Services that shell out to slow, optional, side-effecting external tools (`uv`, `docker-services-cli`, `copier`, `invenio-cli`) are exercised for real in integration tests against the `tests/testlib/` fixture project (see Step 2.2 and onward). [`pytest-subprocess`](https://pytest-subprocess.readthedocs.io/)'s `fake_process` fixture, which patches `subprocess.Popen` process-wide, remains available at the **OS boundary** for the rare unit test that needs to simulate a specific absent/failing binary without a real one on hand.

- [x] Define `services/process.py` with `ProcessResult` dataclass
- [x] Implement `run()`, `stream()`, `get_output()` as plain module-level functions wrapping `subprocess.run`/`Popen`
- [x] Never use `shell=True`; always pass args as list
- [x] Implement timeout handling → `TimeoutExceeded`, with partial output captured
- [x] Ensure proper encoding handling (UTF-8)
- [x] Add `pytest-subprocess` as a dev dependency, for the rare unit test that needs to simulate a specific absent/failing binary

**Deliverables**:
- [x] `services/process.py`: production-ready, safe subprocess execution
- [x] Safe execution without shell injection risks

**Tests** (`tests/unit/test_process.py`):
- [x] Test successful command execution, using trivial, always-available real commands (`echo`, `true`, `false`, `python3 -c`) — call `process.run(...)` directly, no fixture needed
- [x] Test error capture on failure
- [x] Test `check=True/False` behavior
- [x] Test timeout raises `TimeoutExceeded`
- [x] Test environment variable inheritance
- [x] Test working directory parameter
- [x] Test shell injection is prevented (literal output, not executed)
- [x] Test `get_output()` returns stripped stdout
- [x] Test `stream()` yields lines

---

## Phase 1: Core Domain Models

### Step 1.1: PyProject.toml Reader
**Goal**: Parse pyproject.toml with typed accessors using tomllib.

- [x] Implement `services/pyproject_reader.py` with `PyProjectData` dataclass
- [x] Properties: `name`, `homepage`, `requires_python`, `dependencies`, `optional_dependencies`, `oarepo_versions`, `default_extras`
- [x] Implement `PyProjectReader` class with `read()` method
- [x] Handle missing file and invalid TOML errors

**Deliverables**:
- [x] Robust TOML parsing with typed interface
- [x] No grep/sed/awk parsing

**Tests** (`tests/unit/test_pyproject_reader.py`):
- [x] Test minimal project parsing
- [x] Test extraction of oarepo versions from dependencies
- [x] Test default extras parsing
- [x] Test missing file raises `ConfigurationError`
- [x] Test invalid TOML raises `ConfigurationError`
- [x] Test multiple oarepo versions extracted correctly

---

### Step 1.2: Version Resolver
**Goal**: Determine compatible Python and OARepo versions.

- [x] Implement `services/version_resolver.py` with `VersionInfo` dataclass
- [x] `VersionResolver` class with methods: `resolve_from_pyproject()`, `find_available_python()`, `validate_compatibility()`
- [x] Parse `requires-python` constraint into discrete version list
- [x] Check system for available Python binaries
- [x] Select highest available Python version within constraints

**Deliverables**:
- [x] Version resolution logic
- [x] Python availability detection

**Tests** (`tests/unit/test_version_resolver.py`):
- [x] Test version range parsing (e.g., `>=3.12,<3.15` → `["3.12", "3.13", "3.14"]`)
- [x] Test finding highest available Python
- [x] Test fallback to lower version if highest unavailable
- [x] Test `VersionMismatchError` when no compatible version found
- [x] Test OARepo-Python compatibility validation

---

### Step 1.3: Configuration Model
**Goal**: Typed configuration from env vars and files.

- [x] Implement `core/config.py` with dataclasses: `BuildConfig`, `TestConfig`, `VenvConfig`, `PythonConfig`, `OARepoConfig`, `ServicesConfig`, `ModelConfig`, `TranslationsConfig`, `CeleryConfig`, `LicenseConfig`, `SecurityConfig`, `CliConfig`
- [x] `CliConfig.from_env()` reads environment variables
- [x] `CliConfig.from_pyproject()` reads `[tool.oarepo-cli]` section
- [x] Merge strategy: defaults < pyproject < env vars < CLI flags

**Deliverables**:
- Complete configuration model
- Multi-source configuration loading

**Tests** (`tests/unit/test_config.py`):
- [x] Test default values for all configs
- [x] Test environment variable overrides
- [x] Test pyproject.toml overrides
- [x] Test precedence order (CLI > env > pyproject > defaults)
- [x] Test invalid config values raise `ValidationError`

---

### Step 1.4: Project Context Discovery
**Goal**: Discover and validate project context at startup.

- [x] Implement `core/context.py` with `ProjectContext` dataclass
- [x] Fields: `root_directory`, `pyproject_path`, `venv_path`, `python_binary`, `oarepo_version`
- [x] Computed properties: `code_directories`, `instance_path`, `assets_path`
- [x] `ContextBuilder` fluent API for construction with validation
- [x] Auto-discovery of `pyproject.toml` in cwd and parents

**Deliverables**:
- Immutable project context object
- Validation during discovery

**Tests** (`tests/unit/test_context.py`):
- [x] Test context discovery from valid project
- [x] Test error when pyproject.toml missing
- [x] Test computed properties (code directories)
- [x] Test builder pattern with overrides
- [x] Test validation fails for incompatible versions

---

## Phase 2: Virtual Environment Management

### Step 2.1: Venv Requirements Model
**Goal**: Define requirements for virtual environment setup.

- [x] Implement `services/venv.py` with `VenvRequirements` dataclass
- [x] Fields: `python_binary`, `oarepo_version`, `extras`, `editable`
- [x] Validation: ensure Python version supports OARepo version

**Deliverables**:
- Venv requirements model
- Validation logic

**Tests** (`tests/unit/test_venv_requirements.py`):
- [x] Test requirements creation with defaults
- [x] Test validation of Python-OARepo compatibility
- [x] Test editable flag handling

---

### Step 2.2: Virtual Environment Manager
**Goal**: Create and manage virtual environments via uv.

- [x] Implement `VirtualEnvironmentManager` class
- [x] Method: `ensure_venv(requirements, force=False)` → Path
- [x] Method: `upgrade_environment()` → None
- [x] Method: `cleanup()` → None
- [x] Use `uv venv` for creation
- [x] Use `uv pip install` for dependencies
- [x] Handle editable vs wheel builds

**Deliverables**:
- Venv management service
- uv integration

**Tests** (`tests/integration/test_venv_workflow.py`):
- [x] Test venv creation against real `uv`/`pip` calls (project_root passed explicitly, no cwd dependency)
- [x] Test setuptools installed first
- [x] Test oarepo installed with correct version constraint
- [x] Test editable vs non-editable modes
- [x] Test force recreation removes existing venv
- [x] Test skip creation if venv already exists

---

### Step 2.3: Lock File Concurrency Control
**Goal**: Prevent concurrent executions from corrupting state.

- [x] Implement `utils/locks.py` with `FileLock` class
- [x] Acquire lock with timeout
- [x] Release lock (idempotent)
- [x] Handle stale locks
- [x] Context manager support

**Deliverables**:
- File-based locking mechanism
- Concurrent execution protection

**Tests** (`tests/unit/test_locks.py`):
- [x] Test lock acquisition
- [x] Test lock release
- [x] Test concurrent acquisition fails
- [x] Test timeout raises `LockAcquisitionError`
- [x] Test stale lock recovery
- [x] Test idempotent release

---

## Phase 3: Library Commands

### Step 3.1: CLI Skeleton with Typer
**Goal**: Set up Typer CLI with root command and subcommand groups.

- [x] Install Typer and Pydantic
- [x] Implement `cli/main.py` with root `app`
- [x] Add global options: `--verbose`, `--config`, `--cd`
- [x] Create `cli/library.py` with empty `library_app`
- [x] Create `cli/repository.py` with empty `repository_app`
- [x] Register subcommands with root app
- [x] Verify `oarepo-cli --help` displays correctly

**Deliverables**:
- Working CLI skeleton
- Help text matches shell script structure

**Tests** (`tests/unit/test_cli_skeleton.py`):
- [x] Test `--help` shows all commands
- [x] Test unknown command returns exit code 2
- [x] Test global options parsed correctly
- [x] Test `--version` displays package version

---

### Step 3.2: Library `venv` Command
**Goal**: Implement `oarepo-cli library venv` command.

- [x] Implement `library_venv()` function in `cli/library.py`
- [x] Options: `--force`, `--no-editable`
- [x] Inject `ProjectContext` and `CliConfig`
- [x] Call `VirtualEnvironmentManager.ensure_venv()`
- [x] Display success message with venv path

**Deliverables**:
- Working `venv` command
- Matches shell script behavior

**Tests** (`tests/integration/test_library_venv.py`):
- [x] Test venv created in temp project
- [x] Test `--force` recreates existing venv
- [x] Test `--no-editable` builds wheel instead
- [x] Test help text matches shell script
- [x] Characterization test: exit code matches bash
- [x] Additional: Test VIRTUAL_ENV stripping in `tests/services/test_process_venv_isolation.py`

---

### Step 3.3: Library `upgrade` Command
**Goal**: Implement `oarepo-cli library upgrade` command.

- [x] Implement `library_upgrade()` function
- [x] Stop services (if running)
- [x] Remove existing venv
- [x] Clean uv cache
- [x] Recreate venv with `ensure_venv(force=True)`

**Deliverables**:
- Working `upgrade` command

**Tests** (`tests/integration/test_upgrade_workflow.py`):
- [x] Test venv removed and recreated
- [x] Test cache cleaned
- [x] Test services stopped before upgrade
- [x] Test success message displayed
- [x] Test cache clean failure handling

---

### Step 3.4: Services Lifecycle Manager
**Goal**: Manage Docker service lifecycle.

- [x] Implement `services/services_lifecycle.py` with `ServicesLifecycleManager`
- [x] Method: `start_services(config)` → env dict
- [x] Method: `stop_services()` → None
- [x] Use `docker-services-cli up/down`
- [x] Write/read `.env-services` file
- [x] Support DB, search, MQ, cache, S3 options
- [x] Update 3.3 steps with service checks

**Deliverables**:
- Service lifecycle management
- Environment file handling

**Tests** (`tests/integration/test_services_lifecycle.py`):
- [x] Test services start against real `docker-services-cli` (via `uvx`, always available in this project's environment)
- [x] Test `.env-services` file written
- [x] Test services stop removes file
- [x] Test environment variables loaded from file
- [x] Test skip services functionality

---

### Step 3.5: Library `start`/`stop` Commands
**Goal**: Implement service start/stop commands.

- [x] Implement `library_start()` and `library_stop()` functions
- [x] Delegate to `ServicesLifecycleManager`
- [x] Display colored status messages

**Deliverables**:
- Start/stop commands

**Tests** (`tests/integration/test_library_services.py`):
- [x] Test start creates env file
- [x] Test stop removes env file
- [x] Test exit codes match bash

---

### Step 3.5.1: Interactive Output for Long-Running Commands
**Goal**: Enable real-time output for long-running commands with --quiet option.

- [x] Add `--quiet` flag to commands that run long operations (venv, upgrade, etc.)
- [x] Update `process.run()` to support interactive mode (no capture_output)
- [x] Use PTY for interactive subprocesses when appropriate
- [x] By default, show real-time output (visible to user)
- [x] With `--quiet`, suppress output (capture and silence)
- [x] Apply to commands:
  - `library venv` - `uv pip install` can take long time
  - `library upgrade` - cache clean + full reinstall
  - Future commands with long operations

**Deliverables**:
- Interactive output for long-running commands
- `--quiet` flag support
- Real-time visibility of subprocess output

**Tests** (`tests/integration/test_quiet_mode.py`):
- [x] Existing tests pass with new interactive mode
- [x] Test venv command shows output by default (manual verification)
- [x] Test venv --quiet suppresses output (manual verification)
- [x] Test upgrade command shows output by default (manual verification)
- [x] Test upgrade --quiet suppresses output (manual verification)

---

### Step 3.6: Test Orchestrator
**Goal**: Orchestrate pytest execution with services.

- [x] Implement `services/test_orchestrator.py` with `TestOrchestrator` class
- [x] Method: `run_tests(pytest_args=[], coverage=False, skip_services=False)` → CommandResult
- [x] Start services if not skipped
- [x] Install pytest-cov if coverage enabled
- [x] Run pytest with appropriate args
- [x] Stop services after tests
- [x] Return structured result

**Deliverables**:
- Test orchestration service
- Coverage support

**Tests** (`tests/integration/test_test_orchestrator.py`):
- [x] Test services start before pytest
- [x] Test services stop after pytest
- [x] Test coverage flags added when enabled
- [x] Test skip_services skips start/stop
- [x] Test failure status returned on pytest failure
- [x] Integration test: run real pytest in temp project

---

### Step 3.7: Library `test` Command
**Goal**: Implement `oarepo-cli library test` command.

- [x] Implement `library_test()` function
- [x] Options: `--skip-services`, `--with-coverage`, pass-through args via `ctx.args`
- [x] Use `ignore_unknown_options=True` to allow pytest flags without `--` separator
- [x] Create orchestrator and call `run_tests()`
- [x] Display results with colors
- [x] Exit with pytest exit code

**Deliverables**:
- Working `test` command

**Tests** (`tests/integration/test_library_test.py`):
- [x] Test tests run successfully
- [x] Test coverage enabled with flag
- [x] Test skip-services works
- [x] Test extra pytest args passed through (no `--` needed)
- [x] Test exit code on failure
- [x] Test combined flags
- [x] Test interspersed flags

---

### Step 3.8: Library `clean` Command
**Goal**: Implement `oarepo-cli library clean` command.

- [x] Implement `library_clean()` function
- [x] Stop services
- [x] Remove venv directory
- [x] Remove `.env-services` file
- [x] Display cleanup summary

**Deliverables**:
- Working `clean` command

**Tests** (`tests/integration/test_cleanup_workflow.py` and `tests/integration/test_library_clean.py`):
- [x] Test venv removed
- [x] Test env-services file removed
- [x] Test services stopped
- [x] Test idempotent (works even if nothing exists)
- [x] Integration tests for full command execution

---

### Step 3.9: Library `shell` and `invenio` Commands
**Goal**: Implement shell and invenio passthrough commands.

- [x] Implement `library_shell()` and `library_invenio()` functions
- [x] Options: `--skip-services`
- [x] Ensure venv exists
- [x] Start services if not skipped
- [x] Activate venv and exec bash/invenio
- [x] Pass through all arguments

**Deliverables**:
- Shell and invenio commands
- Argument passthrough

**Tests** (`tests/integration/test_library_passthrough.py`):
- [~] Test shell starts interactive bash
- [~] Test invenio runs with args
- [~] Test skip-services skips service start
- [~] Test arguments passed correctly

**Note**: Commands are implemented and functional. Tests are partially complete but need fixture refinement for subprocess mocking. The core functionality (venv activation, environment variable loading, argument passthrough via os.execve) is working correctly.

---

### Step 3.9.1: Migrate Library `lint` Type Checking from mypy/pyright to `ty`
**Goal**: Replace `mypy` and `pyright` in `library lint` with `ty` alone, so the CLI bundles and invokes a single type checker instead of two.

This step was **not part of the original architecture design** — `00-main-architecture.md` §1.1 and §1.5 originally described `lint` as running `mypy`/`pyright`, with a "planned change" note pointing here. Both sections have been updated to describe `ty` as the shipped implementation now that this step is complete.

- [x] Remove `mypy`, `pyright`, `types-pyyaml`, `types-requests` from oarepo-cli's dependencies (`pyproject.toml`)
- [x] Add `ty` as a runtime dependency of oarepo-cli (previously a `dev`-only dependency for oarepo-cli's own type checking; moved to core `dependencies` so `library lint` can invoke it too, and dropped from `dev` since core deps are always installed regardless of extras)
- [x] Replace the `mypy`/`pyright` invocations in `LintRunner.run_lint()` (`oarepo_cli/services/lint.py`) with a single `ty check` invocation against `code_directories[0]`
- [x] Remove `.mypy.ini` generation; generate a `ty.toml` in the target project instead. Note: by the time this step landed, `RUFF_TOML`/`MYPY_INI` were no longer Python string constants in `lint.py` — an earlier refactor moved them to real data files under `oarepo_cli/configuration/` (`ruff.toml.tmpl`, loaded lazily via `importlib.resources`). Followed that existing pattern instead of the string-constant one this bullet originally described: added `oarepo_cli/configuration/ty.toml.tmpl`, loaded via `resources.read_text("ty.toml.tmpl")`. The `.tmpl` suffix matters — a bare `ruff.toml`/`ty.toml` inside `oarepo_cli/configuration/` gets auto-discovered by ruff (confirmed) and could plausibly confuse `ty` (not confirmed either way, but not worth the risk) when linting/type-checking oarepo-cli's own source in that directory
- [x] Decide `ty`-equivalent handling for the old `--ignore-missing-imports`/`--exclude os-v2` mypy flags and pyright's `--pythonpath <venv_python>` (or confirm they're no longer applicable) — see mapping below
- [x] Update `docs/architecture/00-main-architecture.md` §1.1 and §1.5 to remove the "planned change" notes added for this step and describe `ty` as the actual implementation

**Resolved mypy/pyright → `ty` mapping** (researched against `ty` 0.0.65 and
[docs.astral.sh/ty](https://docs.astral.sh/ty/), verified empirically — see
below — rather than guessed from defaults):

| Old setting | Where | `ty` equivalent | Notes |
|---|---|---|---|
| `--ignore-missing-imports` | mypy CLI flag | `ty.toml`: `[rules]` → `unresolved-import = "ignore"` | Confirmed by test: without it, an unresolvable import errors; with it, `ty check` passes. |
| `--exclude os-v2` | mypy CLI flag | `ty.toml`: `[src]` → `exclude = ["**/os-v2/**"]` | A bare `"os-v2"` pattern does **not** exclude nested contents when the parent directory is passed explicitly on the command line (verified empirically — `ty check src/cleanlib` with `exclude = ["os-v2"]` still reported an error inside `src/cleanlib/os-v2/`); needed the `**/os-v2/**` glob form to actually exclude it. |
| pyright `--pythonpath <venv_python>` | pyright CLI flag | `ty check --python <venv_python>` CLI flag | Kept as a CLI flag rather than baked into `ty.toml`, same as the old pyright invocation — it's per-invocation (the target project's venv path), not a static ruleset preference. |
| `warn_return_any` | `.mypy.ini` | **Dropped, no equivalent** | `ty`'s rule set (checked against the full list at docs.astral.sh/ty/reference/rules/) has no rule for "function returns a value ty inferred as `Any`" — `ty`'s `invalid-return-type` rule checks assignability, not implicit-`Any` leakage, which is a different, mypy-specific inference-strictness concept. |
| `warn_unreachable` | `.mypy.ini` | **Dropped, no equivalent** | No unreachable-code rule exists in `ty`'s rule set at all (confirmed against the full rule list). |
| `warn_unused_configs` | `.mypy.ini` | **Dropped, not applicable** | This warns about stale/unmatched sections in `.mypy.ini` itself — a mypy-config-file-specific meta-check with no meaning under `ty`'s config format. |
| `follow_untyped_imports` | `.mypy.ini` | **Dropped, no equivalent toggle** | Controls whether mypy analyzes untyped third-party packages' source instead of treating them as `Any`; `ty`'s import resolution model doesn't expose an equivalent on/off switch. |

**Deliverables**:
- [x] `library lint` runs `ruff check`, `ruff format --check`, license header check, future annotations check, `ty check` — no `mypy`/`pyright` involved
- [x] Generated `ty.toml` whose rules are traceable back to the specific `.mypy.ini`/mypy-flag/pyright-flag settings they replace (see mapping table above; also documented in the PR description)
- [x] Architecture docs no longer reference `mypy`/`pyright` as the lint type checker

**Tests** (`tests/integration/test_library_lint_format.py`):
- [x] Update `test_lint_passes_on_clean_code`/`test_lint_fails_on_dirty_code` fixtures for `ty`'s diagnostics if they differ from mypy/pyright's — not needed, the existing clean/dirty fixtures pass/fail identically under `ty`; added a new `test_lint_fails_on_type_error` test (return-type mismatch) to exercise the `ty check` step specifically, since the existing dirty-code test only exercises the earlier `ruff check` step
- [x] Test that `library lint` no longer shells out to `mypy`/`pyright` (e.g. no `.mypy.ini` generated) — folded into `test_lint_passes_on_clean_code`, which now asserts `ty.toml` exists and `.mypy.ini` does not

---

### Step 3.10: Library `lint` and `format` Commands
**Goal**: Implement linting and formatting commands.

- [x] Implement `library_lint()` function
- [x] Generate `.ruff.toml` config
- [x] Run `ruff check`, `mypy`, `pyright`
- [x] Check license headers and future annotations
- [x] Implement `library_format()` function
- [x] Run `ruff format` and `ruff check --fix`

**Deliverables**:
- [x] Lint and format commands

**Tests** (`tests/integration/test_library_lint_format.py`):
- [x] Test lint passes on clean code
- [x] Test lint fails on dirty code
- [x] Test format fixes issues
- [x] Test license header check
- [x] Test future annotations check

---

### Step 3.10.2: `library lint`/`format` Fix by Default; New `library check` Command
**Goal**: Make `library lint` and `library format` apply fixes by default, and add a new `library check` command that runs the same checks without ever modifying target project files.

**This is a deliberate divergence from the original bash scripts**, not a
behavior-preservation step — requested explicitly, not derived from
`library_runner.sh`'s `run_linters()`/`format_code()`. The bash scripts had
no "fix vs. check-only" split: `lint` only ever reported problems,
`format` always rewrote files unconditionally. Flag this clearly wherever
this step touches docs that otherwise document behavior-preserving
mappings (`00-main-architecture.md` §1.1, `03-migration-guide.md` §5.5 —
both already updated with "planned" notes pointing here; finish updating
them to describe the shipped behavior once this step lands).

- [x] Add `--fix`/`--no-fix` option to `library lint` (default: `--fix`)
- [x] Add `--fix`/`--no-fix` option to `library format` (default: `--fix`, matching today's always-rewrites behavior)
- [x] `library lint --fix` (default): run `ruff check --fix` instead of a bare `ruff check`. License header check and future-annotations check stay read-only either way — inserting headers/imports is `license-headers`' job (Step 3.11), not `lint`'s
- [x] `library lint --no-fix`: reproduce today's non-destructive behavior exactly (`ruff check`, `ruff format --check`, license header check, future annotations check, `ty check`)
- [x] `library format --no-fix`: run `ruff format --check` instead of rewriting, and skip `ruff check --fix`
- [x] Investigate `ty check --fix` (`ty check --help` lists `--fix`: "Apply fixes to resolve errors") — decide whether `library lint --fix` should use it, and document the decision either way; don't wire it in blind
- [x] Implement new `library check` command: `ruff format --check`, `ruff check` (no `--fix`), license header check, future annotations check, `ty check` (no `--fix`) — i.e. today's `library lint` behavior, preserved under its own name once `lint` itself starts fixing by default. Still generates `.ruff.toml`/`ty.toml` (that's config generation, not "modifying target project files")
- [x] Update `docs/architecture/00-main-architecture.md` §1.1/§1.1.1 to describe the shipped behavior instead of "planned"
- [x] Update `docs/architecture/03-migration-guide.md` §5.5 to describe the shipped behavior instead of "planned"

**Deliverables**:
- [x] `library lint` fixes ruff-autofixable issues by default; `--no-fix` preserves today's report-only behavior exactly
- [x] `library format` gains a `--no-fix` preview mode; `--fix` (default) is unchanged
- [x] New `library check` command, functionally equivalent to `library lint --no-fix`, documented as the CI-safe entry point
- [x] Architecture docs clearly mark this as an intentional divergence, not a bash-compatibility gap

**Tests** (`tests/integration/test_library_lint_format.py`, new `tests/integration/test_library_check.py`):
- [x] Test `library lint` (default `--fix`) auto-fixes an autofixable ruff violation instead of just reporting it
- [x] Test `library lint --no-fix` reports without modifying any file
- [x] Test `library format --no-fix` does not rewrite files, only reports
- [x] Test `library format` (default `--fix`) behavior is unchanged from before this step
- [x] Test `library check` never modifies any file
- [x] Test `library check`'s pass/fail behavior and exit codes match `library lint --no-fix` exactly

---

### Step 3.11: Library `translations`, `license-headers`, `jslint`, `jstest` Commands
**Goal**: Implement remaining library commands.

- [x] Implement `library_translations()` → calls `make-translations`
- [x] Implement `library_license_headers()` → adds SPDX headers to Python files (pure Python implementation, no external tool)
- [x] Implement `library_jslint()` → runs ESLint and Prettier
- [x] Implement `library_jstest()` → sets up and runs Jest
- [x] All commands support `--skip-services` where applicable
- [x] **SPDX migration**: `license-headers` now uses SPDX format, extracts year/org from old-style headers, and replaces them

**Deliverables**:
- [x] Complete set of library commands
- [x] SPDX-format license headers (machine-readable, compact)

**Tests** (`tests/integration/test_library_misc_commands.py`):
- [x] Test each command executes without error
- [x] Test help text for each command
- [x] Characterization tests for key commands
- [x] Test SPDX header addition for files without headers
- [x] Test old-style copyright header replacement with SPDX format

---

### Step 3.12: Library `oarepo-versions` Command
**Goal**: Implement JSON version reporting.

- [x] Implement `library_oarepo_versions()` function
- [x] Parse pyproject.toml for oarepo version from `[tool.oarepo-cli].version`
- [x] Resolve Python versions from constraints
- [x] Output JSON: `{"oarepo_versions": [...], "python_versions": [...], "node_versions": [...]}`

**Deliverables**:
- [x] Version reporting command
- [x] Uses `[tool.oarepo-cli].version` instead of scanning optional-dependencies keys (architectural change documented in 00-main-architecture.md §1.1.2)

**Tests** (`tests/integration/test_library_versions.py`):
- [x] Test JSON output valid
- [x] Test versions extracted correctly
- [x] Test configuration from `[tool.oarepo-cli].version`

**Note**: This approach is **superseded by Step 3.13**, which extracts versions
from dependency constraints instead of requiring explicit configuration. Step
3.12 remains functional but the `[tool.oarepo-cli].version` key is deprecated.

---

### Step 3.13: Refactor `oarepo-versions` to Extract from Dependencies
**Goal**: Replace `[tool.oarepo-cli].version` configuration with automatic extraction from main/optional dependencies.

- [x] Update `PyProjectData.oarepo_versions()` to scan `dependencies` and `optional-dependencies` for `oarepo` package
- [x] Parse version constraints (e.g., `"oarepo>=14.0.0,<15.0.0"` → major version `14`)
- [x] Return list of major versions sorted highest-first
- [x] Support both main dependencies and dev/tests extras
- [x] Remove reliance on `[tool.oarepo-cli].version` key

**Deliverables**:
- [x] Updated `PyProjectData.oarepo_versions` property
- [x] Helper function `_extract_oarepo_version_from_specifier()` using `packaging.requirements`
- [x] Updated command docstring in `library.py`

**Tests** (`tests/unit/test_pyproject_reader.py`, `tests/integration/test_library_versions.py`):
- [x] Test extraction from main dependencies: `oarepo>=14.0.0,<15.0.0` → `[14]`
- [x] Test extraction from optional dependencies (dev, tests extras)
- [x] Test multiple constraints: `oarepo>=13.0.0,<14.0.0` and `oarepo>=14.0.0,<15.0.0` → `[14, 13]` (highest first)
- [x] Test exact version pins: `oarepo==14.0.5` → `[14]`
- [x] Test deduplication across extras
- [x] Test with extras markers: `oarepo[search]>=14.0.0`
- [x] Test invalid constraint format (gracefully ignore/log warning)
- [x] Integration test: JSON output still valid after refactor
- [x] Integration test: multi-version scenario

**Migration impact**:
- Existing `[tool.oarepo-cli].version` configuration is **no longer used** (standard dependencies are the source of truth)
- Projects using standard dependency declarations automatically work without config changes
- See migration guide (§5.6) for details

**Rationale**:
- Eliminates duplicate configuration: the oarepo version is already declared in dependencies
- Aligns with standard Python packaging practices (version constraints live in `[project]` section)
- Supports projects with multiple oarepo versions in different extras (e.g., dev with v14, tests with v13)
- Makes the CLI less opinionated about project structure

---

### Step 3.14: Migrate Library venv/install to `uv sync`
**Goal**: Replace `uv pip install` with `uv sync` for library dependency installation, unifying the approach with repository installation.

- [x] Update `VirtualEnvironmentManager._install_dependencies()` to use `uv sync` instead of `uv pip install`
- [x] Build extras list correctly for `--extra` flags (e.g., `--extra dev --extra tests --extra oarepo14`)
- [x] Ensure `uv.lock` is in `.gitignore` for libraries (already at line 208)
- [x] Update unit tests in `tests/unit/test_venv_sync.py` to expect `uv sync` commands
- [x] Update integration tests in `tests/integration/test_library_venv_sync.py` to verify sync behavior
- [x] Add migration guide entry (§5.7) documenting the switch from pip to sync

**Deliverables**:
- [x] Modified `VirtualEnvironmentManager._install_dependencies()` method
- [x] Updated unit tests expecting `uv sync` instead of `uv pip install`
- [x] Updated integration tests verifying lockfile generation and sync behavior
- [x] Migration guide entry explaining the change and its impact

**Tests** (`tests/unit/test_venv_sync.py`, `tests/integration/test_library_venv_sync.py`):
- [x] Unit test: verify `uv sync` called with correct extras
- [x] Unit test: verify `--extra` flags built correctly from extras list
- [x] Unit test: verify editable install uses `uv sync`, non-editable uses wheel build
- [x] Integration test: verify `uv.lock` generated in library directory
- [x] Integration test: verify dependencies installed correctly via sync
- [x] Integration test: verify extras (dev, tests, oarepo14) activated correctly

**Migration impact**:
- `uv sync` replaces `uv pip install`, generating a `uv.lock` file in library directories
- Lockfiles provide reproducible builds during development but are gitignored for libraries
- Behavior change: `uv sync` may install/update dependencies differently than pip (more deterministic)
- Users must have `uv` 0.1.0+ (already a requirement)
- See migration guide (§5.7) for details

**Rationale**:
- Unifies library and repository installation paths using the same `VirtualEnvironmentManager` API
- Uses uv's native sync mechanism instead of the pip compatibility layer
- Prepares for Step 4.1 (repository install) to reuse the same installation logic
- Lockfile provides reproducible builds during development, reducing "works on my machine" issues
- Aligns with modern Python tooling practices (Poetry, PDM also use lock files)
- Simplifies the codebase by having one installation code path instead of two

---

## Phase 4: Repository Commands

### Step 4.1: Repository `install` Command
**Goal**: Implement repository installation.

- [x] Implement `repository_install()` function
- [x] Ensure venv exists
- [x] Sync dependencies with `uv sync`
- [x] Copy translations overlay
- [x] Resolve instance path (`INVENIO_INSTANCE_PATH` or `<venv>/var/instance` — see Step 4.1.2)
- [x] Create symlinks for invenio.cfg
- [x] Run `invenio-cli install`
- [x] Configure local service ports in `.invenio.private`
- [x] Compile backend translations

**Deliverables**:
- Working install command

**Tests** (`tests/integration/test_repository_install.py`):
- [x] Test venv synced
- [x] Test translations copied
- [x] Test instance path created
- [x] Test `.invenio.private` configured
- [x] Integration test: full install in temp repo

Runs against a real scaffolded repository rather than a mocked one: see
`tests/conftest.py`'s `testrepo_project` (creates it once via the real
`repository_installer.sh` — https://nrp-cz.github.io/docs/installation/create_instance
— and reuses the cached scaffold on subsequent runs) and `clean_testrepo`/
`reset_testrepo_state`. A full install (`uv sync` of invenio-app-rdm and
friends, `invenio-cli install`) takes 1-2 minutes even with a warm cache,
so `installed_repo` (module-scoped, in the test file) runs it once and
every test asserts on a distinct side effect of that single run.

---

### Step 4.1.1: CESNET-patched invenio-cli dependency
**Goal**: Require the CESNET-patched `invenio-cli` build (docker-environment,
extension hooks, cert paths, etc. — see
[oarepo/invenio-cli@oarepo-feature-docker-environment](https://github.com/oarepo/invenio-cli))
that `repository install`/`run`/`services` rely on, and fail fast if the
plain upstream build ends up installed instead. See
[ADR-006](./00-main-architecture.md#adr-006-cesnet-patched-invenio-cli-dependency).

- [x] Add `CESNET_PYPI_INDEX_URL` constant (`configuration/constants.py`), reused by `OAREPO_ENV_DEFAULTS`
- [x] Scope `invenio-cli` to the CESNET registry via `[[tool.uv.index]]` / `[tool.uv.sources]` in `pyproject.toml`
- [x] Bump `invenio-cli` constraint to `>=1.12.0,<2.0.0` (base version of the patched build)
- [x] Implement `core/dependency_check.py:check_invenio_cli_version()` — verifies the installed version carries a `+oarepo...` local version segment
- [x] Call `check_invenio_cli_version()` at the top of `cli/main.py:cli_main()`, before dispatching to Typer
- [x] Raise `VersionMismatchError` with a message pointing at the CESNET registry on mismatch/missing package

**Deliverables**:
- `invenio-cli` always resolves from the CESNET registry via `uv lock`/`uv sync`
- Startup check catches environments where that didn't happen (manual install, stale lock, etc.)

**Tests** (`tests/core/test_dependency_check.py`):
- [x] Accepts a version with the `+oarepo` local segment
- [x] Rejects a plain upstream version
- [x] Rejects a local version with an unrelated prefix
- [x] Rejects when the package isn't installed
- [x] Rejects an unparseable version string
- [x] Error message references the CESNET registry URL

---

### Step 4.1.2: Fast instance path resolution
**Goal**: Replace the `invenio shell`-based instance path lookup (slow: full
Flask app boot on every `install`) with a direct computation of Invenio's own
default resolution rule. See
[ADR-007](./00-main-architecture.md#adr-007-fast-instance-path-resolution-no-invenio-shell).

- [x] Rewrite `services/repository.py:get_instance_path()` to return `INVENIO_INSTANCE_PATH` if set, else `context.venv_path / "var" / "instance"`
- [x] Remove `services/invenio_cli.py:run_invenio_shell()` (its only caller)
- [x] Update `cli/repository.py:install()`'s docstring step list accordingly

**Tests** (`tests/unit/test_repository_service.py`):
- [x] Defaults to `<venv>/var/instance` when `INVENIO_INSTANCE_PATH` is unset
- [x] Honors `INVENIO_INSTANCE_PATH` when set

---

### Step 4.1.3: Run the already-installed invenio-cli directly, not via uvx

**Goal**: `services/invenio_cli.py`'s `run_invenio_cli()` (used by every
`repository install`/`upgrade`/`services *`/`run`/`ModelManager` reinstall
call) had, since its introduction alongside Step 4.1, been shelling out to
`uvx --python="$PYTHON" --with git+.../oarepo-cli@rdm-14 --from
git+.../invenio-cli@oarepo-feature-docker-environment invenio-cli ...` on
every single call -- a literal, uncommented-on port of
`repository_runner.sh`'s `run_invenio_cli`, itself marked there as
`# temporary implementation until release`. That release (Step 4.1.1's
CESNET-patched `invenio-cli` on the CESNET PyPI registry, verified at
startup by `check_invenio_cli_version()`) has since happened, but the uvx
call was never updated to match -- so oarepo-cli was verifying one
invenio-cli build at startup while actually running a completely different
one (a different git branch, plus an unrelated old `oarepo-cli@rdm-14`
`--with` dependency) on every command, and paying a uvx resolve/network
cost each time.

Found and fixed via user discussion after Step 4.8: since invenio-cli purely
orchestrates the target project via subprocesses/docker (confirmed with the
user) rather than needing to run under the target project's own
interpreter, there's no reason not to call the already-installed,
already-verified binary directly.

- [x] Add `services/invenio_cli.py:_invenio_cli_path()` -- resolves the
  `invenio-cli` binary installed next to the running interpreter (mirrors
  `services/lint.py:_tool_path()`'s identical rationale for ruff/ty),
  falling back to the bare name (PATH-resolved) if not found
- [x] Simplify `_build_command()` to `[_invenio_cli_path(), *args]`, dropping
  the `uvx`/`--python=`/`--with`/`--from` construction entirely
- [x] Update `tests/unit/test_invenio_cli.py` accordingly, plus new tests
  for `_invenio_cli_path()`'s two branches

**Tests** (`tests/unit/test_invenio_cli.py`):
- [x] `run_invenio_cli` runs the resolved binary path directly, with args appended
- [x] `_invenio_cli_path()` prefers a binary next to the interpreter
- [x] `_invenio_cli_path()` falls back to the bare name otherwise

---

### Step 4.2: Repository `upgrade` Command
**Goal**: Implement repository upgrade.

- [x] Implement `repository_upgrade()` function
- [x] Remove venv and uv.lock
- [x] Clean uv cache
- [x] Reinstall repository

`install`'s steps were extracted into `_install_repository()` (no top-level
success/failure messaging) so `install` and `upgrade` share the exact same
reinstall logic, mirroring how `repository_runner.sh`'s
`upgrade_repository()` calls `install_repository()` directly. Uses
`VirtualEnvironmentManager.cleanup()` for venv+lock removal (same method
`library upgrade` uses) and `uv cache clean --force` (note: `--force`,
unlike `library upgrade`'s plain `uv cache clean` — matches
`repository_runner.sh` exactly, which is stricter here than
`library_runner.sh`).

**Deliverables**:
- Working upgrade command

**Tests** (`tests/integration/test_repository_upgrade.py`):
- [x] Test venv and lock removed
- [x] Test cache cleaned
- [x] Test reinstall succeeds

The venv/lock-removed and cache-cleaned checks mock out `_install_repository`
and the `uv cache clean` subprocess call so they run in milliseconds rather
than repeating a multi-minute reinstall; a separate real, slow
`test_upgrade_reinstalls_successfully` runs a full install-then-upgrade
cycle end-to-end (including a real `uv cache clean --force` — verified it
actually clears the machine's uv cache, ~1.1GiB in local testing, and that
the subsequent reinstall re-populates it correctly).

---

### Step 4.3: Repository `services` Subcommands
**Goal**: Implement services subcommands (setup/start/stop/destroy).

- [x] Implement `repository_services()` with subcommands
- [x] Delegate to `run_invenio_cli services ...`
- [x] Pass through all arguments

Implemented as a `services_app` sub-Typer group mounted on `repository_app`
(same pattern as `library`'s own `services_app`), with each of
`setup`/`start`/`stop`/`destroy` a separate command delegating through
`_run_services_subcommand()` to `invenio_cli.run_invenio_cli(context,
["services", subcommand, *extra_args], check=False)`. `check=False` plus
`raise typer.Exit(code=result.return_code)` propagates invenio-cli's exact
exit code, rather than collapsing failures to `1` the way `install`/
`upgrade` do — matching `repository_runner.sh`'s `services()`, which is a
pure passthrough under `set -e` (whatever invenio-cli exits with is what
the script exits with). `context_settings` (`allow_extra_args`,
`ignore_unknown_options`, `help_option_names: []`) mirror the existing
`library invenio` passthrough command, so extra flags (e.g. invenio-cli's
own `-N`/`--no-demo-data`) and `--help` reach invenio-cli itself instead of
being intercepted by Typer/Click.

**Deliverables**:
- Services subcommands

**Tests** (`tests/integration/test_repository_services.py`):
- [x] Test each subcommand delegates correctly
- [x] Test arguments passed through

All 4 subcommands are parametrized over the same test bodies: delegates to
`invenio-cli services <subcommand>`, forwards extra args verbatim,
propagates a non-0/1 exit code exactly, and forwards `--help`. Mocked
(`discover_context`/`run_invenio_cli`) rather than run for real — a pure
passthrough wrapper has no real side effects of its own to exercise beyond
command construction (unlike `install`/`upgrade`, which do get a real
end-to-end test). Manually verified against the real `tests/testrepo`
fixture too: `repository services setup --help` prints invenio-cli's own
real help text (`-f`/`--force`, `-N`/`--no-demo-data`, `--stop-services`,
`-s`/`--services`).

---

### Step 4.4: Model Manager
**Goal**: Implement record model management via copier.

- [x] Implement `services/models.py` with `ModelManager` class
- [x] Method: `create_model(name, config_file=None)` → None
- [x] Method: `update_model(name, answers_file=None)` → None
- [x] Use `copier.run_copy`/`copier.run_update` (see deviation note below)
- [x] Support GitHub templates and local paths
- [x] Reinstall repository after model changes

**Deviation from the original plan**: rather than shelling out to
`uvx --with copier-template-extensions --with pycountry --with tomli
--with tomli-w copier copy/update ...` for a fresh ephemeral environment on
every call (`repository_runner.sh`'s approach, and this step's original
"Use `uvx copier copy` and `copier update`" bullet), `copier`,
`copier-template-extensions` (note: singular -- `copier-templates-extensions`
is the deprecated old name, even though `repository_runner.sh`'s model
commands use the old plural spelling), `pycountry`, `tomli`, and `tomli-w`
are now regular oarepo-cli dependencies, and `ModelManager` calls
`copier.run_copy`/`copier.run_update` directly as a library, in-process.
`repository.install_repository()` was extracted from `cli/repository.py`
(previously `_install_repository`, private to that module) into
`services/repository.py` as a public function so both `install`/`upgrade`
and `ModelManager.create_model()`'s post-creation reinstall share it,
mirroring how `repository_runner.sh`'s `install_repository()` is called
from `install`, `upgrade_repository`, and `create_model` alike.

One further deliberate behavioral difference, discovered while writing
real tests against real copier (see below): a given `config_file`/
`answers_file` is loaded and passed to copier as `data` (like copier's own
`--data-file`), not merely as `answers_file` (like bash's
`--answers-file`). `answers_file` alone only pre-fills copier's
interactive prompts with prior answers -- it still requires a live
terminal to confirm each one, which defeats the entire point of passing a
config file for scripted/non-interactive use. See `services/models.py`'s
`ModelManager` docstring.

**Deliverables**:
- Model management service

**Tests** (`tests/integration/test_model_manager.py`):
- [x] Test model creation against real `copier` (slow)
- [x] Test model update with answers file
- [x] Test template URL handling

Since copier now runs in-process rather than as a subprocess, AGENTS.md's
guidance to use `pytest-subprocess`'s `fake_process` for "services that
shell out to slow external tools (uv, docker-services-cli, copier)" no
longer applies to it specifically -- there's no subprocess to intercept.
Instead, tests run copier for real against small local template fixtures
(fast: no network, no ephemeral `uvx` bootstrap), which is both simpler
and more faithful than mocking copier's Python API. Notable things learned
along the way, now documented in the test file: copier never writes an
answers file unless the template itself contains a file that renders the
special `_copier_answers` context variable (this is *not* automatic --
`nrp-app-copier`/`nrp-model-copier` do this via
`{{_copier_conf.answers_file}}.copier`); `copier update` only works on
git-tracked, clean destinations, and requires `overwrite=True` for those
(safe, since the user can review via `git diff`); an `answers_file` path
must resolve inside `dst_path`, never a parent/sibling.

---

### Step 4.5: Repository `model` Command
**Goal**: Implement `oarepo-cli repository model` command.

- [x] Implement `repository_model()` with `create` and `update` subcommands
- [x] Options: template URL, version, config file
- [x] Delegate to `ModelManager`

**Deviation from the original plan**: template URL/version are not exposed
as CLI flags on `model create`/`model update` -- per `03-migration-guide.md`
(`oarepo-cli repository model create <name> [config_file]`, `... update
<name> [answers_file]`), they're only ever configured via
`[tool.oarepo-cli] model.template_url`/`.template_version` in
`pyproject.toml` or the `MODEL_TEMPLATE`/`MODEL_TEMPLATE_VERSION` env vars
(already resolved into `context.config.model` by `core/config.py`, see
Step 4.4), matching `repository_runner.sh`'s `create_model`/`update_model`,
which never took `--template`/`--version` flags either. Each subcommand
takes only a `name` positional and an optional `config_file`/
`answers_file` positional, plus `--quiet` (consistent with `install`/
`upgrade`).

**Deliverables**:
- Model command

**Tests** (`tests/integration/test_repository_model.py`):
- [x] Test model create subcommand
- [x] Test model update subcommand
- [x] Test help text

---

### Step 4.5.1: Fix pre-existing test failures uncovered by the Step 4.5 full-suite run
**Goal**: Fix two `make test` failures, unrelated to Step 4.5, discovered while
running the full suite (not just the changed files) after implementing it.

- [x] `tests/integration/test_repository_upgrade.py::test_upgrade_removes_venv_and_lock`
  and `::test_upgrade_cleans_uv_cache_with_force`: both `monkeypatch.setattr(
  "oarepo_cli.cli.repository._install_repository", ...)`, but that name hasn't
  existed since Step 4.4 (#124), which extracted it out of `cli/repository.py`
  into the public `oarepo_cli.services.repository.install_repository`. Fixed
  by retargeting both monkeypatches to
  `"oarepo_cli.cli.repository.repository.install_repository"`, matching how
  `cli/repository.py` itself calls it (via its `from oarepo_cli.services
  import ... repository` import) and how `test_repository_services.py`
  patches through the same kind of imported-submodule reference.
- [x] `tests/integration/test_library_venv_sync.py::test_uv_lock_added_to_gitignore`:
  not test-order pollution as originally suspected -- it fails even in
  isolation, on a clean checkout. Root cause: the real, checked-in
  `tests/testlib/.gitignore` fixture file already lists `uv.lock` (added
  deliberately in a later step, since testlib is a member of this repo's
  own root uv workspace and has its own real lock), but the test's premise
  (`assert "uv.lock" not in content_before`) assumed a fixture `.gitignore`
  that never mentions `uv.lock` yet. Fixed with a new
  `testlib_without_gitignored_uv_lock` fixture (wraps `clean_testlib`):
  strips any existing `uv.lock` line from the real `.gitignore` before the
  test runs (so the dynamic-add behavior can be verified for real, not
  mocked) and restores the original content afterward, leaving the
  committed fixture file untouched on disk once the test finishes.

**Deliverables**:
- Both failures fixed, `make test` green end to end (not just per-file)

---

### Step 4.6: Local Package Manager
**Goal**: Manage local packages in `tool.uv.sources`.

- [x] Implement `services/local_packages.py` with `LocalPackageManager` class
- [x] Method: `add_package(path)` → None
- [x] Method: `remove_package(name)` → None
- [x] Parse and modify pyproject.toml
- [x] Trigger repository upgrade after changes

**Deviation from the original plan**: rather than shelling out to `uv add
<path> --editable` (`repository_runner.sh`'s approach), `add_package`/
`remove_package` edit `pyproject.toml` directly with `tomlkit` (a new
dependency), which round-trips comments/key order/formatting elsewhere in
the file -- unlike `tomllib` (read-only, used by `PyProjectReader`) or
`tomli-w` (write-only, full-dict dump, used by copier's own templates).
Both methods unconditionally call a newly-extracted
`services.repository.upgrade_repository()` afterwards (moved out of
`cli/repository.py`'s `upgrade` command, which now just calls it too) --
mirroring `local_sources_cmd`'s unconditional call to `upgrade_repository`
after `uv add`, in contrast to `ModelManager.create_model()`'s conditional
reinstall (only if a venv already exists). `remove_package()` has no bash
equivalent: `repository_runner.sh`'s `local remove` was never implemented
(it just told the user to edit `pyproject.toml` by hand and run
`./run.sh upgrade`), but `00-main-architecture.md`'s compatibility matrix
lists `local remove <name>` as a command the rewrite must actually
support, so this fills that gap.

**Deliverables**:
- Local package management

**Tests** (`tests/integration/test_local_packages.py`):
- [x] Test package added to sources
- [x] Test package removed from sources
- [x] Test pyproject.toml updated correctly

---

### Step 4.6.1: Skip uv Cache Clean on Local Package Add/Remove
**Goal**: Correction to Step 4.6 -- adding/removing a local package must not
clean the uv cache.

- [x] Add a `clean_cache: bool = True` keyword to
  `services.repository.upgrade_repository()`, guarding the `uv cache clean
  --force` step
- [x] `LocalPackageManager.add_package()`/`remove_package()`/
  `remove_all_packages()` call `upgrade_repository(..., clean_cache=False)`
- [x] `repository upgrade` (the CLI command) keeps the default
  (`clean_cache=True`), unchanged

**Rationale**: unlike `repository upgrade` (which exists precisely to force
a fresh resolve of every dependency), adding or removing a local, editable
package doesn't change any other package's pinned version -- so purging the
entire uv cache and forcing a full re-download of everything else on the
next install buys nothing and is slow. This is a deliberate deviation from
`repository_runner.sh`'s `local_sources_cmd`, which called the same
unconditional, cache-clearing `upgrade_repository()` bash function as
`./run.sh upgrade` (`local remove` has no bash equivalent to deviate from --
see Step 4.6's own deviation note).

**Deliverables**:
- `local add`/`local remove`/`local remove --all` no longer clean the uv
  cache; `repository upgrade` is unaffected

**Tests**:
- `tests/unit/test_repository_service.py`: `upgrade_repository(...,
  clean_cache=False)` does not run `uv cache clean`; default
  (`clean_cache=True`) behavior unchanged
- `tests/integration/test_local_packages.py`: `add_package`/`remove_package`/
  `remove_all_packages` call `upgrade_repository` with `clean_cache=False`

---

### Step 4.7: Repository `local` Command
**Goal**: Implement `oarepo-cli repository local` command.

- [x] Implement `repository_local()` with `add` and `remove` subcommands
- [x] Delegate to `LocalPackageManager`

**Deviation from the original plan**: `00-main-architecture.md`'s
compatibility matrix (§1) documents `local remove <name>|--all`, not just
`<name>` -- the implementation-steps checklist above predates that detail.
Added `LocalPackageManager.list_local_packages()` (filters
`[tool.uv.sources]` to path-based/editable entries only, so an unrelated
entry like the CESNET-patched `invenio-cli`'s `{ index = "cesnet" }`
override is never touched) and `remove_all_packages()` (removes every local
package but triggers exactly one `upgrade_repository` call at the end, via
a new `remove_package(..., upgrade=False)` keyword rather than one full
upgrade per package) to back `local remove --all`. `local remove` requires
exactly one of a `<name>` positional or `--all` (errors, exit 1, on
neither or both).

**Deliverables**:
- Local command

**Tests** (`tests/integration/test_repository_local.py`):
- [x] Test add subcommand
- [x] Test remove subcommand

---

### Step 4.8: Server Runner
**Goal**: Implement repository server execution with signal handling.

- [x] Implement `services/server.py` with `ServerRunner` class
- [x] Method: `run(no_services=False, no_celery=False)` → None
- [x] Start Docker services if not skipped
- [x] Start Celery worker in background if not skipped
- [x] Run `invenio run` or `invenio-cli run`
- [x] Handle SIGINT/SIGTERM for graceful shutdown
- [x] Cleanup services on exit

**Deviations from the original plan**:
- "Start Celery worker in background": `repository_runner.sh`'s
  `run_server()` never spawns a Celery worker itself -- when Celery isn't
  skipped, it delegates entirely to `invenio-cli run`, which manages Celery
  internally as its own documented behavior. `ServerRunner` mirrors this
  exactly rather than spawning a separate worker process, matching bash
  rather than 01-detailed-design.md's state diagram (which sketches Celery
  as a distinct, separately-managed background process -- that diagram
  predates confirming invenio-cli's actual behavior and uses APIs, e.g.
  `SignalHandler`, `ProjectContext.from_cwd()`, that don't exist in the
  real codebase).
- "Cleanup services on exit": resolved via explicit product decision --
  Docker services are deliberately **not** auto-stopped when the server
  exits/is interrupted. `run_server()` never stops them either (Ctrl+C just
  kills the foreground process; services stay up for the next command,
  like the `library` domain's pattern), and `03-migration-guide.md`
  explicitly promises "Identical behavior" for `run`. Users stop services
  explicitly via `repository services stop`.
- "Handle SIGINT/SIGTERM for graceful shutdown": **superseded** by a second
  revision, after further discussion. The first version spawned invenio-cli
  as a supervised child process (via new `process.popen()`/
  `invenio_cli.popen_invenio_cli()` helpers) and installed SIGINT/SIGTERM
  handlers forwarding the signal to it, escalating to SIGKILL after a grace
  period. Inspecting the actual installed `invenio-cli` package
  (`invenio_cli/commands/local.py:LocalCommands`) showed this was
  unnecessary *and* strictly worse: invenio-cli's own `run` command already
  spawns and gracefully signal-handles its own child processes (web server,
  Celery worker, jobs scheduler, via `_handle_sigint`), but only correctly
  if it believes itself to be the foreground process -- and its children
  only ever listen for SIGINT, so a SIGTERM forwarded by our own wrapper
  would never have cleanly cascaded to them anyway. Replaced with
  `os.execve`/`os.execvpe` process replacement (mirrors
  `cli/library.py`'s `library_shell`/`library_invenio`, and is actually how
  bash's own `run_server()` behaves too, since `invenio-cli run`/`invenio
  run` is simply its last foreground command): `ServerRunner.run()` now
  never returns on success, `process.popen()` was removed entirely (no
  other caller), and `invenio_cli.popen_invenio_cli()` became
  `invenio_cli.exec_invenio_cli()`.

**Deliverables**:
- Server runner

**Tests** (`tests/integration/test_server_runner.py`):
- [x] Test server starts with services
- [x] Test server starts without celery
- [x] Test signal handling stops everything -- superseded: covers that
  invenio-cli/invenio are the ones handling signals now (nothing left in
  `ServerRunner` to test for this), via two real, isolated-subprocess exec
  tests (`test_run_no_celery_real_exec_replaces_process`,
  `test_run_with_celery_real_exec_replaces_process`)
- [x] Test cleanup on interrupt -- superseded, same rationale

---

### Step 4.9: Repository `run` Command
**Goal**: Implement `oarepo-cli repository run` command.

- [x] Implement `repository_run()` function
- [x] Options: `--no-services`, `--no-celery`
- [x] Delegate to `ServerRunner`

**Deviation from the original plan**: also forwards unrecognized
args/options (e.g. `-p 5001`) to the underlying `invenio-cli run`/`invenio
run` command as `extra_args`, mirroring `repository_runner.sh`'s
`run_server()`'s `extra_options` -- not called out in the checklist above,
but dropping it would be a real regression from bash's actual behavior.
Unlike the `services` subcommands' passthrough context settings, `--help`
is *not* forwarded/swallowed here (`help_option_names` left at its
default): `run` has its own real options, so `--help` shows oarepo-cli's
own help, not invenio-cli's.

**Deliverables**:
- Running command

**Tests** (`tests/integration/test_repository_run.py`):
- [x] Test run with services
- [x] Test run without celery
- [x] Test signal handling -- superseded, same rationale as Step 4.8: no
  signal-handling code left in this layer to test (invenio-cli/invenio
  handle it themselves post-exec). Covered instead by
  `test_run_real_exec_replaces_process`, a real, isolated-subprocess test
  driving the full CLI -> `discover_context` -> `ServerRunner` -> exec
  stack against a fake `invenio-cli` binary.

---

### Step 4.10: Repository `cli`, `translations`, `index`, `reset`, `info` Commands
**Goal**: Implement remaining repository commands.

- [x] Implement `repository_cli()` → passthrough to `invenio-cli`
- [x] Implement `repository_translations()` → extract/compile
- [x] Implement `repository_index_rebuild()` → destroy/init/rebuild indices
- [x] Implement `repository_reset()` → full reset with confirmation prompt
- [x] Implement `repository_info()` → show Python version and models

**Deviations from the original plan**:
- `repository cli` reuses Step 4.8's `invenio_cli.exec_invenio_cli()`
  (`os.execve`/`os.execvpe` process replacement) rather than a blocking
  call: it's a one-shot passthrough with nothing to do afterward, exactly
  like `cli/library.py`'s `library_invenio`, so the exit code is preserved
  exactly and `--help` reaches invenio-cli's own help (via the same
  `_SERVICES_CONTEXT_SETTINGS` the `services` subcommands already use).
- `repository translations` mirrors `repository_runner.sh`'s
  `translations()`'s exact dispatch logic directly (first positional arg
  ``== "compile"`` → `invenio-cli translations compile`; anything else,
  including no args, → oarepo-tools `make-translations` with all args
  forwarded) rather than a Typer subcommand group, since bash's dispatch
  isn't a clean subcommand split (any arbitrary first arg is valid
  `make-translations` input, not just a fixed set of subcommands).
- `repository index` *is* a Typer subcommand group (`index rebuild`), since
  bash only ever accepts exactly `rebuild` there (unlike `translations`) --
  matches the `model`/`local`/`services` groups' existing pattern.
- Added `services/repository.py`: `get_invenio_binary()` (also now reused
  by `services/server.py`'s `--no-celery` exec path, replacing its former
  inline `get_platform_detector()` call -- same binary resolution, one
  fewer duplicate), `rebuild_index()`, `reset_repository()` (confirmation
  prompt is the CLI layer's responsibility -- mirrors how `local remove`'s
  validation stays in the CLI layer while the work stays in the service),
  `get_python_version()`, and `list_repository_models()`/`ModelInfo` for
  `info`'s model discovery.
- Found and fixed a pre-existing bug while wiring `reset`'s demo password:
  `core/config.py`'s `SecurityConfig.demo_user_password` read from
  `OAREPO_SECURITY_DEMO_PASSWORD`, but both `00-main-architecture.md`'s env
  var table and `03-migration-guide.md`'s compatibility table (and
  `repository_runner.sh` itself, via `${DEMO_USER_PASSWORD:-123456}`)
  document plain `DEMO_USER_PASSWORD` -- i.e. `reset` would have silently
  ignored the documented, bash-compatible env var. Fixed both `_get_str()`
  call sites (`from_env()`) and the "using default password" warning
  message to use `DEMO_USER_PASSWORD`; no existing test referenced the old
  name.
- `repository_runner.sh` also has an undocumented `run.sh invenio <args>`
  bare-invenio passthrough (distinct from `cli`, which maps to
  `run_invenio_cli`) -- but unlike `library invenio`, it appears nowhere in
  `00-main-architecture.md`'s or `03-migration-guide.md`'s repository
  command tables, so (matching how `self-update` was deliberately dropped)
  it's treated as out of scope for the rewrite, not implemented.
- Found and fixed a second, unrelated pre-existing bug while manually
  smoke-testing `repository cli`/`info` against a throwaway project: the
  `ConfigurationError` raised when no OARepo version can be resolved still
  said "Add to pyproject.toml `[tool.oarepo-cli]`" -- stale guidance from
  before Step 3.13 replaced that key with dependency-scanning. Worse,
  `core/config.py`'s `CliConfig.from_pyproject()` was still actually
  *reading* `[tool.oarepo-cli].oarepo.version` into `config.oarepo.version`
  (checked before dependency-scanning in `ContextBuilder.build()`), directly
  contradicting `PyProjectData.oarepo_versions`'s own warning that the key
  "is deprecated and ignored" -- it was deprecated but not actually
  ignored. Fixed by dropping that pyproject-reading block entirely (`oarepo
  = OARepoConfig()`, unconditionally); `OAREPO_VERSION` (`from_env()`) is
  now the only remaining manual override, matching
  `03-migration-guide.md`'s documented behavior. Updated the error message
  to point at `[project].dependencies` instead. Updated/fixed fixtures that
  relied on the now-inert pyproject key across `tests/unit/test_context.py`
  (15 occurrences), `tests/unit/test_config.py` (assertion flipped to
  `is None`), `tests/integration/test_repository_run.py`,
  `tests/integration/conftest.py`'s `lint_project` template, and the real
  `tests/testlib/pyproject.toml` fixture (dependencies already declared
  `oarepo[rdm,tests]>=14.2.1b10.dev7,<15.0.0`, so the redundant/dead
  `[tool.oarepo-cli]` block was simply removed there).

**Deliverables**:
- Complete repository command set

**Tests** (`tests/integration/test_repository_misc.py`, plus new
`services/repository.py` coverage in `tests/unit/test_repository_service.py`):
- [x] Test each command executes
- [x] Test reset confirmation prompt
- [x] Test info output format
- [x] Characterization tests -- via `tests/unit/test_repository_service.py`'s
  `rebuild_index`/`reset_repository` tests, which assert the exact
  subcommand sequence against a mocked `process.run`/`invenio_cli`, mirroring
  bash's own command-by-command sequence

---

### Step 4.11: Fix Duplicate Summary Print in `library clean`
**Goal**: Fix a copy-paste bug found during the post-Phase-4 library/repository
parity audit ([after_repository_cleanup.md](./after_repository_cleanup.md) §2.1).

- [x] Remove the duplicated "Display summary" if/else block in
  `cli/library.py`'s `library_clean()` -- the entire block (deciding between
  `✨ ✓ Cleanup completed! Removed: ...` and `✨ ✓ Environment is already
  clean!`) appears twice verbatim, so every `library clean` run prints its
  summary message twice
- [x] Add/adjust a test asserting the summary is printed exactly once

**Deliverables**:
- `library clean` prints its summary exactly once

**Tests**:
- Existing `library clean` tests updated (or a new one added) to assert the
  summary message appears exactly once in output, for both the
  "something was removed" and "already clean" cases

---

### Step 4.12: Unify Exception Handling Across `library`/`repository` CLI Commands
**Goal**: Resolve the exception-handling inconsistency found during the audit
([after_repository_cleanup.md](./after_repository_cleanup.md) §2.2): every
`repository.py` command narrowly catches `except (OARepoError,
ProcessExecutionError)`, while every `library.py` command broadly catches
`except Exception`. **Decision: the narrower `repository.py` pattern is
correct** -- a broad `except Exception` silently turns real bugs (e.g. an
`AttributeError`) into a clean, misleading "exit 1" instead of surfacing a
traceback.

- [x] Change all top-level command `except Exception` blocks in
  `cli/library.py` (17 sites) to `except (OARepoError, ProcessExecutionError)`,
  matching `cli/repository.py`'s pattern
- [x] Verify no `library.py` command actually relies on catching a
  non-`OARepoError` exception type (e.g. a raw `OSError`/`subprocess` error
  that isn't already wrapped) -- wrap it into an appropriate `OARepoError`
  subclass at the source (in `services/`) instead of widening the CLI-layer
  catch back out
- [x] While touching these sites, simplify `repository.py`'s
  `except (OARepoError, ProcessExecutionError)` to plain `except OARepoError`
  -- `ProcessExecutionError` already subclasses `OARepoError`
  (`core/errors.py`), so the tuple is redundant
- [x] Re-run the full test suite -- some tests may currently rely on the
  broad catch (e.g. asserting a specific exit code for an exception type
  that isn't an `OARepoError`); fix the underlying exception type rather
  than the test if so

**Deviations from the original plan**:
- Of `library.py`'s 17 `except Exception` sites, only 12 are the "wrap a
  whole command, print an error, exit 1" pattern this step targets --
  `library_clean()`'s 3 step-by-step cleanup handlers and `library_upgrade()`'s
  2 (stop services, clean cache) are a different, correct pattern:
  best-effort, log-a-warning-and-continue steps in an idempotent multi-step
  operation (e.g. `.unlink()` on `.env-services` can raise a raw `OSError`,
  which must not abort the rest of the cleanup). Left broad on purpose, now
  with a comment explaining why so a future audit doesn't re-flag them.
- Landed as plain `except OARepoError` in both files directly (not
  `except (OARepoError, ProcessExecutionError)` in `library.py` first, then
  simplified) -- `ProcessExecutionError` already subclasses `OARepoError`,
  so there was no intermediate state worth landing.
- `library_test()`'s handler had a manual `if not isinstance(e, typer.Exit):
  ... else: raise` guard, needed because `typer.Exit` subclasses
  `RuntimeError`/`Exception`, so the old broad catch used to intercept its
  own `raise typer.Exit(code=result.return_code)` on the success path. Under
  `except OARepoError`, `typer.Exit` is never caught here at all, so the
  guard was removed as dead code rather than kept.

**Deliverables**:
- Every CLI command in both modules uses the same, narrow exception-handling
  policy

**Tests**:
- Existing command-level tests continue to pass; add a regression test per
  module confirming an unexpected (non-`OARepoError`) exception now
  propagates instead of being swallowed into a generic "exit 1"

---

### Step 4.13: Refactor `library oarepo-versions` to Use `discover_context()`
**Goal**: Fix the inconsistency found during the audit
([after_repository_cleanup.md](./after_repository_cleanup.md) §2.3):
`library_oarepo_versions()` is the only command (of 31 across both modules)
that doesn't use `discover_context()` -- it hand-rolls its own
parent-directory walk for `pyproject.toml` and wires up
`PyProjectReader`/`VersionResolver` directly, with function-local imports
(`json`, `Path`, `ConfigurationError`, `PyProjectReader`, `VersionResolver`)
that exist only because they were never hoisted (not to break a circular
import, the only sanctioned reason per AGENTS.md).

- [x] Before refactoring, confirm `discover_context()`'s failure mode still
  satisfies `oarepo-versions`' contract (it may need to work in places a
  fully-resolved `ProjectContext` can't be built -- e.g. no venv yet --
  since it only ever needed `pyproject.toml`); adjust `discover_context()`
  or fall back to a narrower helper if not
- [x] Rewrite `library_oarepo_versions()` to use `discover_context()` (or
  the confirmed narrower alternative) instead of its own directory walk
- [x] Move `json`, `Path`, `ConfigurationError`, `PyProjectReader`,
  `VersionResolver` imports to module level
- [x] Verify the command's output/exit codes are unchanged

**Deviations from the original plan**:
- Confirmed `discover_context()` does *not* fit: `ContextBuilder.validate()`
  requires a resolvable OARepo version and an existing Python binary
  (raising `ConfigurationError` for either), but `oarepo-versions` must keep
  working for a project with no `oarepo` dependency at all --
  `test_oarepo_versions_no_oarepo_extra` exercises exactly this and would
  have broken. Used the "narrower helper" fallback the step anticipated
  instead: extracted the upward `pyproject.toml` search into a new
  `core.context.find_pyproject_toml()`, also adopted by
  `ContextBuilder.from_cwd()` (dropping its own duplicate copy of the same
  loop), so `library_oarepo_versions()` no longer hand-rolls it but still
  doesn't need a full `ProjectContext`.
- Widened the resolver's error handling from `except ConfigurationError` to
  `except OARepoError`, matching Step 4.12's convention -- this also now
  catches `VersionMismatchError`, which `resolve_from_pyproject()` can
  raise but the old code never caught (would have crashed with a raw
  traceback instead of a clean exit 1).
- `Path` itself didn't need hoisting: `pathlib.Path` isn't imported at all
  in `cli/library.py` (unlike `cli/repository.py`, which does need it for a
  type annotation) -- the plan's checklist item is satisfied by simply no
  longer needing it in this function.

**Deliverables**:
- `library oarepo-versions` uses the same context-discovery path as every
  other command; no function-local imports remain in it

**Tests**:
- Existing `library oarepo-versions` tests continue to pass unchanged
  (output format/exit codes are a compatibility contract, not something
  this refactor should touch)

---

### Step 4.14: Move `library_shell`'s Function-Local `traceback` Import
**Goal**: Fix the second AGENTS.md-import-rule violation found during the
audit ([after_repository_cleanup.md](./after_repository_cleanup.md) §2.4):
`library_shell()` has `import traceback  # noqa: TID251` inside its
`except Exception` branch, not to break a circular import.

- [x] Move `import traceback` to module level in `cli/library.py` and drop
  the `# noqa: TID251` suppression
- [x] Re-run `make lint` to confirm no new, unsuppressed violation appears
  (if one does, address the underlying cause rather than re-adding the
  suppression)

**Deviation from the original plan**: `TID` (flake8-tidy-imports, the rule
`TID251` belongs to) isn't in this project's `[tool.ruff.lint].select` list
at all -- the suppression was already a no-op before this step removed it.

**Deliverables**:
- No function-local, non-circular-import imports remain in `cli/library.py`

**Tests**:
- No behavior change expected; existing `library shell` tests continue to
  pass

---

### Step 4.15: Multi-Module Source-Directory Detection (`[tool.uv.build-backend]`)
**Goal**: Generalize `ProjectContext.code_directories` so it also recognizes
repository-style projects, which lay out their source as several top-level
module directories declared in `[tool.uv.build-backend]` rather than a
single `src/`/package directory -- a prerequisite for Steps 4.18-4.19 below
(`repository lint`/`format`/`check`/`jslint`/`jstest` all consume
`code_directories`).

Real repositories built with the `uv_build` backend declare their modules
like this (see `tests/testrepo/pyproject.toml`, already checked into the
repo as a fixture):

```toml
[tool.uv.build-backend]
module-root = ""
module-name = ["common", "i18n", "ui", "datasets"]

[build-system]
requires = ["uv_build>=0.8.7,<0.9.0"]
build-backend = "uv_build"
```

i.e. one directory per entry in `module-name`, resolved relative to
`module-root` (empty string means the project root itself) -- unlike a
library's single `src/`or `<package_name>/` directory.

- [x] Add a typed accessor to `PyProjectData` (`services/pyproject_reader.py`)
  for `[tool.uv.build-backend]`'s `module-name` (list of strings, default
  `[]`) and `module-root` (string, default `""`), following the existing
  pattern used for `default_extras`
- [x] Extend `ProjectContext.code_directories` (`core/context.py`) with a new
  detection branch, in this precedence order:
  1. `src/` (existing)
  2. **New**: `[tool.uv.build-backend].module-name` non-empty -> one
     directory per entry, each `root_directory / module_root / name`,
     included if it exists on disk
  3. `<package_name>/` derived from `[project].name` (existing)
  4. `[tool.hatch.build.targets.wheel].packages[0]` (existing)
  5. Else raise `ConfigurationError` (existing)
  `tests/` is still appended afterwards if present, unchanged.
- [x] Fix `LintRunner.run_lint()`'s `ty check` invocation
  (`services/lint.py`): it currently passes only `code_directories[0]` --
  correct today because a library's `code_directories` only ever has one
  source entry (plus `tests/`), but silently wrong for a multi-module
  repository, which would only ever type-check the first module. Pass every
  non-`tests` entry in `code_directories` instead.
- [x] Verify `check_license_headers()`/`check_future_annotations()`
  (`services/lint.py`) and `run_jslint()` (`services/js_tools.py`) already
  iterate over the full `code_directories` list (they do, as of this
  writing) -- no change needed there, just confirm during review
- [x] Add unit tests for the new `PyProjectData` accessor and the new
  `code_directories` branch, and an integration-level test against the real
  `tests/testrepo/pyproject.toml` fixture asserting `code_directories`
  resolves to `[common/, i18n/, ui/]` (plus `tests/` if present)

**Deviations from the original plan**:
- The `src/` vs. `module-name` vs. flat-layout precedence is enforced with
  `if`/`elif`/`else`, not three independent checks -- a repository's project
  name never coincides with an existing top-level directory in practice, so
  this is mostly a documentation clarification of intent rather than a
  behavior difference, but it's now explicit rather than incidental. Both
  existing library layouts (`src/` and flat/package-name-derived) are
  unchanged and still take priority over `module-name` when both would
  apply, verified by dedicated precedence tests.
- No dedicated `LintRunner` unit test file existed yet (noted as a gap in
  the original plan text); added `tests/unit/test_lint_service.py` rather
  than extending the slower, real-tool
  `tests/integration/test_library_lint_format.py`, to directly assert the
  exact `ty check` argument list via a mocked `process.run` -- both the
  multi-directory regression and confirmation that a library's existing
  single-directory-plus-tests layout is unchanged.
- The real-fixture test landed as
  `tests/integration/test_repository_code_directories.py`, a new file: only
  reads `tests/testrepo`'s real `pyproject.toml`/directories via
  `ContextBuilder`, no install or services lifecycle involved, so it's fast
  and side-effect-free despite living in `tests/integration/`.

**Deliverables**:
- `code_directories` correctly resolves multi-module repository layouts
- `ty check` covers every source module, not just the first

**Tests**:
- `tests/unit/test_pyproject_reader.py`: new accessor, default when absent
- `tests/unit/test_context.py`: `code_directories` precedence order,
  including the new `module-name` branch, and that `src/`/flat-layout still
  win over it when present (backwards compatibility)
- `tests/unit/test_lint_service.py`: `ty check` invoked with every
  non-`tests` code directory, not just the first, and that a library's
  existing single-directory layout still passes exactly that one directory
- `tests/integration/test_repository_code_directories.py`: `code_directories`
  resolves the real `tests/testrepo` fixture's `["common", "i18n", "ui"]`

---

### Step 4.16: Repository `invenio` Command
**Goal**: Add the bare-`invenio` passthrough identified as a real,
unported bash capability in the post-Phase-4 audit
([after_repository_cleanup.md](./after_repository_cleanup.md) §3.1).
`repository_runner.sh` has `run.sh invenio <args>`
(`activate_venv; invenio "$@"`), distinct from `run.sh cli` (which maps to
`invenio-cli`); `library invenio` already has a direct analog, `repository`
never got one.

- [x] Add `repository invenio` to `cli/repository.py`: a pure passthrough
  to the venv's own `invenio` binary, process-replacing (`os.execve`/
  `os.execvpe`) like `repository cli` does via `invenio_cli.exec_invenio_cli`
  -- so `--help` reaches `invenio`'s own help and the exit code is preserved
  exactly. Reuse `services.repository.get_invenio_binary()` (already used
  internally by `rebuild_index`/`reset_repository`) to resolve the binary;
  add an `exec`-based sibling to it (or a shared helper with `cli`'s
  `exec_invenio_cli`) rather than the current blocking `_run_invenio()`,
  since this is a one-shot interactive command like `cli`, not a sequence of
  internal calls
- [x] Use the same `_SERVICES_CONTEXT_SETTINGS` context settings as `cli`/
  `translations` (`allow_extra_args`, `ignore_unknown_options`,
  `help_option_names: []`) so arbitrary `invenio` subcommands and `--help`
  both pass through untouched
- [x] Update `03-migration-guide.md`'s repository command table and
  `00-main-architecture.md` §1.3 to list `invenio` alongside `cli`

**Deviation from the original plan**: added a standalone
`services.repository.exec_invenio()` function (not a shared helper with
`invenio_cli.exec_invenio_cli`) -- the two exec bare, different binaries
(`invenio` vs. `invenio-cli`) with different env needs (`PYTHONWARNINGS=
ignore`, mirroring bash's `run_invenio()`, vs. invenio-cli's
`UV_PRERELEASE` handling), so sharing would have meant a parameterized
helper for two one-line call sites -- not worth the indirection. Mirrors
`ServerRunner._exec_bare_invenio`'s identical approach for `invenio run`
specifically.

**Deliverables**:
- `oarepo-cli repository invenio <args>` mirrors `run.sh invenio <args>`

**Tests** (mirroring `tests/integration/test_repository_misc.py`'s existing
`cli` coverage):
- [x] Test forwards arbitrary args to the venv's `invenio` binary
- [x] Test `--help` reaches `invenio`'s own help output
- [x] Test exit code is preserved exactly
- [x] Test failure when project context can't be discovered

---

### Step 4.17: Repository `shell` Command
**Goal**: Add an interactive shell command for repositories, mirroring
`library shell`. **Note**: unlike Step 4.16, this has no bash equivalent --
`repository_runner.sh` never had a `shell` subcommand. Added for
library/repository UX parity, not bash compatibility.

- [x] Add `repository shell` to `cli/repository.py`: opens an interactive
  bash shell with the venv activated (`VIRTUAL_ENV`/`PATH`), mirroring
  `library_shell`'s environment setup (`VIRTUAL_ENV_PROMPT`, fallback `PS1`,
  dropping inherited `PROMPT_COMMAND`, silencing macOS's bash deprecation
  nag) and process-replacement via `os.execve`
- [x] **Decide the services-lifecycle question before implementing**:
  `library shell` starts services via `ServicesLifecycleManager`
  (docker-services-cli directly) and loads `.env-services` into the shell's
  environment, because a library has no other way to reach its dev
  database. A repository is a Flask app that already resolves its own
  service connections from `invenio.cfg`/`.invenio.private`
  (`configure_local_ports()`), and its services are managed via `invenio-cli
  services *` (see `ServerRunner`/`repository services`), not
  `ServicesLifecycleManager` -- `repository shell` should almost certainly
  start services the same way `ServerRunner`/`repository services start`
  does (`invenio_cli.run_invenio_cli(context, ["services", "start"], ...)`),
  not via the library's `ServicesLifecycleManager`/`.env-services` path.
  Confirm whether a shell even needs services running by default, or
  whether it should mirror `run`'s `--no-services` flag instead of
  `library shell`'s `--skip-services`, for naming consistency with the rest
  of the `repository` command group
- [x] Add `--quiet`/`-q` consistent with other `repository` commands
  (`library shell` has none since it's a forced-`quiet=False` passthrough;
  decide whether to match that or the rest of `repository`'s convention)

**Decisions**: confirmed (user input) that an interactive `invenio shell`
session needs services running, so `repository shell` starts Docker
services by default, matching `run`'s `--no-services` flag name/default
rather than `library shell`'s `--skip-services`. `--quiet`/`-q` was added,
matching the rest of `repository`'s convention rather than `library
shell`'s forced-non-quiet passthrough. No `.env-services`-equivalent
loading: a repository never needs it (see `exec_shell()`'s docstring). The
venv-activation/exec logic itself lives in a new
`services.repository.exec_shell()` (not inline in `cli/repository.py`),
matching this module's established thin-CLI-over-a-service-function
pattern (`exec_invenio`, `rebuild_index`, ...) rather than `library.py`'s
fully-inline style -- and, like `repository cli`/`invenio`, the exec call
itself sits outside the `except OARepoError` block, so an `OSError` from a
failed exec propagates raw rather than being caught and reformatted (unlike
`library_shell`, which does catch it) -- kept consistent with
`repository.py`'s own established convention for its other exec-based
commands rather than mirroring `library_shell` on this specific point.
`repository install` is assumed already run (the venv is assumed to exist,
like `cli`/`invenio`/`run`) -- unlike `library_shell`, this command doesn't
call `ensure_venv_exists()` to create it on demand.

**Deliverables**:
- `oarepo-cli repository shell` opens an interactive shell in the
  repository's venv, with the repository's actual services-lifecycle
  mechanism (not library's) wired up correctly

**Tests** (mirroring `tests/integration/test_library_misc_commands.py`'s
`library shell`/`library invenio` coverage where applicable):
- [x] Test venv activation env vars are set correctly
- [x] Test services are started via the repository's own mechanism, not
  `ServicesLifecycleManager`
- [x] Test failure when project context can't be discovered / venv missing

---

### Step 4.18: Repository `lint`, `format`, `check` Commands
**Goal**: Port `library lint`/`format`/`check` to `repository`, resolving
the open product question raised in the audit
([after_repository_cleanup.md](./after_repository_cleanup.md) §4). Depends
on Step 4.15 for correct multi-module source-directory detection.

- [x] Add `repository lint`/`repository format`/`repository check` to
  `cli/repository.py`, delegating to the existing `services.lint.LintRunner`
  exactly like their `library` counterparts (same `--fix`/`--no-fix` option
  on `lint`/`format`, defaulting to `--fix`; `check` is the always-read-only
  equivalent)
- [x] **Decide**: `LintRunner.run_lint()` unconditionally runs the license
  header check and the `from __future__ import annotations` check as part
  of `lint`/`check` (there's no way to opt out short of a dedicated
  `license-headers` command, which is out of scope here per the current
  request). Confirm this is desired for repository code too before wiring
  it up as-is, since repository projects may have different header/typing
  conventions than library packages
- [x] Confirm `ty.toml`/`.ruff.toml` template generation
  (`configuration/resources.py` templates) doesn't assume a
  single-package/library project shape
- [x] Reuse the exact exception-handling policy decided in Step 4.12
  (narrow `except OARepoError`, not broad `except Exception`) -- these are
  new commands, so they should start out consistent rather than needing a
  follow-up fix

**Decisions/deviations from the original plan**:
- **License headers/future-annotations checks**: confirmed (user input) to
  wire up as-is, matching `library` exactly -- `repository lint`/`check`
  will fail against the real `tests/testrepo` fixture today (it has neither
  convention yet), which is accepted as correct/expected rather than a bug
  to work around.
- **No code duplication** (explicitly requested): extracted the CLI-layer
  command body -- console messages, `LintRunner` construction, exception
  handling, exit-code logic -- into a new shared module,
  `cli/lint_commands.py` (`run_lint()`/`run_format()`/`run_check()`),
  reused verbatim by both `library.py` and `repository.py`. Refactored
  `library_lint`/`library_format`/`library_check` to call it too, rather
  than leaving their bodies duplicated in two places. Each module still
  owns its own Typer registration (decorator, options, docstring) and its
  own `discover_context()` call/error handling, which legitimately differ
  between the two (`library.py` doesn't wrap `discover_context()` in
  `try`/`except` at all, a pre-existing asymmetry with `repository.py`
  left untouched here as out of scope).

**Deliverables**:
- `oarepo-cli repository lint`/`format`/`check`, functionally equivalent to
  their `library` counterparts but operating over a repository's
  multi-module `code_directories`

**Tests** (mirroring `tests/integration/test_library_lint_format.py`/
`test_library_check.py`, plus CLI-wiring tests in
`tests/integration/test_repository_misc.py`):
- [x] Test each command executes against a real multi-module repository
  fixture -- a new, lint-clean `lint_project_multi_module` fixture
  (`tests/integration/conftest.py`) shaped like the real `tests/testrepo`
  (`[tool.uv.build-backend]`, not `tests/testrepo` itself, which isn't
  lint-clean per the decision above and would only prove the command fails,
  not that it works end-to-end)
- [x] Test `ty check` covers every module directory (regression test for
  Step 4.15's fix, exercised for real here via a type error planted in the
  *second* module directory)
- [x] Test `--fix`/`--no-fix` behavior matches `library`'s

---

### Step 4.19: Repository `jslint`, `jstest` Commands
**Goal**: Port `library jslint`/`jstest` to `repository`. Depends on Step
4.15 for correct multi-module source-directory detection.

- [x] Add `repository jslint`/`repository jstest` to `cli/repository.py`,
  delegating to the existing `services.js_tools.run_jslint()`/`run_jstest()`
  exactly like their `library` counterparts
- [x] **Verify before implementing**: `run_jstest()` shells out to `invenio
  webpack run test`, which assumes a webpack/Jest setup created via
  `invenio webpack create` (a library workflow). Confirm a real repository
  project (which already ships `assets/`, `static/`, `ui/`, `i18n/`,
  `babel.ini`, `oarepo.yaml` per `tests/testrepo`) exposes the same `invenio
  webpack run test` entry point, or whether repository JS testing needs a
  different command/setup entirely
- [x] `run_jslint()`'s `package.json`-missing short-circuit (prints "No
  package.json found, skipping") already degrades gracefully -- confirm
  this is the desired behavior for a repository without JS assets configured
  yet, or whether it should be an error instead

**Verification results**: `invenio webpack run test`/`invenio webpack create`
are general Invenio mechanisms, not library-specific -- they collect
*every* registered `invenio_assets.webpack` entry point project-wide (from
installed packages *and* the project's own `pyproject.toml`; `tests/testrepo`
itself registers two: `i18n = "i18n.webpack:theme"`, `components =
"ui.components.webpack:theme"`), and `install_repository()`'s "Run
invenio-cli install" step already triggers this webpack build during a real
`repository install` -- exactly the same precondition `library jstest`
already has (an installed venv with webpack already created). No changes
needed to `services/js_tools.py`; both functions are reused completely
as-is. `run_jslint()`'s package.json-missing skip is kept unchanged too
(not special-cased for repository) -- it's the same safe default already
accepted for a library without its own root-level JS lint config, and a
repository not having one at the project root is the common case (its real
webpack assets/`package.json` live inside the Flask instance path, not the
git-tracked project root -- confirmed against `library_runner.sh`'s own
`assets_path="${instance_path}/assets"`, used by its jstest setup path but
notably *not* by `run_jslint()`, which really does check the bare project
root either way).

**No code duplication** (per Step 4.18's precedent): extracted the
CLI-layer command bodies into a new shared `cli/js_commands.py`
(`run_jslint_command()`/`run_jstest_command()`), reused verbatim by both
`library.py` and `repository.py`, refactoring `library_jslint`/`jstest` to
call it too rather than leaving the duplicated bodies in place.

**Deliverables**:
- `oarepo-cli repository jslint`/`jstest`, functionally equivalent to their
  `library` counterparts wherever the underlying webpack/Jest assumptions
  hold for a repository project

**Tests** (mirroring `tests/integration/test_library_misc_commands.py`'s
`library jslint`/`library jstest` coverage, plus CLI-wiring tests in
`tests/integration/test_repository_misc.py`):
- [x] Test each command's `--help`; a full real `jstest` run needs an
  installed venv plus node/npm/webpack -- too heavy for this suite, and not
  exercised for `library jstest` either
- [x] Test the no-`package.json` short-circuit, against the
  `lint_project_multi_module` fixture added in Step 4.18
- [x] `jslint`/`jstest` reuse `context.code_directories` and its existing
  `tests/`-exclusion unchanged -- already covered by Step 4.15's tests, not
  re-tested here

---

### Step 4.20: Repository `test` Command
**Goal**: Port `library test` to `repository`. Unlike Steps 4.18-4.19, this
one does **not** depend on Step 4.15: `TestOrchestrator` never touches
`code_directories` -- it just runs the venv's own `pytest` with
`cwd=root_directory` and relies on pytest's own test discovery -- so this
should be closer to a drop-in port.

- [x] Add `repository test` to `cli/repository.py`, delegating to the
  existing `services.test_orchestrator.TestOrchestrator` exactly like
  `library test` (same `--skip-services`/`--with-coverage` options)
- [x] Confirm `TestOrchestrator`'s services-start/stop lifecycle
  (`ServicesLifecycleManager`) is the right mechanism for a repository too,
  or whether -- per Step 4.17's services-lifecycle question -- it should
  start services via `invenio-cli services start` instead, for consistency
  with how the rest of the `repository` command group manages services
- [x] Verify pytest/coverage are available in a repository's venv the same
  way they are for a library's (installed as test dependencies), and that a
  freshly-installed repository actually has a `tests/` directory with
  anything to run

**This turned out not to be a drop-in port.** `TestOrchestrator` was not
reused; `services.repository.run_tests()` was added instead, and
`repository test` doesn't call `TestOrchestrator` at all:

- **Services lifecycle**: confirmed -- like Step 4.17 -- that
  `ServicesLifecycleManager` (raw `docker-services-cli`, matching a
  library's setup) doesn't apply to a repository, which manages its own
  `docker/docker-compose.yml` through `invenio-cli services *` instead.
  Beyond that mechanism swap, the *lifecycle shape* itself differs:
  `TestOrchestrator` starts services only if not already running and stops
  them again in a `finally` block once the test run completes -- a
  reasonable "clean up after yourself" default for a library's ephemeral,
  repeated test runs. `repository run`/`shell` never do this "already
  running?" check or auto-stop -- they start services unconditionally
  (unless `--no-services`) and leave them running, since a repository's
  services are a shared, long-lived dev environment other commands
  (`run`, `shell`) expect to keep using. `repository test` follows that
  same shape: unconditional start via `invenio_cli.run_invenio_cli(...,
  ["services", "start"])` unless `--no-services` (naming matches
  `run`/`shell`, not `library test`'s `--skip-services`), no stop
  afterward.
- **Coverage target**: `TestOrchestrator._build_pytest_command()` passes a
  single `--cov <name>`, derived from `[project].name` -- correct for a
  library's one `src/`-or-package-dir layout, but wrong for a repository:
  its `code_directories` are typically several top-level modules (Step
  4.15's `[tool.uv.build-backend]` support), each already a real
  importable package name, and the project's own declared name (e.g.
  `testrepo`) isn't one of them at all. `run_tests()` instead passes
  `--cov <name>` for every non-`tests` `code_directories` entry.
- **pytest/coverage availability**: confirmed a real problem, not just a
  hypothetical -- `tests/testrepo`'s `pyproject.toml` declares no `tests`
  extras group (unlike a library, which either declares one itself or
  depends on it transitively), so `TestOrchestrator`'s
  extras-group-triggered install would never fire, leaving `pytest`
  genuinely absent from a fresh repository's venv. `run_tests()` installs
  `pytest`/`pytest-cov` directly (`uv pip install --python <venv's own
  python> ...`) if missing, unconditionally, rather than gating on an
  extras group. (Caught the hard way during testing: installing against
  `context.python_binary` -- the interpreter used to *create* the venv, not
  the venv's own -- fails against a real uv-managed system interpreter,
  "externally managed"; fixed to target the venv's own python explicitly.)
- **No shared module with `library test`** (unlike Steps 4.18/4.19): the
  underlying orchestration differs enough (services mechanism, lifecycle
  shape, coverage targeting) that forcing one shared implementation would
  need a strategy-style injection for services lifecycle alone, adding
  more complexity than the ~15-line CLI body it would save. `library_test`
  is therefore untouched, still using `TestOrchestrator` directly.

**Deliverables**:
- `oarepo-cli repository test`, running the repository's test suite with
  invenio-cli-managed services and multi-module-aware coverage

**Tests** (unit tests for `services.repository.run_tests()` in
`tests/unit/test_repository_service.py`, CLI-wiring tests in
`tests/integration/test_repository_misc.py`, and a new
`tests/integration/test_repository_test.py` for real end-to-end coverage):
- [x] Test execution against a real project fixture -- the
  `lint_project_multi_module` fixture from Step 4.18, always with
  `--no-services` (no Docker needed for this at all); `tests/testrepo`
  itself has no `tests/` directory, so isn't suited to exercising a real
  passing/failing run
- [x] Test `--no-services`/`--with-coverage` behavior, and that the
  services-lifecycle/coverage-targeting deviations above hold (invenio-cli
  used, not `ServicesLifecycleManager`; every module directory covered, not
  a single package name; pytest installed on demand against the venv's own
  python)

---

## Phase 5: Repository Installer

### Step 5.1: Repository Installer CLI
**Goal**: Implement top-level `new` command.

- [x] Implement `cli/installer.py` with `new_repository()` function
- [x] Options: `--python`, `--template`, `--version`, `--uv`, `--uvx`, `--config`
- [x] Positional: `REPOSITORY_NAME`
- [x] Validate all inputs

**Deliverables**:
- Installer command skeleton

**Tests** (`tests/unit/test_installer_cli.py`):
- [x] Test argument parsing
- [x] Test validation errors
- [x] Test help text

---

### Step 5.2: Repository Installation Workflow
**Goal**: Implement complete repository scaffolding.

- [x] Implement `services/repository_installer.py` with `RepositoryInstaller` class
- [x] Method: `install(name, *, template, version, config_file)` → Path (no
      `python_binary` -- copier runs in-process, the same
      `services.models.ModelManager` approach, so there's no separate copier
      process left to select an interpreter for; see the class docstring)
- [x] Run `copier copy` with template (via `copier.run_copy`, in-process,
      like `ModelManager`, not `uvx --python ... copier copy ...`)
- [x] Generate SSL certificates with openssl
- [x] Setup Docker compose symlinks
- [x] Initialize git repository (if not in CI)
- [x] Return path to created repository

**Deliverables**:
- Full repository installation

**Tests** (`tests/integration/test_repository_installer.py`):
- [x] Test copier executed with params
- [x] Test certificates generated
- [x] Test git initialized
- [x] Integration test: create real repository (slow)

---

### Step 5.3: Integration Tests for Installer
**Goal**: End-to-end installer tests.

- [ ] Test full installation flow
- [ ] Test template variations (GitHub vs local)
- [ ] Test error handling (invalid template, missing python)

**Tests** (`tests/integration/test_repository_installer_e2e.py`):
- [ ] Test successful installation
- [ ] Test certificate files exist
- [ ] Test docker compose file present
- [ ] Test git repo initialized

---

## Phase 6: Hardening & Polish

### Step 6.1: Signal Handling Enhancement
**Goal**: Robust signal handling for long-running processes.

- [ ] Enhance `core/signals.py` with comprehensive handler
- [ ] Forward signals to child processes
- [ ] Graceful shutdown with timeouts
- [ ] Cleanup on unexpected termination

**Tests** (`tests/fault_tolerance/test_signal_handling.py`):
- [ ] Test SIGINT forwarded to children
- [ ] Test graceful shutdown completes
- [ ] Test timeout forces kill

---

### Step 6.4: Comprehensive Documentation
**Goal**: User-facing documentation.

- [ ] Update README.md with installation instructions
- [ ] Write migration guide (already done)
- [ ] Add command reference docs
- [ ] Create CONTRIBUTING.md for developers
- [ ] Add docstrings to all public APIs

**Deliverables**:
- Complete documentation suite

---

### Step 6.5: Final Characterization Tests
**Goal**: Ensure full behavioral parity.

- [ ] Run characterization test suite against all commands
- [ ] Fix any discrepancies
- [ ] Document known differences (if any)

**Tests** (`tests/compatibility/`):
- [ ] All characterization tests pass
- [ ] Exit codes match
- [ ] Help text structure matches

---

## Phase 7: Release Preparation

### Step 7.1: CI/CD Pipeline
**Goal**: Automated testing and deployment.

- [ ] Configure GitHub Actions for CI
- [ ] Run all test suites on PR
- [ ] Build and publish to PyPI on tag
- [ ] Generate coverage reports

**Deliverables**:
- Automated CI/CD pipeline

---

### Step 7.2: Release Notes & Tagging
**Goal**: Prepare v1.0.0 release.

- [ ] Write release notes
- [ ] Tag release
- [ ] Publish to PyPI
- [ ] Announce to community

---

## Summary Statistics

| Phase | Steps | Status |
|-------|-------|--------|
| 0: Project Setup | 4 | [x] (4/4 complete) |
| 1: Core Domain Models | 4 | [x] (4/4 complete) |
| 2: Virtual Environment | 3 | [x] (3/3 complete) |
| 3: Library Commands | 12 | [x] (12/12 complete) |
| 4: Repository Commands | 10 | [ ] |
| 5: Repository Installer | 3 | [ ] |
| 6: Hardening | 5 | [ ] |
| 7: Release Prep | 2 | [ ] |
| **Total** | **43** | **[~] (23/43 complete)** |

---

## Notes

- Each step must have **passing tests** before marking complete
- Steps within a phase can often be done in parallel if dependencies allow
- Integration tests may require external tools (Docker, uv); mark as skipped if unavailable
- Characterization tests require both shell scripts and Python CLI to be present
- If blocked on a step, mark with `[!]` and document the blocker

---

**Last Updated**: 2026-08-01
**Version**: 1.0.0
