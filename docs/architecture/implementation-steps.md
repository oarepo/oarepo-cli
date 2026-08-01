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
| 5: Repository Installer | `oarepo-cli repo-install <name>` works identically to the shell script |
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

For unit-level tests, call `run()`/`stream()`/`get_output()` directly against real, trivial, always-available commands (`echo`, `true`, `false`, `python3 -c`) — no fixture needed. For workflow-level tests of services that shell out to slow, optional, side-effecting external tools (`uv`, `docker-services-cli`, `copier`, `invenio-cli`), fake at the **OS boundary** with [`pytest-subprocess`](https://pytest-subprocess.readthedocs.io/)'s `fake_process` fixture, which patches `subprocess.Popen` process-wide and intercepts calls transparently — no injected executor required. See Step 2.2 and onward for its use in workflow tests.

- [x] Define `services/process.py` with `ProcessResult` dataclass
- [x] Implement `run()`, `stream()`, `get_output()` as plain module-level functions wrapping `subprocess.run`/`Popen`
- [x] Never use `shell=True`; always pass args as list
- [x] Implement timeout handling → `TimeoutExceeded`, with partial output captured
- [x] Ensure proper encoding handling (UTF-8)
- [x] Add `pytest-subprocess` as a dev dependency, for use starting in Phase 2's workflow tests

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

**Tests** (`tests/workflow/test_venv_workflow.py`):
- [x] Test venv creation with `pytest-subprocess` faking `uv`/`pip` calls
- [x] Test setuptools installed first
- [x] Test oarepo installed with correct version constraint
- [x] Test editable vs non-editable modes
- [x] Test force recreation removes existing venv
- [x] Test skip creation if venv already exists
- [x] Integration test: real venv created in temp dir

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

- [ ] Install Typer and Pydantic
- [ ] Implement `cli/main.py` with root `app`
- [ ] Add global options: `--verbose`, `--config`, `--cd`
- [ ] Create `cli/library.py` with empty `library_app`
- [ ] Create `cli/repository.py` with empty `repository_app`
- [ ] Register subcommands with root app
- [ ] Verify `oarepo-cli --help` displays correctly

**Deliverables**:
- Working CLI skeleton
- Help text matches shell script structure

**Tests** (`tests/unit/test_cli_skeleton.py`):
- [ ] Test `--help` shows all commands
- [ ] Test unknown command returns exit code 2
- [ ] Test global options parsed correctly
- [ ] Test `--version` displays package version

---

### Step 3.2: Library `venv` Command
**Goal**: Implement `oarepo-cli library venv` command.

- [ ] Implement `library_venv()` function in `cli/library.py`
- [ ] Options: `--force`, `--no-editable`
- [ ] Inject `ProjectContext` and `CliConfig`
- [ ] Call `VirtualEnvironmentManager.ensure_venv()`
- [ ] Display success message with venv path

**Deliverables**:
- Working `venv` command
- Matches shell script behavior

**Tests** (`tests/integration/test_library_venv.py`):
- [ ] Test venv created in temp project
- [ ] Test `--force` recreates existing venv
- [ ] Test `--no-editable` builds wheel instead
- [ ] Test help text matches shell script
- [ ] Characterization test: exit code matches bash

---

### Step 3.3: Library `upgrade` Command
**Goal**: Implement `oarepo-cli library upgrade` command.

- [ ] Implement `library_upgrade()` function
- [ ] Stop services (if running)
- [ ] Remove existing venv
- [ ] Clean uv cache
- [ ] Recreate venv with `ensure_venv(force=True)`

**Deliverables**:
- Working `upgrade` command

**Tests** (`tests/workflow/test_upgrade_workflow.py`):
- [ ] Test venv removed and recreated
- [ ] Test cache cleaned
- [ ] Test services stopped before upgrade
- [ ] Test success message displayed

---

### Step 3.4: Services Lifecycle Manager
**Goal**: Manage Docker service lifecycle.

- [ ] Implement `services/services_lifecycle.py` with `ServicesLifecycleManager`
- [ ] Method: `start_services(config)` → env dict
- [ ] Method: `stop_services()` → None
- [ ] Use `docker-services-cli up/down`
- [ ] Write/read `.env-services` file
- [ ] Support DB, search, MQ, cache, S3 options

**Deliverables**:
- Service lifecycle management
- Environment file handling

**Tests** (`tests/workflow/test_services_lifecycle.py`):
- [ ] Test services start with `pytest-subprocess` faking `docker-services-cli`
- [ ] Test `.env-services` file written
- [ ] Test services stop removes file
- [ ] Test environment variables loaded from file
- [ ] Integration test: real Docker services (if available)

---

### Step 3.5: Library `start`/`stop` Commands
**Goal**: Implement service start/stop commands.

- [ ] Implement `library_start()` and `library_stop()` functions
- [ ] Delegate to `ServicesLifecycleManager`
- [ ] Display colored status messages

**Deliverables**:
- Start/stop commands

**Tests** (`tests/integration/test_library_services.py`):
- [ ] Test start creates env file
- [ ] Test stop removes env file
- [ ] Test exit codes match bash

---

### Step 3.6: Test Orchestrator
**Goal**: Orchestrate pytest execution with services.

- [ ] Implement `services/test_orchestrator.py` with `TestOrchestrator` class
- [ ] Method: `run_tests(pytest_args=[], coverage=False, skip_services=False)` → CommandResult
- [ ] Start services if not skipped
- [ ] Install pytest-cov if coverage enabled
- [ ] Run pytest with appropriate args
- [ ] Stop services after tests
- [ ] Return structured result

**Deliverables**:
- Test orchestration service
- Coverage support

**Tests** (`tests/workflow/test_test_orchestrator.py`):
- [ ] Test services start before pytest
- [ ] Test services stop after pytest
- [ ] Test coverage flags added when enabled
- [ ] Test skip_services skips start/stop
- [ ] Test failure status returned on pytest failure
- [ ] Integration test: run real pytest in temp project

---

### Step 3.7: Library `test` Command
**Goal**: Implement `oarepo-cli library test` command.

- [ ] Implement `library_test()` function
- [ ] Options: `--skip-services`, `--with-coverage`, positional `args`
- [ ] Inject orchestrator and call `run_tests()`
- [ ] Display results with colors
- [ ] Exit with pytest exit code

**Deliverables**:
- Working `test` command

**Tests** (`tests/integration/test_library_test.py`):
- [ ] Test tests run successfully
- [ ] Test coverage enabled with flag
- [ ] Test skip-services works
- [ ] Test extra pytest args passed through
- [ ] Characterization test: output matches bash

---

### Step 3.8: Library `clean` Command
**Goal**: Implement `oarepo-cli library clean` command.

- [ ] Implement `library_clean()` function
- [ ] Stop services
- [ ] Remove venv directory
- [ ] Remove `.env-services` file
- [ ] Display cleanup summary

**Deliverables**:
- Working `clean` command

**Tests** (`tests/workflow/test_cleanup_workflow.py`):
- [ ] Test venv removed
- [ ] Test env-services file removed
- [ ] Test services stopped
- [ ] Test idempotent (works even if nothing exists)

---

### Step 3.9: Library `shell` and `invenio` Commands
**Goal**: Implement shell and invenio passthrough commands.

- [ ] Implement `library_shell()` and `library_invenio()` functions
- [ ] Options: `--skip-services`
- [ ] Ensure venv exists
- [ ] Start services if not skipped
- [ ] Activate venv and exec bash/invenio
- [ ] Pass through all arguments

**Deliverables**:
- Shell and invenio commands
- Argument passthrough

**Tests** (`tests/integration/test_library_passthrough.py`):
- [ ] Test shell starts interactive bash
- [ ] Test invenio runs with args
- [ ] Test skip-services skips service start
- [ ] Test arguments passed correctly

---

### Step 3.10: Library `lint` and `format` Commands
**Goal**: Implement linting and formatting commands.

- [ ] Implement `library_lint()` function
- [ ] Generate `.ruff.toml` config
- [ ] Run `ruff check`, `mypy`, `pyright`
- [ ] Check license headers and future annotations
- [ ] Implement `library_format()` function
- [ ] Run `ruff format` and `ruff check --fix`

**Deliverables**:
- Lint and format commands

**Tests** (`tests/integration/test_library_lint_format.py`):
- [ ] Test lint passes on clean code
- [ ] Test lint fails on dirty code
- [ ] Test format fixes issues
- [ ] Test license header check
- [ ] Test future annotations check

---

### Step 3.11: Library `translations`, `license-headers`, `jslint`, `jstest` Commands
**Goal**: Implement remaining library commands.

- [ ] Implement `library_translations()` → calls `make-translations`
- [ ] Implement `library_license_headers()` → adds headers to Python files
- [ ] Implement `library_jslint()` → runs ESLint and Prettier
- [ ] Implement `library_jstest()` → sets up and runs Jest
- [ ] All commands support `--skip-services` where applicable

**Deliverables**:
- Complete set of library commands

**Tests** (`tests/integration/test_library_misc_commands.py`):
- [ ] Test each command executes without error
- [ ] Test help text for each command
- [ ] Characterization tests for key commands

---

### Step 3.12: Library `oarepo-versions` Command
**Goal**: Implement JSON version reporting.

- [ ] Implement `library_oarepo_versions()` function
- [ ] Parse pyproject.toml for oarepo versions
- [ ] Resolve Python versions from constraints
- [ ] Output JSON: `{"oarepo_versions": [...], "python_versions": [...], "node_versions": [...]}`

**Deliverables**:
- Version reporting command

**Tests** (`tests/integration/test_library_versions.py`):
- [ ] Test JSON output valid
- [ ] Test versions extracted correctly
- [ ] Characterization test: output matches bash exactly

---

## Phase 4: Repository Commands

### Step 4.1: Repository `install` Command
**Goal**: Implement repository installation.

- [ ] Implement `repository_install()` function
- [ ] Ensure venv exists
- [ ] Sync dependencies with `uv sync`
- [ ] Copy translations overlay
- [ ] Get instance path via invenio shell
- [ ] Create symlinks for invenio.cfg
- [ ] Run `invenio-cli install`
- [ ] Configure local service ports in `.invenio.private`
- [ ] Compile backend translations

**Deliverables**:
- Working install command

**Tests** (`tests/workflow/test_repository_install.py`):
- [ ] Test venv synced
- [ ] Test translations copied
- [ ] Test instance path created
- [ ] Test `.invenio.private` configured
- [ ] Integration test: full install in temp repo

---

### Step 4.2: Repository `upgrade` Command
**Goal**: Implement repository upgrade.

- [ ] Implement `repository_upgrade()` function
- [ ] Remove venv and uv.lock
- [ ] Clean uv cache
- [ ] Reinstall repository

**Deliverables**:
- Working upgrade command

**Tests** (`tests/workflow/test_repository_upgrade.py`):
- [ ] Test venv and lock removed
- [ ] Test cache cleaned
- [ ] Test reinstall succeeds

---

### Step 4.3: Repository `services` Subcommands
**Goal**: Implement services subcommands (setup/start/stop/destroy).

- [ ] Implement `repository_services()` with subcommands
- [ ] Delegate to `run_invenio_cli services ...`
- [ ] Pass through all arguments

**Deliverables**:
- Services subcommands

**Tests** (`tests/integration/test_repository_services.py`):
- [ ] Test each subcommand delegates correctly
- [ ] Test arguments passed through

---

### Step 4.4: Model Manager
**Goal**: Implement record model management via copier.

- [ ] Implement `services/models.py` with `ModelManager` class
- [ ] Method: `create_model(name, config_file=None)` → None
- [ ] Method: `update_model(name, answers_file=None)` → None
- [ ] Use `uvx copier copy` and `copier update`
- [ ] Support GitHub templates and local paths
- [ ] Reinstall repository after model changes

**Deliverables**:
- Model management service

**Tests** (`tests/workflow/test_model_manager.py`):
- [ ] Test model creation with `pytest-subprocess` faking `copier`
- [ ] Test model update with answers file
- [ ] Test template URL handling
- [ ] Integration test: create real model (slow)

---

### Step 4.5: Repository `model` Command
**Goal**: Implement `oarepo-cli repository model` command.

- [ ] Implement `repository_model()` with `create` and `update` subcommands
- [ ] Options: template URL, version, config file
- [ ] Delegate to `ModelManager`

**Deliverables**:
- Model command

**Tests** (`tests/integration/test_repository_model.py`):
- [ ] Test model create subcommand
- [ ] Test model update subcommand
- [ ] Test help text

---

### Step 4.6: Local Package Manager
**Goal**: Manage local packages in `tool.uv.sources`.

- [ ] Implement `services/local_packages.py` with `LocalPackageManager` class
- [ ] Method: `add_package(path)` → None
- [ ] Method: `remove_package(name)` → None
- [ ] Parse and modify pyproject.toml
- [ ] Trigger repository upgrade after changes

**Deliverables**:
- Local package management

**Tests** (`tests/workflow/test_local_packages.py`):
- [ ] Test package added to sources
- [ ] Test package removed from sources
- [ ] Test pyproject.toml updated correctly

---

### Step 4.7: Repository `local` Command
**Goal**: Implement `oarepo-cli repository local` command.

- [ ] Implement `repository_local()` with `add` and `remove` subcommands
- [ ] Delegate to `LocalPackageManager`

**Deliverables**:
- Local command

**Tests** (`tests/integration/test_repository_local.py`):
- [ ] Test add subcommand
- [ ] Test remove subcommand

---

### Step 4.8: Server Runner
**Goal**: Implement repository server execution with signal handling.

- [ ] Implement `services/server.py` with `ServerRunner` class
- [ ] Method: `run(no_services=False, no_celery=False)` → None
- [ ] Start Docker services if not skipped
- [ ] Start Celery worker in background if not skipped
- [ ] Run `invenio run` or `invenio-cli run`
- [ ] Handle SIGINT/SIGTERM for graceful shutdown
- [ ] Cleanup services on exit

**Deliverables**:
- Server runner with signal handling

**Tests** (`tests/workflow/test_server_runner.py`):
- [ ] Test server starts with services
- [ ] Test server starts without celery
- [ ] Test signal handling stops everything
- [ ] Test cleanup on interrupt

---

### Step 4.9: Repository `run` Command
**Goal**: Implement `oarepo-cli repository run` command.

- [ ] Implement `repository_run()` function
- [ ] Options: `--no-services`, `--no-celery`
- [ ] Delegate to `ServerRunner`

**Deliverables**:
- Running command

**Tests** (`tests/integration/test_repository_run.py`):
- [ ] Test run with services
- [ ] Test run without celery
- [ ] Test signal handling

---

### Step 4.10: Repository `cli`, `translations`, `index`, `reset`, `info` Commands
**Goal**: Implement remaining repository commands.

- [ ] Implement `repository_cli()` → passthrough to `invenio-cli`
- [ ] Implement `repository_translations()` → extract/compile
- [ ] Implement `repository_index_rebuild()` → destroy/init/rebuild indices
- [ ] Implement `repository_reset()` → full reset with confirmation prompt
- [ ] Implement `repository_info()` → show Python version and models

**Deliverables**:
- Complete repository command set

**Tests** (`tests/integration/test_repository_misc.py`):
- [ ] Test each command executes
- [ ] Test reset confirmation prompt
- [ ] Test info output format
- [ ] Characterization tests

---

## Phase 5: Repository Installer

### Step 5.1: Repository Installer CLI
**Goal**: Implement top-level `repo-install` command.

- [ ] Implement `cli/installer.py` with `repo_install()` function
- [ ] Options: `--python`, `--template`, `--version`, `--uv`, `--uvx`, `--config`
- [ ] Positional: `REPOSITORY_NAME`
- [ ] Validate all inputs

**Deliverables**:
- Installer command skeleton

**Tests** (`tests/unit/test_installer_cli.py`):
- [ ] Test argument parsing
- [ ] Test validation errors
- [ ] Test help text

---

### Step 5.2: Repository Installation Workflow
**Goal**: Implement complete repository scaffolding.

- [ ] Implement `services/repository_installer.py` with `RepositoryInstaller` class
- [ ] Method: `install(name, template, version, python_binary)` → Path
- [ ] Run `copier copy` with template
- [ ] Generate SSL certificates with openssl
- [ ] Setup Docker compose symlinks
- [ ] Initialize git repository (if not in CI)
- [ ] Return path to created repository

**Deliverables**:
- Full repository installation

**Tests** (`tests/workflow/test_repository_installer.py`):
- [ ] Test copier executed with params
- [ ] Test certificates generated
- [ ] Test git initialized
- [ ] Integration test: create real repository (slow)

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

### Step 6.2: Structured Logging
**Goal**: Optional structured logging for automation.

- [ ] Implement `utils/logging.py` with colored and JSON formatters
- [ ] Configurable log level via `--verbose`
- [ ] Redact sensitive values (passwords, tokens)
- [ ] Log subprocess commands (sanitized)

**Tests** (`tests/unit/test_logging.py`):
- [ ] Test colored output format
- [ ] Test JSON output format
- [ ] Test sensitive value redaction

---

### Step 6.3: Performance Benchmarking
**Goal**: Measure and optimize performance.

- [ ] Benchmark CLI startup time
- [ ] Benchmark venv creation
- [ ] Compare with shell script timings
- [ ] Identify and fix bottlenecks

**Tests** (`tests/benchmarks/`):
- [ ] Startup < 100ms for lightweight commands
- [ ] No regression vs shell scripts

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
| 1: Core Domain Models | 4 | [~] (2/4 complete) |
| 2: Virtual Environment | 3 | [ ] |
| 3: Library Commands | 12 | [ ] |
| 4: Repository Commands | 10 | [ ] |
| 5: Repository Installer | 3 | [ ] |
| 6: Hardening | 5 | [ ] |
| 7: Release Prep | 2 | [ ] |
| **Total** | **43** | **[~] (6/43 complete)** |

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
