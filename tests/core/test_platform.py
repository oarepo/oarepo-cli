# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for oarepo_cli.core.platform."""

from __future__ import annotations

from unittest.mock import patch

from oarepo_cli.core.platform import PlatformDetector, get_platform_detector


def test_platform_detector_is_macos_returns_true_on_darwin() -> None:
    """Test that is_macos() returns True when system is Darwin."""
    with patch("platform.system", return_value="Darwin"):
        detector = PlatformDetector()
        assert detector.is_macos() is True


def test_platform_detector_is_macos_returns_false_on_linux() -> None:
    """Test that is_macos() returns False when system is Linux."""
    with patch("platform.system", return_value="Linux"):
        detector = PlatformDetector()
        assert detector.is_macos() is False


def test_platform_detector_is_macos_returns_false_on_windows() -> None:
    """Test that is_macos() returns False when system is Windows."""
    with patch("platform.system", return_value="Windows"):
        detector = PlatformDetector()
        assert detector.is_macos() is False


def test_platform_detector_is_linux_returns_true_on_linux() -> None:
    """Test that is_linux() returns True when system is Linux."""
    with patch("platform.system", return_value="Linux"):
        detector = PlatformDetector()
        assert detector.is_linux() is True


def test_platform_detector_is_linux_returns_false_on_macos() -> None:
    """Test that is_linux() returns False when system is Darwin."""
    with patch("platform.system", return_value="Darwin"):
        detector = PlatformDetector()
        assert detector.is_linux() is False


def test_platform_detector_is_linux_returns_false_on_windows() -> None:
    """Test that is_linux() returns False when system is Windows."""
    with patch("platform.system", return_value="Windows"):
        detector = PlatformDetector()
        assert detector.is_linux() is False


def test_platform_detector_is_windows_returns_true_on_windows() -> None:
    """Test that is_windows() returns True when system is Windows."""
    with patch("platform.system", return_value="Windows"):
        detector = PlatformDetector()
        assert detector.is_windows() is True


def test_platform_detector_is_windows_returns_false_on_macos() -> None:
    """Test that is_windows() returns False when system is Darwin."""
    with patch("platform.system", return_value="Darwin"):
        detector = PlatformDetector()
        assert detector.is_windows() is False


def test_platform_detector_is_windows_returns_false_on_linux() -> None:
    """Test that is_windows() returns False when system is Linux."""
    with patch("platform.system", return_value="Linux"):
        detector = PlatformDetector()
        assert detector.is_windows() is False


def test_platform_detector_get_venv_bin_dir_returns_bin_on_unix() -> None:
    """Test that get_venv_bin_dir() returns 'bin' on Unix-like systems."""
    with patch("platform.system", return_value="Linux"):
        detector = PlatformDetector()
        assert detector.get_venv_bin_dir() == "bin"


def test_platform_detector_get_venv_bin_dir_returns_bin_on_macos() -> None:
    """Test that get_venv_bin_dir() returns 'bin' on macOS."""
    with patch("platform.system", return_value="Darwin"):
        detector = PlatformDetector()
        assert detector.get_venv_bin_dir() == "bin"


def test_platform_detector_get_venv_bin_dir_returns_scripts_on_windows() -> None:
    """Test that get_venv_bin_dir() returns 'Scripts' on Windows."""
    with patch("platform.system", return_value="Windows"):
        detector = PlatformDetector()
        assert detector.get_venv_bin_dir() == "Scripts"


def test_platform_detector_get_venv_python_returns_python_on_unix() -> None:
    """Test that get_venv_python() returns 'python' on Unix-like systems."""
    with patch("platform.system", return_value="Linux"):
        detector = PlatformDetector()
        assert detector.get_venv_python() == "python"


def test_platform_detector_get_venv_python_returns_python_on_macos() -> None:
    """Test that get_venv_python() returns 'python' on macOS."""
    with patch("platform.system", return_value="Darwin"):
        detector = PlatformDetector()
        assert detector.get_venv_python() == "python"


def test_platform_detector_get_venv_python_returns_python_exe_on_windows() -> None:
    """Test that get_venv_python() returns 'python.exe' on Windows."""
    with patch("platform.system", return_value="Windows"):
        detector = PlatformDetector()
        assert detector.get_venv_python() == "python.exe"


def test_platform_detector_needs_dyld_fix_returns_true_on_macos() -> None:
    """Test that needs_dyld_fix() returns True on macOS."""
    with patch("platform.system", return_value="Darwin"):
        detector = PlatformDetector()
        assert detector.needs_dyld_fix() is True


def test_platform_detector_needs_dyld_fix_returns_false_on_linux() -> None:
    """Test that needs_dyld_fix() returns False on Linux."""
    with patch("platform.system", return_value="Linux"):
        detector = PlatformDetector()
        assert detector.needs_dyld_fix() is False


def test_platform_detector_needs_dyld_fix_returns_false_on_windows() -> None:
    """Test that needs_dyld_fix() returns False on Windows."""
    with patch("platform.system", return_value="Windows"):
        detector = PlatformDetector()
        assert detector.needs_dyld_fix() is False


