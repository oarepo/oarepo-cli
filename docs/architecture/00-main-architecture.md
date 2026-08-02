# OARepo CLI Python Implementation Architecture

## Executive Summary

This document describes the architecture for replacing the existing OARepo shell-script runners (`library_runner.sh`, `repository_installer.sh`, `repository_runner.sh`) with a robust, maintainable Python command-line application called `oarepo-cli`.

The new implementation preserves all existing user-facing behavior while replacing shell-specific parsing, global state, command dispatch, environment mutation, and process orchestration with explicit Python abstractions.

---

## 1. Feature Inventory & Compatibility Matrix

### 1.1 Library Runner Commands

| Command | Options | Description | Status |
|---------|---------|-------------|--------|
| `venv` | `--force`, `--no-editable` | Set up virtual environment (uses `uv sync` for lockfile-based installs) | Must preserve |
| `upgrade` | - | Clean cache and recreate venv | Must preserve |
| `start` | - | Start services for testing | Must preserve |
| `stop` | - | Stop services after testing | Must preserve |
| `test` | `--skip-services`, `--with-coverage` | Run pytest tests | Must preserve |
| `oarepo-versions` | - | List supported OARepo versions (JSON output) | **Diverges from bash** (see §1.1.2) |
| `clean` | - | Stop services, remove venv | Must preserve |
| `shell` | `--skip-services` | Start bash shell in venv | Must preserve |
| `invenio` | `--skip-services` | Run Invenio commands | Must preserve |
| `translations` | - | Extract/compile translations via oarepo-tools | Must preserve |
| `lint` | `--fix`/`--no-fix` (default `--fix`) | Run ruff, `ty`, license checks — auto-fixes ruff/ty-fixable issues by default (see §1.1.1) | **Diverges from bash** (see §1.1.1) |
| `format` | `--fix`/`--no-fix` (default `--fix`) | Format code with ruff — `--no-fix` is a non-writing preview mode (see §1.1.1) | **Diverges from bash** (see §1.1.1) |
| `check` | - | Read-only equivalent of `lint`+`format` that never modifies target project files; see §1.1.1 | **New, not in original bash scripts** |
| `license-headers` | - | Add MIT license headers | Must preserve |
| `jslint` | - | Run ESLint and Prettier | Must preserve |
| `jstest` | `setup`, `--skip-services` | Run JavaScript tests (Jest) | Must preserve |
| `self-update` | - | Download latest runner script | **Not implemented** (deprecated, use `pip install --upgrade oarepo-cli`) |
| `--no-editable` | (global flag) | Build wheel instead of editable install | Must preserve |

#### 1.1.1 Intentional divergence: `lint`/`format` fix by default, new `check` command

**Implemented in Step 3.10.2** — see [implementation-steps.md Step
3.10.2](./implementation-steps.md).

The original bash `run_linters()`/`format_code()` never had a "preview
only" mode: `lint` only ever reported problems, `format` always rewrote
files. This is a **deliberate departure** from that behavior, not a bug —
requested explicitly, not derived from the bash scripts:

- `library lint` has a `--fix`/`--no-fix` option, **defaulting to
  `--fix`**: it runs `ruff check --fix` and `ty check --fix` (auto-fixing
  what ruff and ty can) instead of bare `ruff check` and `ty check`. The
  license header check and future-annotations check remain read-only either
  way (fixing those is `license-headers`' job, not `lint`'s).
- `library format` has the same `--fix`/`--no-fix` option, **defaulting
  to `--fix`** (i.e. unchanged from the original always-rewrites behavior).
  `--no-fix` turns it into a preview: `ruff format --check` instead of
  `ruff format`, without applying `ruff check --fix`.
- A new `library check` command is available: the non-destructive combination
  of what `lint`/`format` check — `ruff format --check`, `ruff check`
  (no `--fix`), license header check, future annotations check, `ty check`
  (no `--fix`). Functionally, this is the original bash `library lint`
  behavior, kept available as its own named command now that `lint` itself
  fixes by default. Intended as the safe-for-CI entry point (never
  modifies target project files, only generates `.ruff.toml`/`ty.toml`,
  same as `lint`/`format` already do).

#### 1.1.2 Intentional divergence: `oarepo-versions` extracts from dependency constraints

**To be implemented in Step 3.13** — see [implementation-steps.md Step
3.13](./implementation-steps.md).

