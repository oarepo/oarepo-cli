# OARepo CLI Testing Strategy

## 1. Overview

This document defines the comprehensive testing strategy for the OARepo CLI Python implementation. The goal is to achieve high confidence in behavioral compatibility with the existing shell scripts while ensuring maintainability and reliability of the new codebase.

### Testing Principles

1. **Test behavior, not implementation**: Focus on observable outcomes (exit codes, output, file system changes)
2. **Isolate external dependencies**: Mock subprocess, network, and filesystem where appropriate
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
| Contract Tests | 30+ | <5s each | All adapters |
| Workflow Tests | 50+ | <10s each | All workflows |
| Integration Tests | 20+ | <60s each | Critical paths |
| Characterization Tests | 40+ | <30s each | Command parity |

---

## 3. Unit Tests

### Scope

Pure unit tests for logic that doesn't require external tools or filesystem access.

### Covered Components

- TOML parsing (`pyproject_reader.py`)
- Version resolution logic (`version_resolver.py`)
- Configuration model validation (`config.py`)
- Context discovery algorithms (`context.py`)
- Platform detection utilities (`platform.py`)
- Error message formatting (`errors.py`)

### Example: PyProjectReader Tests

```python
# tests/unit/test_pyproject_reader.py

import pytest
from pathlib import Path
from oarepo_cli.services.pyproject_reader import (
    PyProjectReader,
    PyProjectData,
    ConfigurationError,
)
from tests.fakes import FakeFileSystem


class TestPyProjectReader:
    """Unit tests for pyproject.toml parsing."""
    
    def test_parse_minimal_project(self):
        """Parse basic project metadata."""
        toml_content = """
[project]
name = "test-package"
requires-python = ">=3.12,<3.15"
"""
        fs = FakeFileSystem({
            "pyproject.toml": toml_content,
        })
        reader = PyProjectReader(fs)
        data = reader.read(Path("pyproject.toml"))
        
        assert data.name == "test-package"
        assert data.requires_python == ">=3.12,<3.15"
    
    def test_extract_oarepo_versions_single(self):
        """Extract single OARepo version from optional dependencies."""
        toml_content = """
[project.optional-dependencies]
oarepo = ["oarepo14>=14.0.0,<15.0.0"]
"""
        fs = FakeFileSystem({"pyproject.toml": toml_content})
        reader = PyProjectReader(fs)
        data = reader.read(Path("pyproject.toml"))
        
        assert data.oarepo_versions == [14]
    
    def test_extract_oarepo_versions_multiple(self):
        """Extract multiple OARepo versions."""
        toml_content = """
[project.optional-dependencies]
oarepo = [
    "oarepo13>=13.0.0,<14.0.0",
    "oarepo14>=14.0.0,<15.0.0",
]
"""
        fs = FakeFileSystem({"pyproject.toml": toml_content})
        reader = PyProjectReader(fs)
        data = reader.read(Path("pyproject.toml"))
        
        assert data.oarepo_versions == [13, 14]
    
    def test_missing_pyproject_raises_error(self):
        """ConfigurationError when pyproject.toml not found."""
        fs = FakeFileSystem({})
        reader = PyProjectReader(fs)
        
        with pytest.raises(ConfigurationError) as exc_info:
            reader.read(Path("nonexistent.toml"))
        
        assert "not found" in str(exc_info.value)
    
    def test_invalid_toml_raises_error(self):
        """ConfigurationError for malformed TOML."""
        fs = FakeFileSystem({"pyproject.toml": "invalid [[[[ syntax"})
        reader = PyProjectReader(fs)
        
        with pytest.raises(ConfigurationError) as exc_info:
            reader.read(Path("pyproject.toml"))
        
        assert "Invalid TOML" in str(exc_info.value)
    
    def test_get_default_extras(self):
        """Parse default_extras from tool.oarepo section."""
        toml_content = """
[tool.oarepo]
default_extras = ["dev", "tests"]
"""
        fs = FakeFileSystem({"pyproject.toml": toml_content})
        reader = PyProjectReader(fs)
        data = reader.read(Path("pyproject.toml"))
        
        assert data.default_extras == ["dev", "tests"]
    
    @pytest.mark.parametrize(
        "constraint,expected",
        [
            (">=3.12,<3.15", ("3.12", "3.13", "3.14")),
            (">=3.13,<3.14", ("3.13",)),
            (">=3.12", None),  # No upper bound
        ],
    )
    def test_parse_python_constraint(self, constraint, expected):
        """Parse Python version constraints into discrete versions."""
        toml_content = f"""
[project]
name = "test"
requires-python = "{constraint}"
"""
        fs = FakeFileSystem({"pyproject.toml": toml_content})
        reader = PyProjectReader(fs)
        data = reader.read(Path("pyproject.toml"))
        
        if expected is None:
            with pytest.raises(ConfigurationError):
                data.python_version_range
        else:
            assert data.python_version_range == expected


class TestVersionResolver:
    """Unit tests for version resolution logic."""
    
    def test_find_highest_available_python(self):
        """Select highest Python version that exists on system."""
        resolver = VersionResolver(FakeProcessExecutor())
        
        # Simulate system with Python 3.12 and 3.14
        resolver._fs.set_executables(["python3.12", "python3.14"])
        
        available = resolver.find_available_python(["3.12", "3.13", "3.14"])
        assert available == "3.14"
    
    def test_fallback_to_lower_version(self):
        """Use lower version if highest not available."""
        resolver = VersionResolver(FakeProcessExecutor())
        resolver._fs.set_executables(["python3.12"])
        
        available = resolver.find_available_python(["3.13", "3.14"])
        assert available == "3.12"
    
    def test_no_compatible_version_raises_error(self):
        """VersionMismatchError when no Python version available."""
        resolver = VersionResolver(FakeProcessExecutor())
        resolver._fs.set_executables([])
        
        with pytest.raises(VersionMismatchError):
            resolver.find_available_python(["3.14", "3.15"])
    
    def test_validate_oarepo_python_compatibility(self):
        """Check that Python version supports OARepo version."""
        resolver = VersionResolver(FakeProcessExecutor())
        
        # Python 3.14 required for OARepo 14
        resolver.validate_compatibility("3.14", 14)  # Should pass
        
        with pytest.raises(VersionMismatchError):
            resolver.validate_compatibility("3.12", 14)  # Too old
```

