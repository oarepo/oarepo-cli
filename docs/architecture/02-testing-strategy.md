# OARepo CLI Testing Strategy

## 1. Overview

This document defines the comprehensive testing strategy for the OARepo CLI Python implementation. The goal is to achieve high confidence in behavioral compatibility with the existing shell scripts while ensuring maintainability and reliability of the new codebase.

### Testing Principles

1. **Test behavior, not implementation**: Focus on observable outcomes (exit codes, output, file system changes)
2. **Isolate external dependencies**: Mock subprocess and network; filesystem code is tested against a real (temporary) filesystem via `tmp_path`, not mocked
3. **Layered approach**: Unit tests → Contract tests → Integration tests → Characterization tests
4. **Fast feedback**: Most tests should run in seconds without Docker or network access
5. **Deterministic**: Tests must produce consistent results across platforms and environments

---

## 2. Test Pyramid

```
                        ┌─────────────────┐
                        │ Characterization│
                        │ (Bash vs Python)│
                       ┌┴─────────────────┴┐
                      │   Integration Tests │
                     ├───────────────────────┤
                    │    Workflow Tests      │
                   ├─────────────────────────┤
                  │     Contract Tests        │
                 ├─────────────────────────────┤
                │        Unit Tests            │
               └────────────────────────────────┘
              (Most numerous, fastest, cheapest)
```

### Test Distribution Target

| Test Type | Count Target | Avg Runtime | Coverage Goal |
|-----------|--------------|-------------|---------------|
| Unit Tests | 200+ | <1s each | 90%+ lines |
| Contract Tests | 0 (reserved) | <5s each | Only protocols with 2+ real implementations (currently none) |
| Workflow Tests | 50+ | <10s each | All workflows |
| Integration Tests | 20+ | <60s each | Critical paths |
| Characterization Tests | 40+ | <30s each | Command parity |

---

## 3. Unit Tests

### Scope

Pure unit tests for logic that doesn't require external tools. Filesystem-touching cases (e.g. TOML parsing) use `tmp_path` for fast, deterministic access to a real filesystem — no mocking involved.

### Covered Components

- TOML parsing (`pyproject_reader.py`)
- Version resolution logic (`version_resolver.py`)
- Configuration model validation (`config.py`)
- Context discovery algorithms (`context.py`)
- Platform detection utilities (`platform.py`)
- Error message formatting (`errors.py`)
- Process execution (`process.py`) — plain functions, tested directly against real trivial commands, no fixture or fake

### Example: PyProjectReader and VersionResolver Tests

```python
# tests/unit/test_pyproject_reader.py
"""Unit tests for pyproject.toml parsing."""

import pytest
from pathlib import Path
from oarepo_cli.services.pyproject_reader import (
    PyProjectReader,
    PyProjectData,
    ConfigurationError,
)


def test_parse_minimal_project(tmp_path: Path):
    """Parse basic project metadata."""
    toml_content = """
[project]
name = "test-package"
requires-python = ">=3.12,<3.15"
"""
    (tmp_path / "pyproject.toml").write_text(toml_content)
    reader = PyProjectReader()
    data = reader.read(tmp_path / "pyproject.toml")

    assert data.name == "test-package"
    assert data.requires_python == ">=3.12,<3.15"


def test_extract_oarepo_versions_single(tmp_path: Path):
    """Extract single OARepo version from optional dependencies."""
    toml_content = """
[project.optional-dependencies]
oarepo = ["oarepo14>=14.0.0,<15.0.0"]
"""
    (tmp_path / "pyproject.toml").write_text(toml_content)
    reader = PyProjectReader()
    data = reader.read(tmp_path / "pyproject.toml")

    assert data.oarepo_versions == [14]


def test_extract_oarepo_versions_multiple(tmp_path: Path):
    """Extract multiple OARepo versions."""
    toml_content = """
[project.optional-dependencies]
oarepo = [
    "oarepo13>=13.0.0,<14.0.0",
    "oarepo14>=14.0.0,<15.0.0",
]
"""
    (tmp_path / "pyproject.toml").write_text(toml_content)
    reader = PyProjectReader()
    data = reader.read(tmp_path / "pyproject.toml")

    assert data.oarepo_versions == [13, 14]


def test_missing_pyproject_raises_error(tmp_path: Path):
    """ConfigurationError when pyproject.toml not found."""
    reader = PyProjectReader()

    with pytest.raises(ConfigurationError) as exc_info:
        reader.read(tmp_path / "nonexistent.toml")

    assert "not found" in str(exc_info.value)


def test_invalid_toml_raises_error(tmp_path: Path):
    """ConfigurationError for malformed TOML."""
    (tmp_path / "pyproject.toml").write_text("invalid [[[[ syntax")
    reader = PyProjectReader()

    with pytest.raises(ConfigurationError) as exc_info:
        reader.read(tmp_path / "pyproject.toml")

    assert "Invalid TOML" in str(exc_info.value)


def test_get_default_extras(tmp_path: Path):
    """Parse default_extras from tool.oarepo section."""
    toml_content = """
[tool.oarepo]
default_extras = ["dev", "tests"]
"""
    (tmp_path / "pyproject.toml").write_text(toml_content)
    reader = PyProjectReader()
    data = reader.read(tmp_path / "pyproject.toml")

    assert data.default_extras == ["dev", "tests"]


@pytest.mark.parametrize(
    "constraint,expected",
    [
        (">=3.12,<3.15", ("3.12", "3.13", "3.14")),
        (">=3.13,<3.14", ("3.13",)),
        (">=3.12", None),  # No upper bound
    ],
)
def test_parse_python_constraint(constraint, expected, tmp_path: Path):
    """Parse Python version constraints into discrete versions."""
    toml_content = f"""
[project]
name = "test"
requires-python = "{constraint}"
"""
    (tmp_path / "pyproject.toml").write_text(toml_content)
    reader = PyProjectReader()
    data = reader.read(tmp_path / "pyproject.toml")

    if expected is None:
        with pytest.raises(ConfigurationError):
            data.python_version_range
    else:
        assert data.python_version_range == expected
```

