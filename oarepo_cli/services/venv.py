# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT
"""Virtual environment management for OARepo projects."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from oarepo_cli.core.config import CliConfig

from oarepo_cli.core.errors import ValidationError
from oarepo_cli.core.platform import get_platform_detector
from oarepo_cli.services import process
from oarepo_cli.services.version_resolver import VersionResolver


@dataclass
class VenvRequirements:
    """Requirements for virtual environment setup.

    Defines what Python version, OARepo version, and extras are needed
    to create or verify a virtual environment for an OARepo project.
    """

    python_binary: str
    oarepo_version: int | None = None
    extras: list[str] = field(default_factory=list)
    editable: bool = True

    def __post_init__(self) -> None:
        """Validate requirements after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate Python-OARepo compatibility.

        Raises:
            ValidationError: If Python version is incompatible with OARepo version.
        """
        if self.oarepo_version is None:
            # No OARepo version specified, nothing to validate
            return

        # Extract Python version from binary path (e.g., "python3.14" -> "3.14")
        python_version = self._extract_python_version()

        # Use VersionResolver to check compatibility
        resolver = VersionResolver()
        if not resolver.is_compatible(python_version, self.oarepo_version):
            msg = (
                f"Python {python_version} is not compatible with "
                f"OARepo version {self.oarepo_version}"
            )
            raise ValidationError(msg)

    def _extract_python_version(self) -> str:
        """Extract version string from Python binary path.

        Examples:
            "python3.14" -> "3.14"
            "/usr/bin/python3.13" -> "3.13"
            "python3" -> "3" (will be validated by VersionResolver)

        Returns:
            Version string extracted from binary name.
        """
        # Get the binary name without path
        binary_name = self.python_binary.split("/")[-1]

        # Remove "python" prefix if present
        if binary_name.startswith("python"):
            version_str = binary_name[6:]  # Remove "python" (6 chars)
            return version_str if version_str else "3"  # Default to "3" if just "python"

        # If no "python" prefix, return as-is (unusual case)
        return binary_name


class VirtualEnvironmentManager:
    """Manages Python virtual environments via uv.

    Handles creation, dependency installation, and cleanup of virtual environments
    for OARepo projects. Uses `uv` for fast, reliable environment management.

    All operations are anchored to an explicit ``project_root`` and target the
    venv's interpreter by absolute path, so behavior never depends on the
    process's current working directory.
    """

    def __init__(self, config: CliConfig, project_root: Path) -> None:
        """Initialize the virtual environment manager.

        Args:
            config: CLI configuration containing venv path and other settings
            project_root: Absolute path to the project root (source of the
                editable/wheel install and base for a relative venv.path)
        """
        self._config = config
        self._project_root = project_root
        self._platform = get_platform_detector()

        venv_path = config.venv.path
        self._venv_path = venv_path if venv_path.is_absolute() else project_root / venv_path

    def ensure_venv(
        self,
        requirements: VenvRequirements,
        force: bool = False,
        quiet: bool = False,
    ) -> Path:
        """Ensure virtual environment exists with required packages.

        Creates a new virtual environment if it doesn't exist, or recreates it
        if force=True. Installs OARepo and project dependencies according to
        the requirements.

        Args:
            requirements: Python version, OARepo version, extras to install
            force: If True, remove existing venv and recreate from scratch
            quiet: If True, suppress command output (for --quiet flag)

        Returns:
            Path to the virtual environment directory

        Raises:
            ValidationError: If requirements are invalid
            ProcessExecutionError: If uv commands fail
        """
        venv_path = self._venv_path

        if force and venv_path.exists():
            shutil.rmtree(venv_path)

        if venv_path.exists() and not self._is_valid_venv(venv_path):
            # Directory is present but not a real venv (e.g. left behind by
            # a crashed run) - treat like it doesn't exist and recreate it.
            shutil.rmtree(venv_path)

        if not venv_path.exists():
            self._create_venv(requirements.python_binary, venv_path, quiet=quiet)

        self._install_dependencies(requirements, venv_path, quiet=quiet)

        return venv_path

    def ensure_venv_fast(self, requirements: VenvRequirements, quiet: bool = False) -> Path:
        """Ensure the venv exists, without reinstalling if it already does.

        Unlike ensure_venv(), this never re-verifies or reinstalls
        dependencies for an existing venv — it only checks that the
        directory is present. Intended for commands that just need
        somewhere to run from on every invocation (shell, invenio, test)
        rather than a full dependency sync each time. Falls through to the
        full ensure_venv() (real `uv venv` creation plus installs) when the
        venv directory doesn't exist yet.

        Args:
            requirements: Requirements to use if the venv needs to be created
            quiet: If True, suppress command output (for --quiet flag)

        Returns:
            Path to the virtual environment directory

        Raises:
            ValidationError: If requirements are invalid
            ProcessExecutionError: If uv commands fail
        """
        if self._venv_path.exists():
            return self._venv_path
        return self.ensure_venv(requirements, force=False, quiet=quiet)

    def upgrade_environment(self, requirements: VenvRequirements) -> None:
        """Clean cache and recreate venv from scratch.

        Removes the existing virtual environment and recreates it with fresh
        dependencies. Useful when dependencies become corrupted or outdated.

        Args:
            requirements: Requirements for the new environment
        """
        self.ensure_venv(requirements, force=True)

    def cleanup(self) -> None:
        """Remove virtual environment and related files.

        Deletes the entire virtual environment directory. Does not fail if
        the directory doesn't exist.
        """
        if self._venv_path.exists():
            shutil.rmtree(self._venv_path)

    def _is_valid_venv(self, venv_path: Path) -> bool:
        """Check whether a directory is a real, usable virtual environment.

        A directory merely existing (e.g. left behind by a crashed run, or
        a stray file) isn't enough to skip creation - look for `pyvenv.cfg`,
        the marker file both stdlib `venv` and `uv venv` write on creation.

        Args:
            venv_path: Path to check

        Returns:
            True if the directory looks like a real virtual environment
        """
        return (venv_path / "pyvenv.cfg").exists()

    def _create_venv(self, python: str, path: Path, quiet: bool = False) -> None:
        """Create fresh virtual environment using uv.

        Args:
            python: Python executable path or name (e.g., "python3.14")
            path: Path where the venv should be created
            quiet: If True, suppress command output

        Raises:
            ProcessExecutionError: If uv venv command fails
        """
        process.run(
            ["uv", "venv", "--python", python, "--seed", str(path)],
            cwd=self._project_root,
            check=True,
            interactive=not quiet,
        )

    def _install_dependencies(
        self,
        requirements: VenvRequirements,
        venv_path: Path,
        quiet: bool = False,
    ) -> None:
        """Install OARepo and project dependencies.

        Installs dependencies in this order:
        1. setuptools (required by uv pip)
        2. oarepo with version constraint and extras
        3. project itself (editable or as wheel)

        Args:
            requirements: Requirements specifying what to install
            venv_path: Path to the virtual environment
            quiet: If True, suppress command output

        Raises:
            ProcessExecutionError: If any pip install command fails
        """
        # Get platform-specific paths
        bin_dir = self._platform.get_venv_bin_dir()
        python_exe = self._platform.get_venv_python()
        python_path = venv_path / bin_dir / python_exe

        # Install setuptools first (required by uv pip)
        process.run(
            [str(python_path), "-m", "pip", "install", "setuptools"],
            check=True,
            interactive=not quiet,
        )

        # Build oarepo version constraint and install
        if requirements.oarepo_version is not None:
            oarepo_constraint = self._build_oarepo_constraint(requirements)
            process.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    str(python_path),
                    "--prerelease",
                    "allow",
                    f"oarepo[{oarepo_constraint}]",
                ],
                check=True,
                interactive=not quiet,
            )

        # Install project itself
        if requirements.editable:
            self._install_editable(requirements, python_path, quiet=quiet)
        else:
            self._build_and_install_wheel(requirements, python_path, quiet=quiet)

    def _build_oarepo_constraint(self, requirements: VenvRequirements) -> str:
        """Build OARepo package constraint string.

        Creates a constraint like "rdm,tests,oarepo14" based on requirements.

        Args:
            requirements: Requirements with oarepo_version and extras

        Returns:
            Comma-separated constraint string
        """
        # Base extras always include rdm and tests
        constraint_parts = ["rdm", "tests"]

        # Add oarepo version extra
        if requirements.oarepo_version is not None:
            constraint_parts.append(f"oarepo{requirements.oarepo_version}")

        # Add any additional extras from requirements
        constraint_parts.extend(requirements.extras)

        return ",".join(constraint_parts)

    def _install_editable(
        self, requirements: VenvRequirements, python_path: Path, quiet: bool = False
    ) -> None:
        """Install project in editable mode.

        Args:
            requirements: Requirements with extras to install
            python_path: Absolute path to the venv's Python interpreter
            quiet: If True, suppress command output

        Raises:
            ProcessExecutionError: If pip install fails
        """
        # Build extras list
        extras = ["dev", "tests"]
        if requirements.oarepo_version is not None:
            extras.append(f"oarepo{requirements.oarepo_version}")
        extras.extend(requirements.extras)

        extras_str = ",".join(extras)

        process.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python_path),
                "--prerelease",
                "allow",
                "-e",
                f"{self._project_root}[{extras_str}]",
            ],
            check=True,
            interactive=not quiet,
        )

    def _build_and_install_wheel(
        self, requirements: VenvRequirements, python_path: Path, quiet: bool = False
    ) -> None:
        """Build wheel and install (non-editable mode).

        Args:
            requirements: Requirements with extras to install
            python_path: Absolute path to the venv's Python interpreter
            quiet: If True, suppress command output

        Raises:
            ProcessExecutionError: If build or install fails
        """
        # Clean dist directory if it exists
        dist_dir = self._project_root / "dist"
        if dist_dir.exists():
            shutil.rmtree(dist_dir)

        # Build wheel
        process.run(
            ["uv", "build", "--wheel", "--out-dir", str(dist_dir), str(self._project_root)],
            check=True,
            interactive=not quiet,
        )

        # Find the built wheel
        wheels = list(dist_dir.glob("*.whl"))
        if not wheels:
            msg = "No wheel found in dist/ after build"
            raise ValidationError(msg)

        wheel_path = wheels[0]

        # Build extras list
        extras = ["tests"]
        if requirements.oarepo_version is not None:
            extras.append(f"oarepo{requirements.oarepo_version}")
        extras.extend(requirements.extras)

        extras_str = ",".join(extras)

        # Install the wheel with extras
        process.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python_path),
                "--prerelease",
                "allow",
                f"{wheel_path}[{extras_str}]",
            ],
            check=True,
            interactive=not quiet,
        )
