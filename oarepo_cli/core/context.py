# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Project context discovery and validation."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from oarepo_cli.core.config import CliConfig
from oarepo_cli.core.errors import ConfigurationError
from oarepo_cli.services.process import get_system_path
from oarepo_cli.services.pyproject_reader import PyProjectReader
from oarepo_cli.services.version_resolver import VersionResolver


@dataclass(frozen=True)
class ProjectContext:
    """Immutable project context discovered at startup.

    Contains all the information needed to operate on an OARepo project:
    - Location of the project root and pyproject.toml
    - Virtual environment path and Python binary
    - Resolved OARepo version
    - Computed paths for code directories, instance, and assets
    """

    root_directory: Path
    pyproject_path: Path
    venv_path: Path
    python_binary: Path
    oarepo_version: int
    config: CliConfig = field(default_factory=CliConfig)

    @property
    def code_directories(self) -> list[Path]:
        """Source and test directories to lint/type-check/format.

        Mirrors ``library_runner.sh``'s ``code_directories`` detection for a
        library project: prefer a top-level ``src/`` directory (the "src
        layout"), else the package's own top-level directory derived from
        the project name (the "flat layout"), or from
        ``[tool.hatch.build.targets.wheel].packages`` if that doesn't exist
        either -- both preserved exactly, unchanged.

        A repository project built with the ``uv_build`` backend has no
        bash equivalent to mirror: it declares its source as several
        top-level module directories in ``[tool.uv.build-backend]``'s
        ``module-name`` (e.g. ``["common", "i18n", "ui"]``) instead of a
        single ``src/``/package directory. Checked between the ``src/`` and
        flat-layout checks -- a repository's project name never matches an
        existing top-level directory anyway, but this keeps the precedence
        explicit rather than relying on that coincidence.

        ``tests/`` is appended afterwards if present, for either kind of
        project.

        Returns:
            List of existing directories to process

        Raises:
            ConfigurationError: If none of the above can be found
        """
        pyproject_data = PyProjectReader().read(self.pyproject_path)

        directories: list[Path] = []

        src_dir = self.root_directory / "src"
        module_names = pyproject_data.uv_build_module_names
        if src_dir.is_dir():
            directories.append(src_dir)
        elif module_names:
            module_root = self.root_directory / pyproject_data.uv_build_module_root
            directories.extend(
                module_root / name for name in module_names if (module_root / name).is_dir()
            )
        else:
            top_level = pyproject_data.name.replace("-", "_")
            package_dir = self.root_directory / top_level
            if package_dir.is_dir():
                directories.append(package_dir)
            else:
                wheel_packages = (
                    pyproject_data.raw.get("tool", {})
                    .get("hatch", {})
                    .get("build", {})
                    .get("targets", {})
                    .get("wheel", {})
                    .get("packages", [])
                )
                if wheel_packages:
                    directories.append(self.root_directory / wheel_packages[0])
                else:
                    raise ConfigurationError(
                        f"No src/ or {top_level}/ directory found, please ensure "
                        "your package structure is correct."
                    )

        tests_dir = self.root_directory / "tests"
        if tests_dir.is_dir():
            directories.append(tests_dir)

        return directories

    @property
    def instance_path(self) -> Path | None:
        """Path to the Flask instance directory.

        Returns:
            Path to instance directory if it exists, None otherwise
        """
        instance_dir = self.root_directory / "instance"
        return instance_dir if instance_dir.exists() else None

    @property
    def assets_path(self) -> Path | None:
        """Path to the assets directory.

        Returns:
            Path to assets directory if it exists, None otherwise
        """
        assets_dir = self.root_directory / "assets"
        return assets_dir if assets_dir.exists() else None


def find_pyproject_toml(start: Path | None = None) -> Path | None:
    """Search upward from ``start`` (default: cwd) for a ``pyproject.toml``.

    Standalone helper for callers that only need the raw pyproject.toml
    path -- e.g. ``library oarepo-versions``, which reports the OARepo/
    Python/Node versions a project *declares* and must therefore keep
    working before a venv exists or an OARepo version can be resolved,
    unlike ``ContextBuilder.validate()``'s full ``ProjectContext`` (which
    requires both). ``ContextBuilder.from_cwd()`` uses this too, so the
    upward-search logic itself only lives in one place.

    Args:
        start: Directory to start searching from (default: current working
            directory)

    Returns:
        Path to the found pyproject.toml, or None if none exists in
        ``start`` or any parent directory
    """
    for directory in [start or Path.cwd(), *(start or Path.cwd()).parents]:
        candidate = directory / "pyproject.toml"
        if candidate.exists():
            return candidate
    return None


