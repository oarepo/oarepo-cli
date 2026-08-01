# OARepo CLI Python Implementation Architecture

## Executive Summary

This document describes the architecture for replacing the existing OARepo shell-script runners (`library_runner.sh`, `repository_installer.sh`, `repository_runner.sh`) with a robust, maintainable Python command-line application called `oarepo-cli`.

The new implementation preserves all existing user-facing behavior while replacing shell-specific parsing, global state, command dispatch, environment mutation, and process orchestration with explicit Python abstractions.

---

## 1. Feature Inventory & Compatibility Matrix

### 1.1 Library Runner Commands

| Command | Options | Description | Status |
|---------|---------|-------------|--------|
| `venv` | `--force`, `--no-editable` | Set up virtual environment | Must preserve |
| `upgrade` | - | Clean cache and recreate venv | Must preserve |
| `start` | - | Start services for testing | Must preserve |
| `stop` | - | Stop services after testing | Must preserve |
| `test` | `--skip-services`, `--with-coverage` | Run pytest tests | Must preserve |
| `oarepo-versions` | - | List supported OARepo versions (JSON output) | Must preserve |
| `clean` | - | Stop services, remove venv | Must preserve |
| `shell` | `--skip-services` | Start bash shell in venv | Must preserve |
| `invenio` | `--skip-services` | Run Invenio commands | Must preserve |
| `translations` | - | Extract/compile translations via oarepo-tools | Must preserve |
| `lint` | - | Run ruff, mypy, pyright, license checks | Must preserve |
| `format` | - | Format code with ruff | Must preserve |
| `license-headers` | - | Add MIT license headers | Must preserve |
| `jslint` | - | Run ESLint and Prettier | Must preserve |
| `jstest` | `setup`, `--skip-services` | Run JavaScript tests (Jest) | Must preserve |
| `self-update` | - | Download latest runner script | **Not implemented** (deprecated, use `pip install --upgrade oarepo-cli`) |
| `--no-editable` | (global flag) | Build wheel instead of editable install | Must preserve |

### 1.2 Repository Installer Commands

| Command/Option | Description | Status |
|----------------|-------------|--------|
| `--python <binary>` | Specify Python binary (default: python3.14) | Must preserve |
| `--template <url/path>` | Copier template source | Must preserve |
| `--version <ref>` | Template version/tag | Must preserve |
| `--uv <binary>` | uv executable path | Must preserve |
| `--uvx <binary>` | uvx executable path | Must preserve |
| `--config <file>` | Additional copier data file | Must preserve |
| `REPOSITORY_NAME` | Positional argument for repo name | Must preserve |

**Side effects:** Creates SSL certificates, initializes git repo, sets up Docker compose symlinks

### 1.3 Repository Runner Commands

| Command | Subcommands/Options | Description | Status |
|---------|---------------------|-------------|--------|
| `install` | - | Install repository in venv | Must preserve |
| `upgrade` | - | Clean and reinstall | Must preserve |
| `services` | `setup`, `start`, `stop`, `destroy` | Docker service management | Must preserve |
| `model` | `create [name] [config]`, `update [name] [answers]` | Record model management | Must preserve |
| `local` | `add <path>`, `remove <name>\|--all>` | Local package management | Must preserve |
| `run` | `--no-services`, `--no-celery` | Start repository server | Must preserve |
| `cli` | `[subcommand...]` | Delegates to invenio-cli | Must preserve |
| `translations` | `compile` | Backend translations only | Must preserve |
| `index` | `rebuild` | Rebuild search index | Must preserve |
| `reset` | - | Full reset with confirmation prompt | Must preserve |
| `info` | - | Show Python version and models | Must preserve |
| `self-update` | - | Download latest runner script | **Not implemented** (deprecated, use `pip install --upgrade oarepo-cli`) |

### 1.4 Environment Variables