The original bash script extracted OARepo versions by scanning
`pyproject.toml` for keys like `oarepo14`, `oarepo13` in
`[project.optional-dependencies]`, supporting multiple versions:

```bash
egrep "^oarepo[0-9]{2}\\s*=" pyproject.toml
```

The initial Python CLI implementation (Step 3.12) replaced this with a
`[tool.oarepo-cli].version` configuration key. **Step 3.13 refactors this
approach** to instead extract version information directly from dependency
constraints in `[project.dependencies]` or `[project.optional-dependencies]`,
eliminating the need for separate configuration.

**Old bash approach** (scanned optional-dependencies keys):
```toml
[project.optional-dependencies]
oarepo14 = ["oarepo>=14.0.0,<15.0.0"]
oarepo13 = ["oarepo>=13.0.0,<14.0.0"]
```

**Step 3.12 approach** (explicit configuration, now deprecated):
```toml
[tool.oarepo-cli]
version = 14
```

**New Step 3.13 approach** (extracted from standard dependency declarations):
```toml
[project.dependencies]
oarepo = ">=14.0.0,<15.0.0"

# OR in optional dependencies:
[project.optional-dependencies]
dev = ["oarepo>=14.0.0,<15.0.0"]
tests = ["oarepo>=13.0.0,<14.0.0"]  # multi-version support
```

**Rationale:**
- **Single source of truth**: Version information lives where it already must
  be declared (in dependency specs), not duplicated in a tool-specific config
- **Standard Python packaging**: Aligns with PEP 621 and how all other tools
  (pip, uv, poetry) already consume version constraints
- **Multi-version support restored**: Unlike the Step 3.12 single-version
  config, this approach can detect multiple oarepo versions across different
  extras (e.g., dev with v14, tests with v13) and return them highest-first
- **Zero configuration**: Projects following standard packaging conventions
  work out-of-the-box without any `[tool.oarepo-cli]` section
- **Less opinionated**: The CLI doesn't dictate a specific configuration
  structure beyond standard dependencies

**Multi-version selection behavior:**

When multiple OARepo versions are detected (e.g., different versions in `dev`
and `tests` extras), the CLI selects the **highest version** for commands that
need a single version (`venv`, `install`, `test`, etc.).

For the example above with versions 14 and 13:
- `oarepo-cli library oarepo-versions` → Returns `["14", "13"]` (both versions)
- `oarepo-cli library venv` → Uses version `14` (highest)

**Override with environment variable:**

To use a different version, set the `OAREPO_VERSION` environment variable:
```bash
OAREPO_VERSION=13 oarepo-cli library venv
```

This is useful for testing against older OARepo versions or when you need
explicit control over which version to use.

The JSON output format returns all detected major versions, sorted
highest-first:
```json
{
  "oarepo_versions": [14, 13],
  "python_versions": ["3.14"],
  "node_versions": ["24"]
}
```