`VersionResolver` calls `process.run()`/`process.get_output()` directly (no injected executor). For the two tests below that need to fake which Python binaries exist on `PATH`, use the `fake_process` fixture from `pytest-subprocess`, which patches `subprocess.Popen` for the duration of the test — no DI required.

```python
# tests/unit/test_version_resolver.py
"""Unit tests for version resolution logic."""

import pytest
from oarepo_cli.services.version_resolver import VersionResolver, VersionMismatchError


def test_find_highest_available_python(fake_process):
    """Select highest Python version that exists on system."""
    # Simulate system with Python 3.12 and 3.14 on PATH
    fake_process.register(["which", "python3.12"], stdout="/usr/bin/python3.12")
    fake_process.register(["which", "python3.13"], returncode=1)
    fake_process.register(["which", "python3.14"], stdout="/usr/bin/python3.14")
    resolver = VersionResolver()

    available = resolver.find_available_python(["3.12", "3.13", "3.14"])
    assert available == "3.14"


def test_fallback_to_lower_version(fake_process):
    """Use lower version if highest not available."""
    fake_process.register(["which", "python3.12"], stdout="/usr/bin/python3.12")
    fake_process.register(["which", "python3.13"], returncode=1)
    fake_process.register(["which", "python3.14"], returncode=1)
    resolver = VersionResolver()

    available = resolver.find_available_python(["3.13", "3.14"])
    assert available == "3.12"


def test_no_compatible_version_raises_error(fake_process):
    """VersionMismatchError when no Python version available."""
    fake_process.register(["which", "python3.14"], returncode=1)
    fake_process.register(["which", "python3.15"], returncode=1)
    resolver = VersionResolver()

    with pytest.raises(VersionMismatchError):
        resolver.find_available_python(["3.14", "3.15"])


def test_validate_oarepo_python_compatibility():
    """Check that Python version supports OARepo version — pure logic, no subprocess involved."""
    resolver = VersionResolver()

    # Python 3.14 required for OARepo 14
    resolver.validate_compatibility("3.14", 14)  # Should pass

    with pytest.raises(VersionMismatchError):
        resolver.validate_compatibility("3.12", 14)  # Too old
```

### Example: Process Execution Tests

`process.run()` is a plain function — call it directly with real, trivial, always-available commands. No fixture, no fake, no DI.