| Variable | Default | Description | Typed Config |
|----------|---------|-------------|--------------|
| `UV_EXTRA_INDEX_URL` | GitLab PyPI | Extra pip index URL | `uv.extra_index_url` |
| `PIP_EXTRA_INDEX_URL` | GitLab PyPI | Legacy extra index | Deprecated (use above) |
| `OAREPO_VERSION` | First from pyproject.toml | OARepo version to use | `oarepo.version` |
| `PYTHON` | Auto-detected | Python binary path | `python.binary` |
| `UV_PROJECT_ENVIRONMENT` | `.venv` | Virtual env path | `venv.path` |
| `SKIP_SERVICES` | Empty | Skip service lifecycle | Not configurable (cmd flag) |
| `NO_EDITABLE` | Empty | Use wheel build mode | `build.editable` (bool) |
| `WITH_COVERAGE` | Empty | Enable pytest coverage | `test.coverage` (bool) |
| `MODEL_TEMPLATE` | GitHub URL | Model copier template | `model.template_url` |
| `MODEL_TEMPLATE_VERSION` | `rdm-14` | Model template version | `model.template_version` |
| `COLLECTED_TRANSLATIONS_DIR` | Auto-detected | Translation overlay source | `translations.overlay_dir` |
| `LC_TIME` | `en_US.UTF-8` | Locale for dates | Not needed (system default) |
| `INVENIO_CELERY_WORKER_POOL` | `threads` (macOS) | Celery pool type | `celery.pool_type` |
| `INVENIO_CELERY_WORKER_CONCURRENCY` | `10` (macOS) | Celery worker count | `celery.concurrency` |
| `ORGANIZATION` | `CESNET z.s.p.o` | License header org | `license.organization` |
| `DEMO_USER_PASSWORD` | `123456` | Reset admin password | **Do not log** |

### 1.5 External Dependencies

| Tool | Usage | Required |
|------|-------|----------|
| `uv` / `uvx` | Package management, venv creation | Yes |
| `copier` | Repository/model scaffolding | Yes (via uvx) |
| `docker compose` | Service orchestration | Optional (for services) |
| `docker-services-cli` | Service environment setup | Optional |
| `pytest` | Python testing | Optional (for test cmd) |
| `ruff` | Linting/formatting | Optional |
| `mypy` / `pyright` | Type checking | Optional |
| `npm` / `pnpm` | JavaScript dependencies | Optional |
| `jest` | JavaScript testing | Optional |
| `curl` | Self-update download | Yes |
| `openssl` | Certificate generation | Yes |
| `git` | Repo initialization | Optional |

### 1.6 Identified Issues & Risks

| Issue | Severity | Recommendation |
|-------|----------|----------------|
| Shell string interpolation in subprocess calls | High | Use `list` args, never `shell=True` |
| Global mutable state via exported variables | Medium | Use explicit context objects |
| `grep/sed/awk` TOML parsing is fragile | High | Use `tomllib` (Python 3.11+) |
| Self-update downloads from raw GitHub | Medium | Consider signed releases or pypi |
| Interactive prompts without timeout | Low | Add timeout for automation |
| Exit codes not consistently propagated | Medium | Ensure subprocess exit codes are returned |
| No structured logging | Low | Add optional JSON logging mode |
| Race conditions in concurrent executions | Medium | Add lock files for venv operations |

---

## 2. Architecture Overview

### 2.1 Design Principles

1. **Maintainability first**: Clear separation of concerns, typed interfaces, minimal cleverness
2. **Reuse where stable**: Shared infrastructure (process execution, environment) but separate domain workflows
3. **Behavioral compatibility**: Preserve exit codes, stdout/stderr streams, help text structure
4. **Testability**: Dependency injection around network access only, where a real alternate backend exists to swap in for testing. Filesystem, environment-variable, and subprocess-execution code call `pathlib.Path`/`os.environ`/`subprocess` directly with no injected protocol — there is exactly one real implementation of each, so a `Protocol`/`ABC` would only add indirection. They're tested against real (temporary) state instead: `tmp_path` for the filesystem, `monkeypatch` for environment variables, and `pytest-subprocess` (patches `subprocess.Popen` process-wide) for the unit tests in §3 of `02-testing-strategy.md` that need to simulate absent binaries — integration tests invoke the slow, external, side-effecting tools (`uv`, `docker-services-cli`, `copier`) for real against `tests/testlib/`
5. **Explicit error handling**: Custom exception hierarchy, normalized error messages
6. **No premature abstraction**: Only abstract when there are 2+ concrete implementations

