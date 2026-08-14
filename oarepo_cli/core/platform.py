# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Platform detection utilities for cross-platform compatibility."""

from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path


class PlatformDetector:
    """Abstract platform-specific behavior.

    Provides utilities for detecting the current operating system and
    determining platform-specific paths and behaviors.
    """

    def __init__(self) -> None:
        """Initialize the platform detector with the current platform."""
        self._system = platform.system().lower()

    def is_macos(self) -> bool:
        """Check if the current platform is macOS."""
        return self._system == "darwin"

    def is_linux(self) -> bool:
        """Check if the current platform is Linux."""
        return self._system == "linux"

    def is_windows(self) -> bool:
        """Check if the current platform is Windows."""
        return self._system == "windows"

    def get_venv_bin_dir(self) -> str:
        """Get the virtual environment bin directory name.

        Returns:
            'bin' on Unix-like systems (macOS, Linux), 'Scripts' on Windows.

        """
        if self.is_windows():
            return "Scripts"
        return "bin"

    def get_venv_python(self) -> str:
        """Get the Python executable name in a virtual environment.

        Returns:
            'python' on Unix-like systems, 'python.exe' on Windows.

        """
        if self.is_windows():
            return "python.exe"
        return "python"

    def get_default_shell(self) -> str:
        """Get the path to the preferred bash executable for interactive shells.

        On macOS, Apple ships a very old bash (3.2, frozen for licensing
        reasons) as /bin/bash. A Homebrew-installed bash is a modern
        version and is preferred when present: /opt/homebrew/bin/bash on
        Apple Silicon, /usr/local/bin/bash on Intel. Falls back to
        /bin/bash, then to whatever "bash" is found on PATH.

        Returns:
            Absolute path to the bash executable to use.

        """
        if self.is_macos():
            for homebrew_bash in (
                Path("/opt/homebrew/bin/bash"),
                Path("/usr/local/bin/bash"),
            ):
                if homebrew_bash.exists():
                    return str(homebrew_bash)

        system_bash = Path("/bin/bash")
        if system_bash.exists():
            return str(system_bash)

        found = shutil.which("bash")
        if found:
            return found

        return "bash"

    def needs_dyld_fix(self) -> bool:
        """Check if DYLD_LIBRARY_PATH fix is needed.

        On macOS, certain environment variables are stripped when spawning
        subprocesses. This method determines if special handling is required.

        Returns:
            True if running on macOS and dyld fix is needed.

        """
        return self.is_macos()

    def extra_env_vars(self) -> dict[str, str]:
        """Get extra environment variables to set on the platform.

        Returns:
            Dictionary of extra environment variables.

        """
        if self.needs_dyld_fix():
            dyld_path = Path("/opt/homebrew/lib")
            if dyld_path.exists():
                return {"DYLD_FALLBACK_LIBRARY_PATH": str(dyld_path)}
        return {}

    def get_celery_pool_recommendation(self) -> str:
        """Get the recommended Celery pool implementation for the platform.

        On macOS, the 'threads' pool is recommended due to process forking
        issues with the default 'prefork' pool.

        Returns:
            'threads' on macOS, 'prefork' on other platforms.

        """
        if self.is_macos():
            return "threads"
        return "prefork"

    def get_system_info(self) -> dict[str, str]:
        """Get detailed system information.

        Returns:
            Dictionary with platform details.

        """
        return {
            "system": self._system,
            "node": platform.node(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        }


# Singleton instance for platform detection
_detector: PlatformDetector | None = None


def get_platform_detector() -> PlatformDetector:
    """Get or create the global platform detector instance.

    Returns:
        The singleton PlatformDetector instance.

    """
    global _detector  # noqa: PLW0603 singleton
    if _detector is None:
        _detector = PlatformDetector()
    return _detector