### Fake Implementations

```python
# tests/fakes.py

from pathlib import Path
from typing import Optional, Sequence
from oarepo_cli.services.process import ProcessExecutor, ProcessResult
from oarepo_cli.services.filesystem import FileSystem


class FakeFileSystem(FileSystem):
    """In-memory filesystem for testing."""
    
    def __init__(self, files: dict[str, str] | None = None):
        self._files = files or {}
        self._executables: set[str] = set()
    
    def set_executables(self, executables: list[str]):
        """Mock available system executables."""
        self._executables = set(executables)
    
    def exists(self, path: Path) -> bool:
        return str(path) in self._files
    
    def read_text(self, path: Path) -> str:
        if str(path) not in self._files:
            raise FileNotFoundError(f"File not found: {path}")
        return self._files[str(path)]
    
    def write_text(self, path: Path, content: str) -> None:
        self._files[str(path)] = content
    
    def rmtree(self, path: Path, ignore_errors: bool = False) -> None:
        prefix = str(path) + "/"
        self._files = {k: v for k, v in self._files.items() if not k.startswith(prefix)}
    
    def mkdir(self, path: Path, parents: bool = False) -> None:
        # Simplified: just track directory existence
        pass
    
    def symlink(self, target: Path, link_name: Path) -> None:
        self._files[str(link_name)] = f"symlink:{target}"
    
    def is_executable(self, path: str) -> bool:
        return path in self._executables


class FakeProcessExecutor(ProcessExecutor):
    """Fake process executor for testing."""
    
    def __init__(self):
        self._commands: dict[list[str], ProcessResult] = {}
        self._call_log: list[list[str]] = []
    
    def register_response(
        self,
        command: list[str],
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ):
        """Register expected command response."""
        self._commands[command] = ProcessResult(
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            command=command,
            cwd=Path.cwd(),
            duration_ms=0,
        )
    
    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Optional[Path] = None,
        env: Optional[dict[str, str]] = None,
        capture_output: bool = True,
        check: bool = True,
        forward_stdout: bool = False,
        timeout: Optional[float] = None,
    ) -> ProcessResult:
        cmd_list = list(command)
        self._call_log.append(cmd_list)
        
        if cmd_list in self._commands:
            result = self._commands[cmd_list]
        else:
            # Default behavior for unregistered commands
            result = ProcessResult(
                returncode=0,
                stdout="",
                stderr="",
                command=cmd_list,
                cwd=cwd or Path.cwd(),
                duration_ms=0,
            )
        
        if check and result.returncode != 0:
            from oarepo_cli.core.errors import ProcessExecutionError
            raise ProcessExecutionError(
                command=cmd_list,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        
        return result
    
    def stream(self, command, *, cwd=None, env=None):
        yield from []
    
    def get_output(self, command, *, cwd=None, env=None):
        result = self.run(command, cwd=cwd, env=env, check=False)
        return result.stdout.strip()
    
    @property
    def call_log(self) -> list[list[str]]:
        """Return list of all executed commands."""
        return self._call_log.copy()
```