### 2.2 CLI Framework Decision

**Decision: Use Typer**

**Rationale:**
- Built on Click with Pydantic integration for automatic type validation
- Excellent help text generation with color support (matches shell scripts)
- Native async support for future extensibility
- Active maintenance by Astral (same team as ruff/uv)
- Easier migration path from shell-style subcommands
- Automatic argument parsing with proper POSIX compliance

**Alternative considered:**
- `argparse`: Too verbose, no nested subcommand groups out-of-box
- `Click`: Good but requires more boilerplate for typed options
- `rich-click`: Adds formatting to Click but Typer already includes this

### 2.3 Single Executable vs Multiple Entry Points

**Decision: Single `oarepo-cli` executable with subcommand groups**

```bash
oarepo-cli library <command>    # Library runner replacement
oarepo-cli repository <command> # Repository runner replacement
oarepo-cli repo-install         # Repository installer (top-level for convenience)
```

**Rationale:**
- Single package installation, easier version management
- Shared configuration and state between modes
- Consistent help structure and option handling
- Easier to add cross-cutting features (logging, diagnostics)
- Matches modern CLI patterns (git, docker, npm)

---

## 3. Package Structure

```
oarepo_cli/
├── __init__.py                 # Package metadata
├── __main__.py                 # Entry point for `python -m oarepo_cli`
├── cli/
│   ├── __init__.py
│   ├── main.py                 # Root CLI group, global options
│   ├── library.py              # Library subcommand group
│   ├── repository.py           # Repository subcommand group
│   └── shared.py               # Shared command options/helpers
├── core/
│   ├── __init__.py
│   ├── context.py              # ProjectContext: discovery, config, state
│   ├── config.py               # Configuration loading from pyproject.toml
│   ├── errors.py               # Exception hierarchy
│   ├── platform.py             # Platform detection utilities
│   └── signals.py              # Signal handling for long-running processes
├── services/
│   ├── __init__.py
│   ├── process.py              # run()/stream()/get_output() — plain functions, no protocol
│   ├── network.py              # NetworkClient protocol + implementations
│   ├── venv.py                 # VirtualEnvironmentManager
│   ├── version_resolver.py     # Python/OARepo version resolution
│   ├── pyproject_reader.py     # TOML parsing with tomllib
│   ├── services_lifecycle.py   # Docker service lifecycle manager
│   ├── test_orchestrator.py    # Test/lint orchestration
│   ├── translations.py         # Translation management
│   ├── models.py               # Record model management (copier)
│   ├── local_packages.py       # Local package management
│   ├── index_manager.py        # Search index operations
│   └── server.py               # Server/run command orchestration
├── adapters/
│   ├── __init__.py
│   ├── http_client.py          # requests/httpx wrapper
│   └── fake_*                  # Test doubles for protocols with a real swappable backend (e.g. NetworkClient)
└── utils/
    ├── __init__.py
    ├── logging.py              # Structured logging setup
    ├── formatting.py           # Colored output helpers
    └── locks.py                # File-based concurrency control
```

---

## 4. Component Specifications

### 4.1 Core Context (`core/context.py`)

**Responsibility**: Central project context containing discovered configuration, resolved paths, and runtime state.

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ProjectContext:
    """Immutable project context discovered at startup."""

    root_directory: Path  # Directory containing pyproject.toml
    pyproject_path: Path  # Full path to pyproject.toml
    venv_path: Path  # Resolved virtual environment path
    python_binary: Path  # Resolved Python executable
    oarepo_version: int  # Resolved OARepo version

    # Computed properties
    @property
    def code_directories(self) -> list[Path]: ...
    @property
    def instance_path(self) -> Optional[Path]: ...
    @property
    def assets_path(self) -> Optional[Path]: ...


