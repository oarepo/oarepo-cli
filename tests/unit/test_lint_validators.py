# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Unit tests for lint validation functions (license headers, future annotations)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from oarepo_cli.services.lint import check_future_annotations, check_license_headers

if TYPE_CHECKING:
    from pathlib import Path


def test_license_header_check_detects_missing(tmp_path: Path) -> None:
    """Test check_license_headers flags files without a license header."""
    (tmp_path / "src").mkdir()
    missing_file = tmp_path / "src" / "no_header.py"
    missing_file.write_text('"""No header here."""\n')
    has_header_file = tmp_path / "src" / "has_header.py"
    has_header_file.write_text('# SPDX-License-Identifier: MIT\n\n"""Has a header."""\n')

    missing = check_license_headers([tmp_path / "src"])

    assert missing == [missing_file]


def test_license_header_check_passes_with_header(tmp_path: Path) -> None:
    """Test check_license_headers returns nothing when all files have a header."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ok.py").write_text("# SPDX-License-Identifier: MIT\n")

    assert check_license_headers([tmp_path / "src"]) == []


def test_future_annotations_check_detects_missing(tmp_path: Path) -> None:
    """Test check_future_annotations flags files without the future import."""
    (tmp_path / "src").mkdir()
    missing_file = tmp_path / "src" / "no_future.py"
    missing_file.write_text('"""No future import."""\n')
    ok_file = tmp_path / "src" / "ok.py"
    ok_file.write_text('"""OK."""\n\nfrom __future__ import annotations\n')

    missing = check_future_annotations([tmp_path / "src"])

    assert missing == [missing_file]


def test_future_annotations_check_ignores_venv(tmp_path: Path) -> None:
    """Test check_future_annotations skips files under .venv/."""
    venv_dir = tmp_path / ".venv" / "lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "vendored.py").write_text('"""No future import, but vendored."""\n')

    assert check_future_annotations([tmp_path / ".venv"]) == []


def test_license_header_check_ignores_gitignored_files(tmp_path: Path) -> None:
    """Test check_license_headers skips files matched by the root .gitignore."""
    (tmp_path / ".gitignore").write_text("generated/\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "generated").mkdir()
    ignored_file = tmp_path / "src" / "generated" / "no_header.py"
    ignored_file.write_text('"""No header, but gitignored."""\n')
    tracked_file = tmp_path / "src" / "ok.py"
    tracked_file.write_text("# SPDX-License-Identifier: MIT\n")

    assert check_license_headers([tmp_path / "src"]) == []


def test_license_header_check_without_gitignore_checks_everything(tmp_path: Path) -> None:
    """Test check_license_headers behaves as before when no .gitignore exists.

    The `.git` marker bounds the upward search to `tmp_path`, so the result
    doesn't depend on whatever happens to live above it on the test machine.
    """
    (tmp_path / ".git").mkdir()
    (tmp_path / "src").mkdir()
    missing_file = tmp_path / "src" / "no_header.py"
    missing_file.write_text('"""No header here."""\n')

    assert check_license_headers([tmp_path / "src"]) == [missing_file]