---

## 4. Contract Tests

### Purpose

Verify that adapter implementations satisfy their protocols. These tests ensure that swapping implementations (e.g., real vs fake) maintains consistent behavior.

### ProcessExecutor Contract Tests

```python
# tests/contracts/test_process_executor.py

import pytest
from pathlib import Path
from oarepo_cli.services.process import ProcessExecutor, ProcessExecutionError

@pytest.fixture
def executor() -> ProcessExecutor:
    """Override in each test to test different implementations."""
    raise NotImplementedError("Each test must provide its own executor")


class TestProcessExecutorContract:
    """Contract tests for ProcessExecutor implementations."""
    
    def test_returns_zero_exit_code_for_success(self, executor: ProcessExecutor):
        result = executor.run(["echo", "hello"], check=False)
        assert result.returncode == 0
    
    def test_captures_stdout_correctly(self, executor: ProcessExecutor):
        result = executor.run(["echo", "test output"], check=False)
        assert "test output" in result.stdout
    
    def test_captures_stderr_correctly(self, executor: ProcessExecutor):
        result = executor.run(
            ["python", "-c", "import sys; print('error', file=sys.stderr)"],
            check=False,
        )
        assert "error" in result.stderr
    
    def test_raises_on_nonzero_with_check_true(self, executor: ProcessExecutor):
        with pytest.raises(ProcessExecutionError):
            executor.run(["python", "-c", "import sys; sys.exit(42)"], check=True)
    
    def test_does_not_raise_on_nonzero_with_check_false(self, executor: ProcessExecutor):
        result = executor.run(
            ["python", "-c", "import sys; sys.exit(42)"],
            check=False,
        )
        assert result.returncode == 42
    
    def test_environment_variables_passed_correctly(self, executor: ProcessExecutor):
        result = executor.run(
            ["python", "-c", "import os; print(os.environ.get('TEST_VAR'))"],
            env={"TEST_VAR": "test_value"},
            check=False,
        )
        assert result.stdout.strip() == "test_value"
    
    def test_cwd_parameter_sets_working_directory(self, executor: ProcessExecutor, tmp_path: Path):
        # Create a file in tmp_path
        (tmp_path / "test.txt").write_text("content")
        
        result = executor.run(
            ["cat", "test.txt"],
            cwd=tmp_path,
            check=False,
        )
        assert "content" in result.stdout
    
    def test_command_is_stored_in_result(self, executor: ProcessExecutor):
        result = executor.run(["echo", "test"], check=False)
        assert "echo" in result.command
        assert "test" in result.command
    
    def test_duration_is_positive(self, executor: ProcessExecutor):
        result = executor.run(["echo", "test"], check=False)
        assert result.duration_ms >= 0
    
    def test_shell_injection_prevented(self, executor: ProcessExecutor):
        """Ensure arguments are not interpreted as shell commands."""
        # This should NOT execute rm -rf /
        result = executor.run(
            ["echo", "; rm -rf / ;"],
            check=False,
        )
        # Output should be literal string
        assert "; rm -rf / ;" in result.stdout
    
    def test_timeout_raises_exception(self, executor: ProcessExecutor):
        with pytest.raises(TimeoutExceeded):
            executor.run(["sleep", "100"], timeout=0.1)


# Concrete test classes for each implementation

class TestSubprocessExecutor(TestProcessExecutorContract):
    """Tests for real subprocess-based executor."""
    
    @pytest.fixture
    def executor(self) -> ProcessExecutor:
        from oarepo_cli.adapters.subprocess_executor import SubprocessExecutor
        return SubprocessExecutor()


class TestFakeProcessExecutor(TestProcessExecutorContract):
    """Tests for fake executor used in unit tests."""
    
    @pytest.fixture
    def executor(self) -> ProcessExecutor:
        return FakeProcessExecutor()
```