class ContextBuilder:
    """Fluent builder for constructing ProjectContext with validation."""

    def from_cwd(self) -> "ContextBuilder": ...
    def with_python_override(self, path: Path) -> "ContextBuilder": ...
    def with_oarepo_version(self, version: int) -> "ContextBuilder": ...
    def validate(self) -> ProjectContext: ...
```

**Dependencies**: `pyproject_reader`, `version_resolver` (both use `pathlib.Path` directly for filesystem access)

**Testing**: Unit tests using `tmp_path` with real synthetic pyproject.toml fixtures

---

### 4.2 Process Execution Helper (`services/process.py`)

**Responsibility**: Run subprocesses safely and consistently — never `shell=True`, UTF-8 output, timeout handling, env-dict merging. Plain module-level functions, called directly by every service; no protocol, no constructor injection, since there is exactly one real implementation.

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Sequence


@dataclass
class ProcessResult:
    """Result of a subprocess execution."""

    returncode: int
    stdout: str
    stderr: str
    command: Sequence[str]
    duration_ms: int


def run(
    command: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
    capture_output: bool = True,
    check: bool = True,
    forward_stdout: bool = False,
    timeout: Optional[float] = None,
) -> ProcessResult:
    """Execute a command and wait for completion. Never uses shell=True."""
    ...


def stream(
    command: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
) -> Iterator[str]:
    """Execute a command and yield output lines as they're produced."""
    ...


def get_output(
    command: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
) -> str:
    """Execute a command and return stripped stdout."""
    ...
```

**Dependencies**: None (pure stdlib)

**Testing**: Direct calls to `run()`/`stream()`/`get_output()` against trivial, always-available real commands (`echo`, `true`, `false`, `python3 -c`) verify exit code propagation, output capture, and environment isolation — no fixture or fake needed. Higher up the stack, services that shell out to slow/optional tools (`uv`, `docker-services-cli`, `copier`) are exercised for real in integration tests, not through a faked `subprocess.Popen` boundary.

---

### 4.3 Version Resolver (`services/version_resolver.py`)

**Responsibility**: Determine compatible Python and OARepo versions from pyproject.toml and system availability.

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class VersionInfo:
    oarepo_versions: list[int]
    python_versions: list[str]  # e.g., ["3.12", "3.13"]
    node_versions: list[int]


class VersionResolver(Protocol):
    def resolve_from_pyproject(self, pyproject_path: Path) -> VersionInfo: ...
    def find_available_python(self, versions: list[str]) -> str: ...  # Highest available
    def validate_compatibility(self, python: str, oarepo: int) -> None: ...
```

**Dependencies**: `pyproject_reader`, `services/process.py` (calls `run()`/`get_output()` directly to check python binaries — no injected executor)

**Testing**: Pure unit tests with synthetic TOML inputs

---

### 4.4 Virtual Environment Manager (`services/venv.py`)

**Responsibility**: Create, activate, and manage Python virtual environments via uv.

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class VenvConfig:
    python_binary: str
    extras: list[str]
    editable: bool = True
    oarepo_version: Optional[int] = None


class VirtualEnvironmentManager:
    def ensure_venv(self, config: VenvConfig, force: bool = False) -> Path: ...
    def upgrade_environment(self) -> None: ...
    def cleanup(self) -> None: ...
    def get_site_packages(self) -> Path: ...
```

**Dependencies**: `services/process.py`, `version_resolver` (calls `process.run()` directly — no injected executor; uses `pathlib.Path` directly for filesystem access)

**Testing**: Integration tests against the real `tests/testlib/` fixture project, with `project_root` passed explicitly so every `uv`/`pip` invocation is absolute-path/`cwd`-independent (see `tests/integration/test_venv_workflow.py`)

---

### 4.5 PyProject Reader (`services/pyproject_reader.py`)

**Responsibility**: Parse pyproject.toml using `tomllib` with typed accessors.

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PyProjectModel:
    name: str
    homepage: str
    requires_python: str
    oarepo_dependencies: dict[str, str]  # {version_range: constraint}
    default_extras: list[str]
    custom_sections: dict[str, Any]