def test_platform_detector_get_celery_pool_recommendation_returns_threads_on_macos() -> None:
    """Test that get_celery_pool_recommendation() returns 'threads' on macOS."""
    with patch("platform.system", return_value="Darwin"):
        detector = PlatformDetector()
        assert detector.get_celery_pool_recommendation() == "threads"


def test_platform_detector_get_celery_pool_recommendation_returns_prefork_on_linux() -> None:
    """Test that get_celery_pool_recommendation() returns 'prefork' on Linux."""
    with patch("platform.system", return_value="Linux"):
        detector = PlatformDetector()
        assert detector.get_celery_pool_recommendation() == "prefork"


def test_platform_detector_get_celery_pool_recommendation_returns_prefork_on_windows() -> None:
    """Test that get_celery_pool_recommendation() returns 'prefork' on Windows."""
    with patch("platform.system", return_value="Windows"):
        detector = PlatformDetector()
        assert detector.get_celery_pool_recommendation() == "prefork"


def test_platform_detector_get_system_info_returns_correct_structure() -> None:
    """Test that get_system_info() returns a dictionary with all expected keys."""
    detector = PlatformDetector()
    info = detector.get_system_info()

    assert isinstance(info, dict)
    assert "system" in info
    assert "node" in info
    assert "release" in info
    assert "version" in info
    assert "machine" in info
    assert "python_version" in info


def test_platform_detector_get_system_info_system_matches_detection() -> None:
    """Test that get_system_info()['system'] matches is_* methods."""
    with patch("platform.system", return_value="Darwin"):
        detector = PlatformDetector()
        info = detector.get_system_info()
        assert info["system"] == "darwin"
        assert detector.is_macos() is True


def test_get_platform_detector_returns_instance() -> None:
    """Test that get_platform_detector() returns a PlatformDetector instance."""
    detector = get_platform_detector()
    assert isinstance(detector, PlatformDetector)


def test_get_platform_detector_returns_singleton() -> None:
    """Test that get_platform_detector() returns the same instance each time."""
    # Reset the global instance
    import oarepo_cli.core.platform as platform_module

    platform_module._detector = None  # noqa: SLF001

    detector1 = get_platform_detector()
    detector2 = get_platform_detector()

    assert detector1 is detector2


def test_get_default_shell_prefers_apple_silicon_homebrew_bash_on_macos() -> None:
    """Test that get_default_shell() prefers /opt/homebrew/bin/bash on macOS."""
    with (
        patch("platform.system", return_value="Darwin"),
        patch(
            "oarepo_cli.core.platform.Path.exists",
            new=lambda self: str(self) == "/opt/homebrew/bin/bash",
        ),
    ):
        detector = PlatformDetector()
        assert detector.get_default_shell() == "/opt/homebrew/bin/bash"


def test_get_default_shell_prefers_intel_homebrew_bash_on_macos() -> None:
    """Test that get_default_shell() falls back to /usr/local/bin/bash on macOS."""
    with (
        patch("platform.system", return_value="Darwin"),
        patch(
            "oarepo_cli.core.platform.Path.exists",
            new=lambda self: str(self) == "/usr/local/bin/bash",
        ),
    ):
        detector = PlatformDetector()
        assert detector.get_default_shell() == "/usr/local/bin/bash"


def test_get_default_shell_falls_back_to_system_bash_on_macos() -> None:
    """Test that get_default_shell() uses /bin/bash on macOS when no Homebrew bash exists."""
    with (
        patch("platform.system", return_value="Darwin"),
        patch(
            "oarepo_cli.core.platform.Path.exists",
            new=lambda self: str(self) == "/bin/bash",
        ),
    ):
        detector = PlatformDetector()
        assert detector.get_default_shell() == "/bin/bash"


def test_get_default_shell_skips_homebrew_check_on_linux() -> None:
    """Test that get_default_shell() doesn't look for Homebrew bash on Linux."""
    with (
        patch("platform.system", return_value="Linux"),
        patch(
            "oarepo_cli.core.platform.Path.exists",
            new=lambda self: str(self) == "/bin/bash",
        ),
    ):
        detector = PlatformDetector()
        assert detector.get_default_shell() == "/bin/bash"


def test_get_default_shell_falls_back_to_path_lookup() -> None:
    """Test that get_default_shell() searches PATH if no known bash path exists."""
    with (
        patch("platform.system", return_value="Linux"),
        patch("oarepo_cli.core.platform.Path.exists", return_value=False),
        patch("shutil.which", return_value="/usr/bin/bash"),
    ):
        detector = PlatformDetector()
        assert detector.get_default_shell() == "/usr/bin/bash"


def test_get_default_shell_falls_back_to_bare_name_if_not_found() -> None:
    """Test that get_default_shell() returns 'bash' as a last resort."""
    with (
        patch("platform.system", return_value="Linux"),
        patch("oarepo_cli.core.platform.Path.exists", return_value=False),
        patch("shutil.which", return_value=None),
    ):
        detector = PlatformDetector()
        assert detector.get_default_shell() == "bash"