For projects with a single oarepo dependency, the behavior is identical to
Step 3.12 (single-element list). Projects with multiple versions in different
extras now get all versions reported, restoring the bash script's capability.

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
| `ruff` | Linting/formatting | Yes (bundled dependency, not shelled out to via `uvx`) |
| `ty` | Type checking | Yes (bundled dependency, not shelled out to via `uvx`) |
| `npm` / `pnpm` | JavaScript dependencies | Optional |
| `jest` | JavaScript testing | Optional |
| `curl` | Self-update download | Yes |
| `openssl` | Certificate generation | Yes |
| `git` | Repo initialization | Optional |
| `invenio-cli` | Repository install/run passthrough | Yes (CESNET-patched build required — see [ADR-006](#adr-006-cesnet-patched-invenio-cli-dependency)) |

`library lint`'s type checking uses `ty` alone (the same tool already used
for oarepo-cli's own type checking) rather than `mypy` + `pyright` — see
[implementation-steps.md Step 3.9.1](./implementation-steps.md) for the
mapping from the old mypy/pyright configuration to `ty`'s.

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

**Responsibility**: Create, activate, and manage Python virtual environments via uv. For library development, uses `uv sync` to install dependencies from a lockfile (`uv.lock`), which provides reproducible builds. The lockfile is generated automatically but should be gitignored for libraries (repositories commit their lockfiles).

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

### ADR-006: CESNET-patched invenio-cli dependency

**Status**: Accepted
**Date**: 2026-08-02

**Context**: oarepo-cli's repository install/run/services flows shell out to
`invenio-cli`. CESNET carries patches on top of upstream `invenio-cli`
(docker-environment/compose file discovery, `.env` linking, extension
entry-point hooks, custom cert/key paths, `UV_PROJECT_ENVIRONMENT` support,
OARepo-aware RDM version detection — see
[oarepo/invenio-cli@oarepo-feature-docker-environment](https://github.com/oarepo/invenio-cli))
that are required for oarepo-cli to work correctly but are not part of the
upstream PyPI release. Because the patched build's base version (e.g.
`1.12.0`) still overlaps with the public PyPI release, a plain version
range in `pyproject.toml` cannot by itself guarantee the right build is
installed — a `pip install`/resolver pass that skips the CESNET index would
silently install the upstream build instead.

**Decision**: Two complementary mechanisms:
1. **Resolution**: `pyproject.toml` declares a `[[tool.uv.index]]` named
   `cesnet` pointing at the CESNET GitLab PyPI registry
   (`CESNET_PYPI_INDEX_URL` in `configuration/constants.py`) and scopes
   `invenio-cli` to it via `[tool.uv.sources]`, so `uv sync`/`uv lock`
   always resolve `invenio-cli` from CESNET rather than PyPI.
2. **Verification**: The patched build publishes a PEP 440 local version
   segment starting with `oarepo` (e.g. `1.12.0+oarepo.1.cgeloxoaidcutj32`).
   `core/dependency_check.py:check_invenio_cli_version()` inspects the
   installed `invenio-cli` version via `importlib.metadata` at CLI startup
   (`cli/main.py:cli_main()`, before dispatching to Typer) and raises
   `VersionMismatchError` with a message pointing at the CESNET registry if
   that local segment is missing — covering environments where the venv was
   built without the CESNET index (manual `pip install`, stale lock file,
   etc.).

**Consequences**:
- Pros: Fails fast with an actionable message instead of obscure downstream
  failures in docker/services commands; works even if the dependency was
  installed by a tool other than `uv`.
- Cons: Adds a network dependency on the CESNET registry for `uv
  lock`/`uv sync`; the check must be updated if the local-version naming
  scheme changes.

---

### ADR-007: Fast instance path resolution (no `invenio shell`)

**Status**: Accepted
**Date**: 2026-08-02

**Context**: `repository install` needs the Invenio instance path (where
`invenio.cfg` gets symlinked and where `var/`, `assets/`, etc. live) to set
up the instance directory. `repository_runner.sh` gets this by piping
`print(app.instance_path, end='')` through `in_invenio_shell` — booting the
full Flask application just to read one attribute. `services/repository.py`'s
`get_instance_path()` originally replicated that exactly via
`invenio_cli.run_invenio_shell()` (`uv run invenio shell -c ...`), which was
slow (full app boot, `uv run`'s own implicit sync) and was also the root
cause of two follow-on bugs: streamed diagnostic output crashing the parser
when `stdout` wasn't captured, and `uv sync`/`uv run` disagreeing on
pre-release mode and forcing lockfile re-resolution (see the `invenio_cli.py`
git history around 2026-08-02 for both).

**Decision**: Compute the instance path directly instead of asking Invenio
for it. Invenio's own default instance path is `sys.prefix/var/instance`,
which for a project's venv resolves to `<venv>/var/instance`; the
`INVENIO_INSTANCE_PATH` environment variable, when set, overrides it. Both
rules are Invenio's own (not oarepo-cli-specific), so replicating them in
`get_instance_path()` (`services/repository.py`) is exact, not a heuristic:

```python
instance_path = os.environ.get("INVENIO_INSTANCE_PATH")
if instance_path:
    return Path(instance_path)
return context.venv_path / "var" / "instance"
```

This made `run_invenio_shell()` (`services/invenio_cli.py`) dead code —
`get_instance_path()` was its only caller — so it was removed.

**Consequences**:
- Pros: No subprocess/app boot on every `install`; removes an entire class
  of bugs tied to parsing subprocess output for this value.
- Cons: If a project ever customizes `app.instance_path` through a
  mechanism other than `INVENIO_INSTANCE_PATH` (e.g. a custom
  `create_app()` that hardcodes a different path), this would silently
  compute the wrong path instead of asking the app directly. Not currently
  the case for OARepo/RDM projects.

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
