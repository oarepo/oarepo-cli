# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

from __future__ import annotations

from unittest.mock import patch

from oarepo_cli.core.platform import PlatformDetector, get_platform_detector


class TestPlatformDetector:
    """Tests for the PlatformDetector class."""

    def test_is_macos_returns_true_on_darwin(self) -> None:
        """Test that is_macos() returns True when system is Darwin."""
        with patch("platform.system", return_value="Darwin"):
            detector = PlatformDetector()
            assert detector.is_macos() is True

    def test_is_macos_returns_false_on_linux(self) -> None:
        """Test that is_macos() returns False when system is Linux."""
        with patch("platform.system", return_value="Linux"):
            detector = PlatformDetector()
            assert detector.is_macos() is False

    def test_is_macos_returns_false_on_windows(self) -> None:
        """Test that is_macos() returns False when system is Windows."""
        with patch("platform.system", return_value="Windows"):
            detector = PlatformDetector()
            assert detector.is_macos() is False

    def test_is_linux_returns_true_on_linux(self) -> None:
        """Test that is_linux() returns True when system is Linux."""
        with patch("platform.system", return_value="Linux"):
            detector = PlatformDetector()
            assert detector.is_linux() is True

    def test_is_linux_returns_false_on_macos(self) -> None:
        """Test that is_linux() returns False when system is Darwin."""
        with patch("platform.system", return_value="Darwin"):
            detector = PlatformDetector()
            assert detector.is_linux() is False

    def test_is_linux_returns_false_on_windows(self) -> None:
        """Test that is_linux() returns False when system is Windows."""
        with patch("platform.system", return_value="Windows"):
            detector = PlatformDetector()
            assert detector.is_linux() is False

    def test_is_windows_returns_true_on_windows(self) -> None:
        """Test that is_windows() returns True when system is Windows."""
        with patch("platform.system", return_value="Windows"):
            detector = PlatformDetector()
            assert detector.is_windows() is True

    def test_is_windows_returns_false_on_macos(self) -> None:
        """Test that is_windows() returns False when system is Darwin."""
        with patch("platform.system", return_value="Darwin"):
            detector = PlatformDetector()
            assert detector.is_windows() is False

    def test_is_windows_returns_false_on_linux(self) -> None:
        """Test that is_windows() returns False when system is Linux."""
        with patch("platform.system", return_value="Linux"):
            detector = PlatformDetector()
            assert detector.is_windows() is False

    def test_get_venv_bin_dir_returns_bin_on_unix(self) -> None:
        """Test that get_venv_bin_dir() returns 'bin' on Unix-like systems."""
        with patch("platform.system", return_value="Linux"):
            detector = PlatformDetector()
            assert detector.get_venv_bin_dir() == "bin"

    def test_get_venv_bin_dir_returns_bin_on_macos(self) -> None:
        """Test that get_venv_bin_dir() returns 'bin' on macOS."""
        with patch("platform.system", return_value="Darwin"):
            detector = PlatformDetector()
            assert detector.get_venv_bin_dir() == "bin"

    def test_get_venv_bin_dir_returns_scripts_on_windows(self) -> None:
        """Test that get_venv_bin_dir() returns 'Scripts' on Windows."""
        with patch("platform.system", return_value="Windows"):
            detector = PlatformDetector()
            assert detector.get_venv_bin_dir() == "Scripts"

    def test_get_venv_python_returns_python_on_unix(self) -> None:
        """Test that get_venv_python() returns 'python' on Unix-like systems."""
        with patch("platform.system", return_value="Linux"):
            detector = PlatformDetector()
            assert detector.get_venv_python() == "python"

    def test_get_venv_python_returns_python_on_macos(self) -> None:
        """Test that get_venv_python() returns 'python' on macOS."""
        with patch("platform.system", return_value="Darwin"):
            detector = PlatformDetector()
            assert detector.get_venv_python() == "python"

    def test_get_venv_python_returns_python_exe_on_windows(self) -> None:
        """Test that get_venv_python() returns 'python.exe' on Windows."""
        with patch("platform.system", return_value="Windows"):
            detector = PlatformDetector()
            assert detector.get_venv_python() == "python.exe"

    def test_needs_dyld_fix_returns_true_on_macos(self) -> None:
        """Test that needs_dyld_fix() returns True on macOS."""
        with patch("platform.system", return_value="Darwin"):
            detector = PlatformDetector()
            assert detector.needs_dyld_fix() is True

    def test_needs_dyld_fix_returns_false_on_linux(self) -> None:
        """Test that needs_dyld_fix() returns False on Linux."""
        with patch("platform.system", return_value="Linux"):
            detector = PlatformDetector()
            assert detector.needs_dyld_fix() is False

    def test_needs_dyld_fix_returns_false_on_windows(self) -> None:
        """Test that needs_dyld_fix() returns False on Windows."""
        with patch("platform.system", return_value="Windows"):
            detector = PlatformDetector()
            assert detector.needs_dyld_fix() is False

    def test_get_celery_pool_recommendation_returns_threads_on_macos(self) -> None:
        """Test that get_celery_pool_recommendation() returns 'threads' on macOS."""
        with patch("platform.system", return_value="Darwin"):
            detector = PlatformDetector()
            assert detector.get_celery_pool_recommendation() == "threads"

    def test_get_celery_pool_recommendation_returns_prefork_on_linux(self) -> None:
        """Test that get_celery_pool_recommendation() returns 'prefork' on Linux."""
        with patch("platform.system", return_value="Linux"):
            detector = PlatformDetector()
            assert detector.get_celery_pool_recommendation() == "prefork"

    def test_get_celery_pool_recommendation_returns_prefork_on_windows(self) -> None:
        """Test that get_celery_pool_recommendation() returns 'prefork' on Windows."""
        with patch("platform.system", return_value="Windows"):
            detector = PlatformDetector()
            assert detector.get_celery_pool_recommendation() == "prefork"

    def test_get_system_info_returns_correct_structure(self) -> None:
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

    def test_get_system_info_system_matches_detection(self) -> None:
        """Test that get_system_info()['system'] matches is_* methods."""
        with patch("platform.system", return_value="Darwin"):
            detector = PlatformDetector()
            info = detector.get_system_info()
            assert info["system"] == "darwin"
            assert detector.is_macos() is True


class TestGetPlatformDetector:
    """Tests for the get_platform_detector() function."""

    def test_get_platform_detector_returns_instance(self) -> None:
        """Test that get_platform_detector() returns a PlatformDetector instance."""
        detector = get_platform_detector()
        assert isinstance(detector, PlatformDetector)

    def test_get_platform_detector_returns_singleton(self) -> None:
        """Test that get_platform_detector() returns the same instance each time."""
        # Reset the global instance
        import oarepo_cli.core.platform as platform_module

        platform_module._detector = None

        detector1 = get_platform_detector()
        detector2 = get_platform_detector()

        assert detector1 is detector2