class PyProjectReader:
    def read(self, path: Path) -> PyProjectModel: ...
    def get_package_name(self, path: Path) -> str: ...
    def get_oarepo_versions(self, path: Path) -> list[int]: ...
    def get_python_constraint(self, path: Path) -> str: ...
```

**Dependencies**: `tomllib` (stdlib), `pathlib`

**Testing**: Unit tests with fixture TOML files covering edge cases

---

## 5. Error Hierarchy

```python
# core/errors.py


class OARepoError(Exception):
    """Base exception for all oarepo-cli errors."""

    exit_code: int = 1


class ConfigurationError(OARepoError):
    """Invalid or missing configuration (pyproject.toml, env vars)."""

    exit_code = 2


class VersionMismatchError(ConfigurationError):
    """Incompatible Python or OARepo version."""

    exit_code = 3


class ProcessExecutionError(OARepoError):
    """External command failed."""

    def __init__(self, command: list[str], returncode: int, stdout: str, stderr: str): ...

    exit_code = 4


class FileNotFoundError(OARepoError):
    """Required file or directory missing."""

    exit_code = 5


class ValidationError(OARepoError):
    """User input failed validation."""

    exit_code = 6


class LockAcquisitionError(OARepoError):
    """Could not acquire operation lock (concurrent execution)."""

    exit_code = 7
```

---

## 6. Configuration Model

```python
# core/config.py

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class BuildConfig:
    editable: bool = True


@dataclass
class TestConfig:
    coverage: bool = False
    skip_services: bool = False


@dataclass
class VenvConfig:
    path: Path = Path(".venv")


@dataclass
class PythonConfig:
    binary: Optional[str] = None  # None = auto-detect


@dataclass
class OARepoConfig:
    version: Optional[int] = None  # None = first from pyproject.toml


@dataclass
class ServicesConfig:
    skip: bool = False
    db: str = "postgresql"
    search: str = "opensearch"
    mq: str = "rabbitmq"
    cache: str = "redis"
    s3: str = "minio"


@dataclass
class ModelConfig:
    template_url: str = "https://github.com/oarepo/nrp-model-copier"
    template_version: str = "rdm-14"


@dataclass
class TranslationsConfig:
    overlay_dir: Optional[Path] = None


@dataclass
class CeleryConfig:
    pool_type: str = "threads"  # macOS workaround
    concurrency: int = 10


@dataclass
class LicenseConfig:
    organization: str = "CESNET z.s.p.o"


@dataclass
class SecurityConfig:
    demo_user_password: str = "123456"  # Warn if not changed


@dataclass
class CliConfig:
    build: BuildConfig
    test: TestConfig
    venv: VenvConfig
    python: PythonConfig
    oarepo: OARepoConfig
    services: ServicesConfig
    model: ModelConfig
    translations: TranslationsConfig
    celery: CeleryConfig
    license: LicenseConfig
    security: SecurityConfig

    @classmethod
    def from_env_and_files(cls, root: Path) -> "CliConfig": ...
```

---

## 7. Command Execution Result Model

```python
# core/result.py

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar


class CommandStatus(Enum):
    SUCCESS = 0
    FAILURE = 1
    PARTIAL = 2  # Some steps succeeded, others failed (rollback attempted)
    CANCELLED = 3  # User interrupted


T = TypeVar("T")


@dataclass
class CommandResult(Generic[T]):
    status: CommandStatus
    exit_code: int
    message: str
    output: T | None = None
    warnings: list[str] = None
    errors: list[str] = None

    def is_success(self) -> bool: ...
    def raise_on_failure(self) -> None: ...  # Raises OARepoError on failure