### FileSystem Contract Tests

```python
# tests/contracts/test_filesystem.py

import pytest
from pathlib import Path
from oarepo_cli.services.filesystem import FileSystem

@pytest.fixture
def filesystem() -> FileSystem:
    raise NotImplementedError

class TestFileSystemContract:
    def test_exists_returns_true_for_existing_file(self, filesystem: FileSystem, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        assert filesystem.exists(test_file)
    
    def test_exists_returns_false_for_missing_file(self, filesystem: FileSystem, tmp_path: Path):
        assert not filesystem.exists(tmp_path / "nonexistent.txt")
    
    def test_read_text_returns_file_content(self, filesystem: FileSystem, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        expected = "Hello, World!"
        test_file.write_text(expected)
        
        actual = filesystem.read_text(test_file)
        assert actual == expected
    
    def test_write_text_creates_file(self, filesystem: FileSystem, tmp_path: Path):
        target = tmp_path / "new.txt"
        filesystem.write_text(target, "content")
        assert target.exists()
        assert target.read_text() == "content"
    
    def test_rmtree_removes_directory_and_contents(self, filesystem: FileSystem, tmp_path: Path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "file.txt").write_text("content")
        
        filesystem.rmtree(subdir)
        assert not subdir.exists()
    
    def test_mkdir_creates_directory(self, filesystem: FileSystem, tmp_path: Path):
        target = tmp_path / "new_dir"
        filesystem.mkdir(target)
        assert target.is_dir()
    
    def test_mkdir_parents_creates_intermediate_directories(self, filesystem: FileSystem, tmp_path: Path):
        target = tmp_path / "a" / "b" / "c"
        filesystem.mkdir(target, parents=True)
        assert target.is_dir()


class TestRealFileSystem(TestFileSystemContract):
    @pytest.fixture
    def filesystem(self) -> FileSystem:
        from oarepo_cli.adapters.real_filesystem import RealFileSystem
        return RealFileSystem()


class TestFakeFileSystem(TestFileSystemContract):
    @pytest.fixture
    def filesystem(self) -> FileSystem:
        return FakeFileSystem()
```

---

## 5. Workflow Tests

### Purpose

Test complete business workflows using fake adapters. These verify that services orchestrate correctly without requiring real external tools.

### Example: Virtual Environment Setup Workflow