```python
# tests/unit/test_process.py

import pytest
from pathlib import Path
from oarepo_cli.services import process
from oarepo_cli.services.process import ProcessExecutionError
from oarepo_cli.core.errors import TimeoutExceeded


def test_returns_zero_exit_code_for_success():
    result = process.run(["echo", "hello"], check=False)
    assert result.returncode == 0


def test_captures_stdout_correctly():
    result = process.run(["echo", "test output"], check=False)
    assert "test output" in result.stdout


def test_captures_stderr_correctly():
    result = process.run(
        ["python3", "-c", "import sys; print('error', file=sys.stderr)"],
        check=False,
    )
    assert "error" in result.stderr


def test_raises_on_nonzero_with_check_true():
    with pytest.raises(ProcessExecutionError):
        process.run(["python3", "-c", "import sys; sys.exit(42)"], check=True)


def test_does_not_raise_on_nonzero_with_check_false():
    result = process.run(
        ["python3", "-c", "import sys; sys.exit(42)"],
        check=False,
    )
    assert result.returncode == 42


def test_environment_variables_passed_correctly():
    result = process.run(
        ["python3", "-c", "import os; print(os.environ.get('TEST_VAR'))"],
        env={"TEST_VAR": "test_value"},
        check=False,
    )
    assert result.stdout.strip() == "test_value"


def test_cwd_parameter_sets_working_directory(tmp_path: Path):
    (tmp_path / "test.txt").write_text("content")

    result = process.run(["cat", "test.txt"], cwd=tmp_path, check=False)
    assert "content" in result.stdout


def test_shell_injection_prevented():
    """Ensure arguments are not interpreted as shell commands."""
    result = process.run(["echo", "; rm -rf / ;"], check=False)
    # Output should be the literal string, not an executed command
    assert "; rm -rf / ;" in result.stdout


def test_timeout_raises_exception():
    with pytest.raises(TimeoutExceeded):
        process.run(["sleep", "100"], timeout=0.1)


def test_get_output_returns_stripped_stdout():
    assert process.get_output(["echo", "hello world"]) == "hello world"


def test_stream_yields_lines():
    lines = list(process.stream(["python3", "-c", "print('line1'); print('line2')"]))
    assert lines == ["line1", "line2"]
```

### Faking Subprocess Calls with `pytest-subprocess`

Services that shell out to slow, optional, side-effecting external tools (`uv`, `docker-services-cli`, `copier`, `invenio-cli`) are tested by faking those tools at the OS boundary, not by injecting a hand-written test double. A hand-registered fake class has no independent behavior of its own to verify or maintain — it only returns whatever a test tells it to — so writing and maintaining one from scratch (command matching, call logging, reset semantics, and a way to fall through to a real subprocess for anything unregistered) is effort spent reinventing what a maintained library already does correctly.