```

---

## 8. Architecture Decision Records

### ADR-001: CLI Framework Selection

**Status**: Accepted
**Date**: 2026-08-01

**Context**: Need a CLI framework that supports nested subcommands, typed options, and matches the existing shell script UX.

**Decision**: Typer with Pydantic v2

**Consequences**:
- Pros: Type safety, auto-help, minimal boilerplate
- Cons: New dependency (but already used in OARepo ecosystem via ruff/uv)

---

### ADR-002: Single vs Multiple Executables

**Status**: Accepted
**Date**: 2026-08-01

**Context**: Should library and repository runners be separate executables?

**Decision**: Single `oarepo-cli` with subcommand groups

**Consequences**:
- Shared configuration reduces duplication
- Easier to implement cross-cutting concerns
- Users may initially expect separate commands (document clearly)

---

### ADR-003: Self-Update Mechanism

**Status**: Rejected for Python implementation
**Date**: 2026-08-01

**Context**: Shell scripts self-update by downloading from GitHub. Should Python version do the same?

**Decision**: **Do not implement** self-update in the Python CLI.

**Rationale**:
- Incompatible with Python package distribution model (pip/PyPI)
- Security concerns with downloading and executing remote scripts
- Unnecessary complexity when `pip install --upgrade` provides the same functionality
- Maintains clear separation: shell scripts use shell updates, Python uses pip

**Consequences**:
- Users must use `pip install --upgrade oarepo-cli` for updates
- Shell scripts retain their `self-update` command during transition period
- No deprecation warning needed; simply omit the command
- Clear migration path documented in user guide

---

### ADR-004: Environment Mutation

**Status**: Accepted
**Date**: 2026-08-01

**Context**: Shell scripts export many environment variables that persist across commands.

**Decision**: Do NOT mutate parent shell environment. Instead:
- Write `.env-services` files as before (compatibility)
- Source them explicitly within subprocess invocations
- Document that `eval "$(oarepo-cli ...)"` is not supported

**Consequences**:
- Cleaner, more predictable behavior
- Breaking change for users relying on exported vars (document migration)

---

### ADR-005: Subprocess Execution Safety

**Status**: Accepted
**Date**: 2026-08-01

**Context**: Shell scripts use string interpolation in subprocess calls, creating injection risks.

**Decision**: Never use `shell=True`. Always pass arguments as lists.

**Implementation**:
- `process.run(["uv", "pip", "install", pkg])` not `run(f"uv pip install {pkg}")`
- Validate and sanitize any user-provided strings before inclusion

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Behavioral differences from shell scripts | Medium | High | Extensive characterization tests |
| Performance regression (Python startup) | Low | Low | Benchmark critical paths |
| Missing edge cases in TOML parsing | Medium | Medium | Fuzz testing with malformed TOML |
| Concurrent execution corruption | Low | High | File-based locking for venv ops |
| Secrets in logs (passwords, tokens) | Medium | High | Redaction middleware, warn about DEMO_USER_PASSWORD |
| Platform-specific bugs (macOS vs Linux) | Medium | Medium | CI on both platforms, platform abstraction |
| Breaking changes in uv API | Low | Medium | Pin uv version, monitor upstream |

---

## 10. Implementation Roadmap

Development proceeds through 8 phases, from project scaffolding to release, worked in order with no fixed schedule.

**See:** [implementation-steps.md](./implementation-steps.md) for the full phase-by-phase, test-driven checklist and deliverables.

---

## 11. Migration Guide

User-facing migration from shell scripts to `oarepo-cli` (command mapping, environment variables, breaking changes, deprecation timeline) is covered separately.

**See:** [03-migration-guide.md](./03-migration-guide.md) for complete migration instructions.

---

## 12. Open Questions

1. **Should we support Windows?** Current scripts target Linux/macOS. Adding Windows would require significant effort (WSL recommendation?).

2. **What's the minimum Python version?** Shell scripts use Python 3.14. Should Python CLI require 3.11+ (for tomllib) or support older?

3. **Configuration file format?** Beyond env vars and pyproject.toml, should we support `~/.config/oarepo/config.yaml`?

4. **Plugin system for custom commands?** Future extensibility vs complexity tradeoff.

5. **Telemetry?** Should we collect anonymous usage metrics (opt-in)?

---

## Appendix A: Glossary

- **OARepo**: The overarching repository platform
- **Library**: A Python package that integrates with OARepo (e.g., `oarepo-oaipmh-harvester`)
- **Repository**: A deployed Invenio RDM instance built from a template
- **Runner**: The shell script or Python CLI that orchestrates development workflows
- **Venv**: Python virtual environment
- **Copier**: Template engine used for scaffolding repositories and models