```python
# tests/workflow/test_venv_workflow.py

import pytest
from pathlib import Path
from oarepo_cli.services.venv import VirtualEnvironmentManager, VenvRequirements
from oarepo_cli.services.config import CliConfig
from tests.fakes import FakeFileSystem, FakeProcessExecutor


class TestVirtualEnvironmentWorkflow:
    """Test venv creation workflow with fakes."""
    
    @pytest.fixture
    def setup_manager(self):
        fs = FakeFileSystem({
            "pyproject.toml": """
[project]
name = "test-package"
requires-python = ">=3.12,<3.15"

[project.optional-dependencies]
oarepo = ["oarepo14>=14.0.0,<15.0.0"]
dev = ["ruff", "mypy"]
tests = ["pytest"]
""",
        })
        fs.set_executables(["python3.12", "python3.14"])
        
        process = FakeProcessExecutor()
        # Register expected uv commands
        process.register_response(["uv", "venv", "--python", "python3.14", "--seed", ".venv"])
        process.register_response([
            ".venv/bin/python", "-m", "pip", "install", "setuptools"
        ])
        process.register_response([
            "uv", "pip", "install", "oarepo[rdm,tests]>=14.0.0,<15.0.0"
        ])
        process.register_response([
            "uv", "pip", "install", "-e", ".[dev,tests,oarepo14]"
        ])
        
        config = CliConfig.default()
        config.venv.path = Path(".venv")
        
        manager = VirtualEnvironmentManager(process, fs, config)
        return manager, process
    
    def test_creates_venv_if_missing(self, setup_manager):
        manager, process = setup_manager
        
        manager.ensure_venv(VenvRequirements(python_binary="python3.14"))
        
        # Verify uv venv was called
        assert any("venv" in cmd for cmd in process.call_log)
    
    def test_installs_setuptools_first(self, setup_manager):
        manager, process = setup_manager
        
        manager.ensure_venv(VenvRequirements(python_binary="python3.14"))
        
        # setuptools should be first pip install
        pip_commands = [cmd for cmd in process.call_log if "pip" in cmd]
        assert "setuptools" in pip_commands[0]
    
    def test_installs_oarepo_with_correct_version(self, setup_manager):
        manager, process = setup_manager
        
        manager.ensure_venv(VenvRequirements(
            python_binary="python3.14",
            oarepo_version=14,
        ))
        
        # Check oarepo installation command
        oarepo_cmd = next(
            cmd for cmd in process.call_log
            if "oarepo" in cmd
        )
        assert ">=14.0.0,<15.0.0" in oarepo_cmd
    
    def test_respects_editable_flag(self, setup_manager):
        manager, process = setup_manager
        
        # Non-editable mode
        process.register_response(["uv", "build", "--wheel"])
        process.register_response(["uv", "pip", "install", "dist/test_package-*.whl"])
        
        manager.ensure_venv(
            VenvRequirements(python_binary="python3.14", editable=False)
        )
        
        # Should build wheel instead of -e install
        assert any("build" in cmd for cmd in process.call_log)
    
    def test_force_removes_existing_venv(self, setup_manager):
        manager, process = setup_manager
        manager._fs._files[".venv/placeholder"] = "exists"
        
        manager.ensure_venv(
            VenvRequirements(python_binary="python3.14"),
            force=True,
        )
        
        # Verify .venv was removed
        assert ".venv/placeholder" not in manager._fs._files
    
    def test_skips_creation_if_exists(self, setup_manager):
        manager, process = setup_manager
        manager._fs._files[".venv/pyvenv.cfg"] = "exists"
        
        manager.ensure_venv(VenvRequirements(python_binary="python3.14"))
        
        # Should not call uv venv again
        venv_calls = [cmd for cmd in process.call_log if "venv" in cmd]
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
from tests.fakes import FakeFileSystem, FakeProcessExecutor


class TestTestOrchestratorWorkflow:
    """Test test execution workflow."""
    
    @pytest.fixture
    def setup_orchestrator(self):
        fs = FakeFileSystem({
            "pyproject.toml": """
[project]
name = "test-package"
[project.optional-dependencies]
tests = ["pytest"]
""",
            "src/test_package/module.py": "def hello(): pass",
            "tests/test_module.py": "def test_hello(): pass",
        })
        fs.set_executables(["python3.14"])
        
        process = FakeProcessExecutor()
        process.register_response(["docker-services-cli", "up", ...])  # Start services
        process.register_response(["pytest", ...])  # Run tests
        process.register_response(["docker-services-cli", "down"])  # Stop services
        
        ctx = ProjectContext(
            root_directory=Path("."),
            pyproject_path=Path("pyproject.toml"),
            venv_path=Path(".venv"),
            python_binary="python3.14",
            oarepo_version=14,
        )
        ctx._pyproject_data = PyProjectData(raw={
            "project": {
                "name": "test-package",
                "optional-dependencies": {"tests": ["pytest"]},
            }
        })
        
        config = CliConfig.default()
        config.test.coverage = False
        config.test.skip_services = False
        
        orchestrator = TestOrchestrator(process, ctx, config)
        return orchestrator, process
    
    def test_starts_services_before_tests(self, setup_orchestrator):
        orchestrator, process = setup_orchestrator
        
        orchestrator.run_tests()
        
        # Services should start before pytest
        log = process.call_log
        services_up_idx = next(i for i, cmd in enumerate(log) if "services" in str(cmd) and "up" in str(cmd))
        pytest_idx = next(i for i, cmd in enumerate(log) if "pytest" in str(cmd))
        
        assert services_up_idx < pytest_idx
    
    def test_stops_services_after_tests(self, setup_orchestrator):
        orchestrator, process = setup_orchestrator
        
        orchestrator.run_tests()
        
        log = process.call_log
        pytest_idx = next(i for i, cmd in enumerate(log) if "pytest" in str(cmd))
        services_down_idx = next(i for i, cmd in enumerate(log) if "services" in str(cmd) and "down" in str(cmd))
        
        assert pytest_idx < services_down_idx
    
    def test_passes_coverage_flags_when_enabled(self, setup_orchestrator):
        orchestrator, process = setup_orchestrator
        orchestrator._config.test.coverage = True
        
        orchestrator.run_tests()
        
        pytest_cmd = next(cmd for cmd in process.call_log if "pytest" in str(cmd))
        assert "--cov" in pytest_cmd
    
    def test_skips_services_when_configured(self, setup_orchestrator):
        orchestrator, process = setup_orchestrator
        orchestrator._config.test.skip_services = True
        
        orchestrator.run_tests()
        
        # Should not start/stop services
        assert not any("services" in str(cmd) for cmd in process.call_log)
    
    def test_returns_failure_status_on_test_failure(self, setup_orchestrator):
        orchestrator, process = setup_orchestrator
        process.register_response(["pytest", ...], returncode=1)
        
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
            "--cd", str(temp_project_dir),
            "library", "invenio", "--skip-services",
            "--", "python", "-c",
            "import oarepo; print(oarepo.__version__)"
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
        text = re.sub(r'\x1b\[[0-9;]*m', '', text)
        # Normalize whitespace
        text = ' '.join(text.split())
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


class TestLibraryCommandParity:
    """Verify library commands produce equivalent outputs."""
    
    def test_help_output_structure(self, comparator: BashPythonComparator):
        """Help text should contain same commands."""
        result = comparator.compare(["--help"])
        
        assert result["exit_code_match"]
        
        # Extract command lists from help
        bash_cmds = extract_commands(result["bash"].stdout)
        python_cmds = extract_commands(result["python"].stdout)
        
        assert set(bash_cmds) == set(python_cmds)
    
    def test_oarepo_versions_json_format(self, comparator: BashPythonComparator):
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
    
    def test_venv_force_recreates_environment(self, comparator: BashPythonComparator):
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
    
    def test_lint_exit_codes(self, comparator: BashPythonComparator):
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


class TestRepositoryCommandParity:
    """Verify repository commands produce equivalent outputs."""
    
    def test_install_creates_instance_path(self, comparator: BashPythonComparator):
        """Install should create instance path in both implementations."""
        # Note: This is a slow integration test
        pytestmark = pytest.mark.slow
        
        bash_result = comparator.run_bash(["install"])
        python_result = comparator.run_python(["install"])
        
        assert bash_result.exit_code == 0
        assert python_result.exit_code == 0
        
        # Both should create .invenio.private
        assert (comparator.test_dir / ".invenio.private").exists()
    
    def test_reset_confirms_with_user(self, comparator: BashPythonComparator):
        """Reset should prompt for confirmation in both."""
        # Test with "no" answer
        bash_no = comparator.run_bash_with_input(["reset"], "no\n")
        python_no = comparator.run_python_with_input(["reset"], "no\n")
        
        assert bash_no.exit_code == 0  # Cancelled gracefully
        assert python_no.exit_code == 0
        
        # Repository should still exist
        assert (comparator.test_dir / ".venv").exists()
    
    def test_services_subcommands(self, comparator: BashPythonComparator):
        """Services subcommands should have matching behavior."""
        for subcmd in ["setup", "start", "stop", "destroy"]:
            result = comparator.compare(["services", subcmd])
            
            # Exit codes should match (may be non-zero if Docker not running)
            assert result["exit_code_match"], f"Exit code mismatch for services {subcmd}"


def extract_commands(help_text: str) -> set[str]:
    """Parse command names from help output."""
    import re
    # Match lines like "  venv              Set up..."
    pattern = r'^\s{2}(\w+)[\s\-]'
    commands = re.findall(pattern, help_text, re.MULTILINE)
    return set(commands)
```