[`pytest-subprocess`](https://pytest-subprocess.readthedocs.io/) provides this via its `fake_process` fixture. It patches `subprocess.Popen` (and everything built on it — `subprocess.run`, our own `process.run()`/`stream()`/`get_output()`) for the duration of a test, so it intercepts calls transparently — no injected executor, no constructor parameter, no service needs to know it's under test:

```python
def test_creates_venv_if_missing(fake_process, tmp_path):
    fake_process.register(
        ["uv", "venv", "--python", "python3.14", "--seed", fspath(tmp_path / ".venv")]
    )
    fake_process.register(
        [fspath(tmp_path / ".venv/bin/python"), "-m", "pip", "install", "setuptools"]
    )
    fake_process.register(["uv", "pip", "install", fake_process.any()])

    manager = VirtualEnvironmentManager(config=make_config(venv_path=tmp_path / ".venv"))
    manager.ensure_venv(VenvRequirements(python_binary="python3.14"))

    # fake_process.calls records every intercepted command, in order, for assertions
    assert any("venv" in call for call in fake_process.calls)
```

Unregistered commands raise a clear error by default — no silent success, no silent fallback to a real subprocess.

---

## 4. Contract Tests

### Purpose

Verify that multiple *real* implementations of the same protocol behave identically. This tier only earns its place when a protocol genuinely has (or will have) more than one concrete backend to keep in sync — most of this codebase's boundaries (filesystem, environment variables, subprocess execution) have exactly one real implementation each, so they're called directly (`pathlib`, `os.environ`, `subprocess`) and tested directly instead — see §3 (Unit Tests) for `process.py`'s tests against real trivial commands, and `tmp_path`/`monkeypatch` for filesystem/environment code.

`NetworkClient` is the one protocol in this codebase that could genuinely justify a contract suite (e.g. if both a `requests`- and `httpx`-backed adapter exist); add its contract tests here if and when that happens. Until then, this tier is intentionally empty rather than populated with a suite that has nothing to verify.

---

## 5. Workflow Tests

### Purpose

Test complete business workflows without requiring real external tools — `uv`, `docker-services-cli`, `copier`, `pytest`, etc. are faked at the OS boundary via `pytest-subprocess`'s `fake_process` fixture (see §3), not through an injected executor.

### Example: Virtual Environment Setup Workflow

```python
# tests/workflow/test_venv_workflow.py

import pytest
from pathlib import Path
from oarepo_cli.services.venv import VirtualEnvironmentManager, VenvRequirements
from oarepo_cli.services.config import CliConfig


@pytest.fixture
def setup_manager(tmp_path: Path, fake_process):
    """Set up a venv creation workflow with uv/pip faked via pytest-subprocess."""
    (tmp_path / "pyproject.toml").write_text("""
[project]
name = "test-package"
requires-python = ">=3.12,<3.15"

[project.optional-dependencies]
oarepo = ["oarepo14>=14.0.0,<15.0.0"]
dev = ["ruff", "mypy"]
tests = ["pytest"]
""")

    fake_process.register(
        ["uv", "venv", "--python", "python3.14", "--seed", str(tmp_path / ".venv")]
    )
    fake_process.register(
        [str(tmp_path / ".venv/bin/python"), "-m", "pip", "install", "setuptools"]
    )
    fake_process.register(["uv", "pip", "install", "oarepo[rdm,tests]>=14.0.0,<15.0.0"])
    fake_process.register(["uv", "pip", "install", "-e", ".[dev,tests,oarepo14]"])

    config = CliConfig.default()
    config.venv.path = tmp_path / ".venv"

    manager = VirtualEnvironmentManager(config)
    return manager, fake_process


def test_creates_venv_if_missing(setup_manager):
    manager, fake_process = setup_manager

    manager.ensure_venv(VenvRequirements(python_binary="python3.14"))

    # fake_process.calls records every intercepted command, in order
    assert any("venv" in call for call in fake_process.calls)


def test_installs_setuptools_first(setup_manager):
    manager, fake_process = setup_manager

    manager.ensure_venv(VenvRequirements(python_binary="python3.14"))

    # setuptools should be the first pip install
    pip_calls = [call for call in fake_process.calls if "pip" in call]
    assert "setuptools" in pip_calls[0]


def test_installs_oarepo_with_correct_version(setup_manager):
    manager, fake_process = setup_manager

    manager.ensure_venv(
        VenvRequirements(
            python_binary="python3.14",
            oarepo_version=14,
        )
    )

    # Check oarepo installation command
    oarepo_call = next(call for call in fake_process.calls if "oarepo" in str(call))
    assert ">=14.0.0,<15.0.0" in str(oarepo_call)


def test_respects_editable_flag(setup_manager):
    manager, fake_process = setup_manager

    # Non-editable mode
    fake_process.register(["uv", "build", "--wheel"])
    fake_process.register(["uv", "pip", "install", fake_process.any()])

    manager.ensure_venv(VenvRequirements(python_binary="python3.14", editable=False))

    # Should build wheel instead of -e install
    assert any("build" in call for call in fake_process.calls)


def test_force_removes_existing_venv(setup_manager):
    manager, fake_process = setup_manager
    venv_path = manager._config.venv.path
    venv_path.mkdir(parents=True)
    (venv_path / "placeholder").write_text("exists")

    manager.ensure_venv(
        VenvRequirements(python_binary="python3.14"),
        force=True,
    )

    # Verify the old .venv contents were removed before recreation
    assert not (venv_path / "placeholder").exists()


def test_skips_creation_if_exists(setup_manager):
    manager, fake_process = setup_manager
    venv_path = manager._config.venv.path
    venv_path.mkdir(parents=True)
    (venv_path / "pyvenv.cfg").write_text("exists")

    manager.ensure_venv(VenvRequirements(python_binary="python3.14"))

    # Should not call uv venv again
    venv_calls = [call for call in fake_process.calls if "venv" in call]
    assert len(venv_calls) == 0  # Already exists
```

### Example: Test Orchestration Workflow

```python
# tests/workflow/test_test_orchestrator.py

import pytest
from pathlib import Path
from oarepo_cli.services.test_orchestrator import TestOrchestrator
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services.config import CliConfig


@pytest.fixture
def setup_orchestrator(fake_process):
    """Set up a test execution workflow with docker/pytest faked via pytest-subprocess."""
    fake_process.register(["docker-services-cli", "up", fake_process.any()])  # Start services
    fake_process.register(["pytest", fake_process.any()])  # Run tests
    fake_process.register(["docker-services-cli", "down"])  # Stop services

    ctx = ProjectContext(
        root_directory=Path("."),
        pyproject_path=Path("pyproject.toml"),
        venv_path=Path(".venv"),
        python_binary="python3.14",
        oarepo_version=14,
    )
    ctx._pyproject_data = PyProjectData(
        raw={
            "project": {
                "name": "test-package",
                "optional-dependencies": {"tests": ["pytest"]},
            }
        }
    )

    config = CliConfig.default()
    config.test.coverage = False
    config.test.skip_services = False

    orchestrator = TestOrchestrator(ctx, config)
    return orchestrator, fake_process


def test_starts_services_before_tests(setup_orchestrator):
    orchestrator, fake_process = setup_orchestrator

    orchestrator.run_tests()

    # Services should start before pytest
    calls = list(fake_process.calls)
    services_up_idx = next(
        i for i, call in enumerate(calls) if "services" in str(call) and "up" in str(call)
    )
    pytest_idx = next(i for i, call in enumerate(calls) if "pytest" in str(call))

    assert services_up_idx < pytest_idx


def test_stops_services_after_tests(setup_orchestrator):
    orchestrator, fake_process = setup_orchestrator

    orchestrator.run_tests()

    calls = list(fake_process.calls)
    pytest_idx = next(i for i, call in enumerate(calls) if "pytest" in str(call))
    services_down_idx = next(
        i for i, call in enumerate(calls) if "services" in str(call) and "down" in str(call)
    )

    assert pytest_idx < services_down_idx


def test_passes_coverage_flags_when_enabled(setup_orchestrator):
    orchestrator, fake_process = setup_orchestrator
    orchestrator._config.test.coverage = True

    orchestrator.run_tests()

    pytest_call = next(call for call in fake_process.calls if "pytest" in str(call))
    assert "--cov" in str(pytest_call)


def test_skips_services_when_configured(setup_orchestrator):
    orchestrator, fake_process = setup_orchestrator
    orchestrator._config.test.skip_services = True

    orchestrator.run_tests()

    # Should not start/stop services
    assert not any("services" in str(call) for call in fake_process.calls)


def test_returns_failure_status_on_test_failure(setup_orchestrator):
    orchestrator, fake_process = setup_orchestrator
    fake_process.register(["pytest", fake_process.any()], returncode=1)

    result = orchestrator.run_tests()

    assert result.status == CommandStatus.FAILURE
    assert result.exit_code == 1
```

---

## 6. Integration Tests

### Purpose

End-to-end tests with real tools (uv, pytest, etc.) in isolated temporary directories. These verify actual behavior with minimal mocking.

### Fixture Setup

```python
# tests/integration/conftest.py

import pytest
import subprocess
import tempfile
from pathlib import Path


@pytest.fixture
def temp_project_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with a minimal OARepo project."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[project]
name = "oarepo-test-lib"
requires-python = ">=3.12,<3.15"
dynamic = ["version"]

[project.optional-dependencies]
oarepo = ["oarepo14>=14.0.0,<15.0.0"]
dev = ["ruff"]
tests = ["pytest"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
""")

    src_dir = tmp_path / "src" / "oarepo_test_lib"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text('__version__ = "0.1.0"')

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_example.py").write_text("""
def test_basic():
    assert True
""")

    return tmp_path


@pytest.fixture
def uv_available() -> None:
    """Skip test if uv is not installed."""
    result = subprocess.run(["which", "uv"], capture_output=True)
    if result.returncode != 0:
        pytest.skip("uv not installed")
```

### Example Integration Tests

```python
# tests/integration/test_library_venv.py

import pytest
from typer.testing import CliRunner
from oarepo_cli.cli.main import app

runner = CliRunner()


@pytest.mark.integration
def test_library_venv_creates_environment(temp_project_dir: Path):
    """Integration test: venv command creates virtual environment."""
    result = runner.invoke(
        app,
        ["--cd", str(temp_project_dir), "library", "venv"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert (temp_project_dir / ".venv").exists()
    assert (temp_project_dir / ".venv" / "bin" / "python").exists()


@pytest.mark.integration
def test_library_venv_installs_oarepo(temp_project_dir: Path):
    """Integration test: venv installs OARepo package."""
    result = runner.invoke(
        app,
        ["--cd", str(temp_project_dir), "library", "venv"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0

    # Verify oarepo is installed
    check_result = runner.invoke(
        app,
        [
            "--cd",
            str(temp_project_dir),
            "library",
            "invenio",
            "--skip-services",
            "--",
            "python",
            "-c",
            "import oarepo; print(oarepo.__version__)",
        ],
        catch_exceptions=False,
    )

    assert check_result.exit_code == 0
    assert "oarepo" in check_result.stdout.lower()


@pytest.mark.integration
def test_library_test_runs_pytest(temp_project_dir: Path):
    """Integration test: test command runs pytest successfully."""
    # First create venv
    runner.invoke(
        app,
        ["--cd", str(temp_project_dir), "library", "venv"],
        catch_exceptions=False,
    )

    # Then run tests
    result = runner.invoke(
        app,
        ["--cd", str(temp_project_dir), "library", "test", "--skip-services"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "passed" in result.stdout.lower()


@pytest.mark.integration
def test_library_lint_succeeds_on_clean_code(temp_project_dir: Path):
    """Integration test: lint passes on properly formatted code."""
    # Create venv first
    runner.invoke(
        app,
        ["--cd", str(temp_project_dir), "library", "venv"],
        catch_exceptions=False,
    )

    result = runner.invoke(
        app,
        ["--cd", str(temp_project_dir), "library", "lint"],
        catch_exceptions=False,
    )

    # Should succeed on clean code
    assert result.exit_code == 0


@pytest.mark.integration
def test_library_format_fixes_code(temp_project_dir: Path):
    """Integration test: format command fixes formatting issues."""
    # Create unformatted file
    unformatted = temp_project_dir / "src" / "oarepo_test_lib" / "unformatted.py"
    unformatted.write_text("x=1+2\n")  # Missing spaces

    # Create venv first
    runner.invoke(
        app,
        ["--cd", str(temp_project_dir), "library", "venv"],
        catch_exceptions=False,
    )

    # Run formatter
    result = runner.invoke(
        app,
        ["--cd", str(temp_project_dir), "library", "format"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0

    # Verify file was reformatted
    formatted_content = unformatted.read_text()
    assert formatted_content == "x = 1 + 2\n"
```

---

## 7. Characterization Tests

### Purpose

Compare bash script and Python CLI behavior side-by-side. These ensure behavioral compatibility during migration.

### Test Framework

```python
# tests/compatibility/__init__.py

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class CommandOutput:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class BashPythonComparator:
    """Compare bash script and Python CLI outputs."""

    def __init__(
        self,
        bash_script: Path,
        python_cli: Callable,
        test_dir: Path,
    ):
        self.bash_script = bash_script
        self.python_cli = python_cli
        self.test_dir = test_dir

    def run_bash(self, args: list[str]) -> CommandOutput:
        import time

        start = time.time()

        result = subprocess.run(
            [str(self.bash_script)] + args,
            cwd=self.test_dir,
            capture_output=True,
            text=True,
            env=self._get_env(),
        )

        return CommandOutput(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=int((time.time() - start) * 1000),
        )

    def run_python(self, args: list[str]) -> CommandOutput:
        import time

        start = time.time()

        result = self.python_cli(args)

        return CommandOutput(
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=int((time.time() - start) * 1000),
        )

    def _get_env(self) -> dict:
        import os

        env = os.environ.copy()
        # Set test-specific environment
        env["CI"] = "true"
        return env

    def compare(
        self,
        args: list[str],
        tolerance: float = 0.1,  # 10% timing tolerance
    ) -> dict:
        bash_out = self.run_bash(args)
        python_out = self.run_python(args)

        return {
            "args": args,
            "bash": bash_out,
            "python": python_out,
            "exit_code_match": bash_out.exit_code == python_out.exit_code,
            "stdout_match": self._normalize(bash_out.stdout) == self._normalize(python_out.stdout),
            "timing_ratio": python_out.duration_ms / max(bash_out.duration_ms, 1),
        }

    def _normalize(self, text: str) -> str:
        """Normalize output for comparison (remove timestamps, colors, etc.)."""
        import re

        # Remove ANSI color codes
        text = re.sub(r"\x1b\[[0-9;]*m", "", text)
        # Normalize whitespace
        text = " ".join(text.split())
        return text
```

### Characterization Test Suite

```python
# tests/compatibility/test_command_parities.py

import pytest
from pathlib import Path
from typer.testing import CliRunner
from oarepo_cli.cli.main import app
from . import BashPythonComparator

runner = CliRunner()


@pytest.fixture
def sample_library():
    """Path to sample library for compatibility testing."""
    return Path("/path/to/sample/library")


@pytest.fixture
def comparator(sample_library: Path):
    bash_script = sample_library / "run.sh"
    return BashPythonComparator(
        bash_script=bash_script,
        python_cli=lambda args: runner.invoke(app, args),
        test_dir=sample_library,
    )


# --- Library command parity ---


def test_help_output_structure(comparator: BashPythonComparator):
    """Help text should contain same commands."""
    result = comparator.compare(["--help"])

    assert result["exit_code_match"]

    # Extract command lists from help
    bash_cmds = extract_commands(result["bash"].stdout)
    python_cmds = extract_commands(result["python"].stdout)

    assert set(bash_cmds) == set(python_cmds)


def test_oarepo_versions_json_format(comparator: BashPythonComparator):
    """oarepo-versions should return valid JSON."""
    result = comparator.compare(["oarepo-versions"])

    assert result["exit_code_match"]

    # Both should produce valid JSON
    import json

    bash_json = json.loads(result["bash"].stdout)
    python_json = json.loads(result["python"].stdout)

    # Keys should match
    assert set(bash_json.keys()) == set(python_json.keys())

    # Versions should be identical
    assert bash_json["oarepo_versions"] == python_json["oarepo_versions"]
    assert bash_json["python_versions"] == python_json["python_versions"]


def test_venv_force_recreates_environment(comparator: BashPythonComparator):
    """Both should recreate venv with --force flag."""
    # First create initial venv
    comparator.run_bash(["venv"])
    comparator.run_python(["venv"])

    # Now force recreate
    bash_result = comparator.run_bash(["venv", "--force"])
    python_result = comparator.run_python(["venv", "--force"])

    # Both should succeed
    assert bash_result.exit_code == 0
    assert python_result.exit_code == 0


def test_lint_exit_codes(comparator: BashPythonComparator):
    """Lint should return same exit codes for clean/dirty code."""
    # Test on clean code
    clean_result = comparator.compare(["lint"])
    assert clean_result["exit_code_match"]

    # Introduce linting error
    # ... (setup dirty code)

    # Both should fail with same exit code
    dirty_result = comparator.compare(["lint"])
    assert dirty_result["bash"].exit_code == dirty_result["python"].exit_code
    assert dirty_result["bash"].exit_code != 0


# --- Repository command parity ---


def test_install_creates_instance_path(comparator: BashPythonComparator):
    """Install should create instance path in both implementations."""
    # Note: This is a slow integration test
    pytestmark = pytest.mark.slow

    bash_result = comparator.run_bash(["install"])
    python_result = comparator.run_python(["install"])

    assert bash_result.exit_code == 0
    assert python_result.exit_code == 0

    # Both should create .invenio.private
    assert (comparator.test_dir / ".invenio.private").exists()


def test_reset_confirms_with_user(comparator: BashPythonComparator):
    """Reset should prompt for confirmation in both."""
    # Test with "no" answer
    bash_no = comparator.run_bash_with_input(["reset"], "no\n")
    python_no = comparator.run_python_with_input(["reset"], "no\n")

    assert bash_no.exit_code == 0  # Cancelled gracefully
    assert python_no.exit_code == 0

    # Repository should still exist
    assert (comparator.test_dir / ".venv").exists()


def test_services_subcommands(comparator: BashPythonComparator):
    """Services subcommands should have matching behavior."""
    for subcmd in ["setup", "start", "stop", "destroy"]:
        result = comparator.compare(["services", subcmd])

        # Exit codes should match (may be non-zero if Docker not running)
        assert result["exit_code_match"], f"Exit code mismatch for services {subcmd}"


def extract_commands(help_text: str) -> set[str]:
    """Parse command names from help output."""
    import re

    # Match lines like "  venv              Set up..."
    pattern = r"^\s{2}(\w+)[\s\-]"
    commands = re.findall(pattern, help_text, re.MULTILINE)
    return set(commands)
```

---

## 8. Failure Injection Tests

### Purpose

Verify robustness under failure conditions: interrupted operations, missing tools, network failures, etc.

```python
# tests/fault_tolerance/test_interrupted_operations.py
"""Test graceful handling of interrupts and failures."""

import pytest
import signal
import time
from unittest.mock import patch, MagicMock
from oarepo_cli.services import process
from oarepo_cli.services.venv import VirtualEnvironmentManager
from oarepo_cli.core.errors import ProcessExecutionError


def test_venv_cleanup_on_keyboard_interrupt(temp_project_dir):
    """Partial venv creation should be cleaned up on Ctrl+C."""
    manager = VirtualEnvironmentManager(...)

    # Simulate interrupt during venv creation
    with patch.object(process, "run") as mock_run:
        mock_run.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            manager.ensure_venv(VenvRequirements(...))

        # Verify partial artifacts were cleaned up
        assert not (temp_project_dir / ".venv").exists()


def test_process_timeout_handling():
    """Long-running processes respect timeout parameter."""
    with pytest.raises(TimeoutExceeded):
        process.run(["sleep", "100"], timeout=1.0)


def test_concurrent_execution_lock(temp_project_dir):
    """Second invocation should wait for first to complete."""
    # Start first process
    process1 = subprocess.Popen(
        ["oarepo-cli", "library", "venv"],
        cwd=temp_project_dir,
    )

    # Give it time to acquire lock
    time.sleep(0.5)

    # Try to start second process
    process2 = subprocess.Popen(
        ["oarepo-cli", "library", "venv"],
        cwd=temp_project_dir,
    )

    # Second should fail with lock error
    process2.wait()
    assert process2.returncode != 0

    process1.wait()


def test_malformed_pyproject_toml_error_message(temp_project_dir):
    """Clear error message for invalid TOML."""
    (temp_project_dir / "pyproject.toml").write_text("invalid [[[ toml")

    result = runner.invoke(app, ["library", "venv"])

    assert result.exit_code != 0
    assert "Invalid TOML" in result.stdout or "Invalid TOML" in result.stderr


def test_missing_python_version_error(temp_project_dir):
    """Clear error when required Python version unavailable."""
    # Configure for Python 3.99 which doesn't exist
    manager = VirtualEnvironmentManager(...)

    with pytest.raises(VersionMismatchError) as exc_info:
        manager.ensure_venv(VenvRequirements(python_binary="python3.99"))

    assert "3.99" in str(exc_info.value)
    assert "install" in str(exc_info.value).lower()


def test_docker_unavailable_graceful_degradation(temp_project_dir):
    """Commands that don't need Docker should work without it."""
    # Docker not running
    manager = TestOrchestrator(...)
    manager._config.test.skip_services = True

    # Should still run pytest even if Docker unavailable
    result = manager.run_tests()

    # Test may fail but not due to Docker
    assert "docker" not in str(result.error).lower()
```

```python
# tests/fault_tolerance/test_rollback_behavior.py
"""Test rollback on partial failures."""

import pytest
from unittest.mock import patch
from oarepo_cli.core.errors import ProcessExecutionError


def test_failed_install_rolls_back_changes(temp_project_dir):
    """Failed installation should remove created files."""
    installer = RepositoryInstaller(...)

    # Simulate failure during installation
    with patch.object(installer, "_configure_services") as mock:
        mock.side_effect = ProcessExecutionError(...)

        with pytest.raises(ProcessExecutionError):
            installer.install()

        # Instance path should be removed
        assert not installer._ctx.instance_path.exists()


def test_partial_self_update_keeps_old_version(temp_project_dir):
    """Failed self-update should preserve working script."""
    # Download new version
    # Validate fails
    # Verify old version still in place
    ...
```

---

## 9. Test Configuration and Execution

### pytest Configuration

```ini
# pytest.ini

[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*

# Markers
markers =
    integration: marks tests as integration tests (slow, requires tools)
    compatibility: marks characterization tests (bash vs python)
    slow: marks very slow tests
    fault_tolerance: marks failure injection tests

# Coverage
addopts =
    --cov=oarepo_cli
    --cov-report=term-missing
    --cov-report=html
    --strict-markers

# Filtering
filterwarnings =
    ignore::DeprecationWarning

# Timeouts
timeout = 300  # 5 minutes max per test
```

### CI Pipeline

```yaml
# .github/workflows/tests.yml

name: Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run unit tests
        run: pytest tests/unit -v --tb=short

  contract-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run contract tests
        run: pytest tests/contracts -v --tb=short

  workflow-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run workflow tests
        run: pytest tests/workflow -v --tb=short

  integration-tests:
    runs-on: ubuntu-latest
    needs: [unit-tests, contract-tests]
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run integration tests
        run: pytest tests/integration -v --tb=short -m integration

  compatibility-tests:
    runs-on: ubuntu-latest
    needs: [integration-tests]
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      - name: Install dependencies
        run: pip install -e ".[dev,compatibility]"
      - name: Run compatibility tests
        run: pytest tests/compatibility -v --tb=short -m compatibility

  fault-tolerance-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run fault tolerance tests
        run: pytest tests/fault_tolerance -v --tb=short
```

---

## 10. Test Data Fixtures

### Sample Projects

```python
# tests/fixtures/projects.py

from pathlib import Path
import tempfile
import shutil

MINIMAL_LIBRARY = """
[project]
name = "oarepo-minimal"
version = "0.1.0"
requires-python = ">=3.12,<3.15"

[project.optional-dependencies]
oarepo = ["oarepo14>=14.0.0,<15.0.0"]
dev = ["ruff", "mypy"]
tests = ["pytest"]
"""

LIBRARY_WITH_JS = """
[project]
name = "oarepo-with-js"
requires-python = ">=3.12,<3.15"

[project.optional-dependencies]
oarepo = ["oarepo14>=14.0.0,<15.0.0"]
"""

REPOSITORY_MINIMAL = """
[project]
name = "test-repository"
requires-python = ">=3.12,<3.15"

[tool.uv.sources]
# Local packages
"""


def create_fixture_project(
    template: str,
    include_tests: bool = True,
    include_js: bool = False,
) -> Path:
    """Create a temporary project directory with given template."""
    tmpdir = tempfile.mkdtemp()
    tmp_path = Path(tmpdir)

    # Write pyproject.toml
    (tmp_path / "pyproject.toml").write_text(template)

    # Create src structure
    src_dir = tmp_path / "src" / "test_package"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text('__version__ = "0.1.0"')

    # Add tests if requested
    if include_tests:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "conftest.py").write_text("")
        (tests_dir / "test_example.py").write_text("def test_ok(): pass")

    # Add JS if requested
    if include_js:
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        (assets_dir / "package.json").write_text("{}")

    return tmp_path
```

---

This testing strategy ensures comprehensive coverage while maintaining fast feedback loops. The layered approach allows most tests to run quickly without external dependencies, while integration and characterization tests provide confidence in real-world behavior.