class ContextBuilder:
    """Fluent builder for constructing ProjectContext with validation.

    Usage:
        context = (ContextBuilder()
            .from_cwd()
            .with_python_override(Path("/usr/bin/python3.12"))
            .validate())
    """

    def __init__(self) -> None:
        """Initialize the context builder."""
        self._root_directory: Path | None = None
        self._pyproject_path: Path | None = None
        self._venv_path: Path | None = None
        self._python_binary: Path | None = None
        self._oarepo_version: int | None = None
        self._config: CliConfig | None = None

    def from_cwd(self) -> ContextBuilder:
        """Discover project context from current working directory.

        Searches upward from cwd to find pyproject.toml.

        Returns:
            Self for method chaining

        Raises:
            ConfigurationError: If pyproject.toml is not found
        """
        cwd = Path.cwd()

        pyproject = find_pyproject_toml(cwd)
        if pyproject is None:
            raise ConfigurationError(f"pyproject.toml not found in {cwd} or any parent directory")

        self._root_directory = pyproject.parent
        self._pyproject_path = pyproject
        return self

    def from_directory(self, path: Path) -> ContextBuilder:
        """Discover project context from a specific directory.

        Args:
            path: Directory to search for pyproject.toml

        Returns:
            Self for method chaining

        Raises:
            ConfigurationError: If pyproject.toml is not found
        """
        pyproject = path / "pyproject.toml"

        if not pyproject.exists():
            raise ConfigurationError(f"pyproject.toml not found in {path}")

        self._root_directory = path
        self._pyproject_path = pyproject
        return self

    def with_venv_path(self, path: Path) -> ContextBuilder:
        """Set the virtual environment path.

        Args:
            path: Path to virtual environment

        Returns:
            Self for method chaining
        """
        self._venv_path = path
        return self

    def with_python_override(self, path: Path) -> ContextBuilder:
        """Override the Python binary path.

        Args:
            path: Path to Python executable

        Returns:
            Self for method chaining
        """
        self._python_binary = path
        return self

    def with_oarepo_version(self, version: int) -> ContextBuilder:
        """Override the OARepo version.

        Args:
            version: OARepo major version

        Returns:
            Self for method chaining
        """
        self._oarepo_version = version
        return self

    def with_config(self, config: CliConfig) -> ContextBuilder:
        """Set the configuration.

        Args:
            config: CLI configuration

        Returns:
            Self for method chaining
        """
        self._config = config
        return self

    def validate(self) -> ProjectContext:
        """Validate and construct the ProjectContext.

        Performs the following validations:
        - pyproject.toml exists and is readable
        - Virtual environment exists (or can be created)
        - Python binary is available
        - OARepo version is compatible

        Returns:
            Validated ProjectContext

        Raises:
            ConfigurationError: If required files/paths are missing
            VersionMismatchError: If the Python/OARepo version combination
                is incompatible
        """
        if self._root_directory is None or self._pyproject_path is None:
            raise ConfigurationError("Project root and pyproject.toml must be set")

        # Read pyproject.toml
        pyproject_reader = PyProjectReader()
        pyproject_data = pyproject_reader.read(self._pyproject_path)

        # Get config from pyproject.toml and environment
        config_from_pyproject = CliConfig.from_pyproject(self._root_directory)
        config_from_env = CliConfig.from_env()
        config = CliConfig.merge([config_from_pyproject, config_from_env])

        if self._config:
            config = CliConfig.merge([config, self._config])

        # Determine venv path
        venv_path = self._venv_path or self._root_directory / config.venv.path

        # Determine Python binary
        if self._python_binary:
            python_binary = self._python_binary
        elif config.python.binary:
            python_binary = Path(config.python.binary)
            if not python_binary.is_absolute():
                # Try to find in PATH, excluding any active venv (see get_system_path)
                resolved = shutil.which(python_binary.name, path=get_system_path())
                if resolved:
                    python_binary = Path(resolved)
        else:
            # Auto-detect using version resolver, excluding any active venv
            # from PATH -- otherwise resolving e.g. "python3.14" while a
            # project's own venv is activated finds that venv's own
            # interpreter, which is wrong for anything that needs to
            # (re)create that very venv (e.g. `repository upgrade`, which
            # removes the venv before reinstalling).
            resolver = VersionResolver(pyproject_reader=pyproject_reader)
            info = resolver.resolve_from_pyproject(self._pyproject_path)
            python_version = resolver.find_available_python(info.python_versions)
            system_path = get_system_path()
            python_binary = Path(
                shutil.which(f"python{python_version}", path=system_path) or "python"
            )

        # Validate Python binary exists
        if not python_binary.exists():
            raise ConfigurationError(f"Python binary not found: {python_binary}")

        # Determine OARepo version
        if self._oarepo_version:
            oarepo_version = self._oarepo_version
        elif config.oarepo.version:
            oarepo_version = config.oarepo.version
        elif pyproject_data.oarepo_versions:
            oarepo_version = pyproject_data.oarepo_versions[0]
        else:
            raise ConfigurationError(
                "OARepo version not specified. Add an 'oarepo' dependency to "
                "[project].dependencies (or [project.optional-dependencies]) in "
                "pyproject.toml, or set the OAREPO_VERSION environment variable"
            )

        # A missing venv is not an error here: repository/library `install`
        # creates it on demand, so context discovery only needs to resolve
        # where it *would* live, not that it already exists.

        # Validate OARepo-Python compatibility
        resolver = VersionResolver(pyproject_reader=pyproject_reader)
        resolver.validate_compatibility(python_binary.name, oarepo_version)

        return ProjectContext(
            root_directory=self._root_directory,
            pyproject_path=self._pyproject_path,
            venv_path=venv_path,
            python_binary=python_binary,
            oarepo_version=oarepo_version,
            config=config,
        )


def discover_context(cwd: Path | None = None) -> ProjectContext:
    """Convenience function to discover project context.

    Args:
        cwd: Optional directory to start search from (defaults to current directory)

    Returns:
        Validated ProjectContext

    Raises:
        ConfigurationError: If context cannot be discovered
    """
    builder = ContextBuilder()
    if cwd:
        builder.from_directory(cwd)
    else:
        builder.from_cwd()
    return builder.validate()