---

## 8. Failure Injection Tests

### Purpose

Verify robustness under failure conditions: interrupted operations, missing tools, network failures, etc.

```python
# tests/fault_tolerance/test_interrupted_operations.py

import pytest
import signal
import time
from unittest.mock import patch, MagicMock
from oarepo_cli.services.venv import VirtualEnvironmentManager
from oarepo_cli.core.errors import ProcessExecutionError


class TestInterruptHandling:
    """Test graceful handling of interrupts and failures."""
    
    def test_venv_cleanup_on_keyboard_interrupt(self, temp_project_dir):
        """Partial venv creation should be cleaned up on Ctrl+C."""
        manager = VirtualEnvironmentManager(...)
        
        # Simulate interrupt during venv creation
        with patch.object(manager._process, "run") as mock_run:
            mock_run.side_effect = KeyboardInterrupt()
            
            with pytest.raises(KeyboardInterrupt):
                manager.ensure_venv(VenvRequirements(...))
            
            # Verify partial artifacts were cleaned up
            assert not (temp_project_dir / ".venv").exists()
    
    def test_process_timeout_handling(self):
        """Long-running processes respect timeout parameter."""
        executor = SubprocessExecutor()
        
        with pytest.raises(TimeoutExceeded):
            executor.run(["sleep", "100"], timeout=1.0)
    
    def test_concurrent_execution_lock(self, temp_project_dir):
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
    
    def test_malformed_pyproject_toml_error_message(self, temp_project_dir):
        """Clear error message for invalid TOML."""
        (temp_project_dir / "pyproject.toml").write_text("invalid [[[ toml")
        
        result = runner.invoke(app, ["library", "venv"])
        
        assert result.exit_code != 0
        assert "Invalid TOML" in result.stdout or "Invalid TOML" in result.stderr
    
    def test_missing_python_version_error(self, temp_project_dir):
        """Clear error when required Python version unavailable."""
        # Configure for Python 3.99 which doesn't exist
        manager = VirtualEnvironmentManager(...)
        
        with pytest.raises(VersionMismatchError) as exc_info:
            manager.ensure_venv(VenvRequirements(python_binary="python3.99"))
        
        assert "3.99" in str(exc_info.value)
        assert "install" in str(exc_info.value).lower()
    
    def test_docker_unavailable_graceful_degradation(self, temp_project_dir):
        """Commands that don't need Docker should work without it."""
        # Docker not running
        manager = TestOrchestrator(...)
        manager._config.test.skip_services = True
        
        # Should still run pytest even if Docker unavailable
        result = manager.run_tests()
        
        # Test may fail but not due to Docker
        assert "docker" not in str(result.error).lower()


class TestRollbackBehavior:
    """Test rollback on partial failures."""
    
    def test_failed_install_rolls_back_changes(self, temp_project_dir):
        """Failed installation should remove created files."""
        installer = RepositoryInstaller(...)
        
        # Simulate failure during installation
        with patch.object(installer, "_configure_services") as mock:
            mock.side_effect = ProcessExecutionError(...)
            
            with pytest.raises(ProcessExecutionError):
                installer.install()
            
            # Instance path should be removed
            assert not installer._ctx.instance_path.exists()
    
    def test_partial_self_update_keeps_old_version(self, temp_project_dir):
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
python_classes = Test*
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
        (assets_dir / "package.json").write_text('{}')
    
    return tmp_path
```

---

This testing strategy ensures comprehensive coverage while maintaining fast feedback loops. The layered approach allows most tests to run quickly without external dependencies, while integration and characterization tests provide confidence in real-world behavior.
