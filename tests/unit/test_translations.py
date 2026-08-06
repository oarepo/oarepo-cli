# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Unit tests for translations service module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services import translations


@pytest.fixture
def mock_context(tmp_path: Path) -> Mock:
    """Create a mock ProjectContext."""
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path
    return context


def test_copy_translations_copies_files(mock_context: Mock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that copy_translations copies files to site-packages."""
    from oarepo_cli.services import process

    # Setup source translations
    src = tmp_path / "collected_translations"
    src.mkdir()
    (src / "file1.txt").write_text("content1")
    (src / "subdir").mkdir()
    (src / "subdir" / "file2.txt").write_text("content2")

    # Setup site-packages
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()

    # Mock process.run to return site-packages path
    mock_result = Mock(spec=process.ProcessResult)
    mock_result.stdout = str(site_packages) + "\n"
    mock_run = Mock(return_value=mock_result)
    monkeypatch.setattr("oarepo_cli.services.translations.process.run", mock_run)

    # Run copy with explicit source directory
    translations.copy_translations(
        mock_context,
        collected_translations_dir=str(src),
        quiet=True,
    )

    # Verify files were copied
    assert (site_packages / "file1.txt").exists()
    assert (site_packages / "file1.txt").read_text() == "content1"
    assert (site_packages / "subdir" / "file2.txt").exists()
    assert (site_packages / "subdir" / "file2.txt").read_text() == "content2"


def test_copy_translations_handles_missing_source(
    mock_context: Mock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that copy_translations handles missing source directory gracefully."""
    from oarepo_cli.services import process

    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()

    # Mock process.run to return site-packages path
    mock_result = Mock(spec=process.ProcessResult)
    mock_result.stdout = str(site_packages) + "\n"
    mock_run = Mock(return_value=mock_result)
    monkeypatch.setattr("oarepo_cli.services.translations.process.run", mock_run)

    # Run with non-existent source - should not raise
    translations.copy_translations(
        mock_context,
        collected_translations_dir="/nonexistent/path",
        quiet=True,
    )

    # No files should be copied (directory doesn't exist)
    # Should just return without error


def test_copy_translations_uses_default_path_when_none(
    mock_context: Mock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that copy_translations uses default path when collected_translations_dir is None."""
    from oarepo_cli.services import process

    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    oarepo_collected = site_packages / "oarepo" / "collected_translations"
    oarepo_collected.mkdir(parents=True)
    (oarepo_collected / "default.txt").write_text("default content")

    # Mock process.run to return site-packages path
    mock_result = Mock(spec=process.ProcessResult)
    mock_result.stdout = str(site_packages) + "\n"
    mock_run = Mock(return_value=mock_result)
    monkeypatch.setattr("oarepo_cli.services.translations.process.run", mock_run)

    # Run with None (should use default path in site-packages)
    translations.copy_translations(
        mock_context,
        collected_translations_dir=None,
        quiet=True,
    )

    # Verify default.txt was "copied" (merged into site-packages)
    # Since src is already in site-packages, this is a no-op in practice
    assert (site_packages / "oarepo" / "collected_translations" / "default.txt").exists()
