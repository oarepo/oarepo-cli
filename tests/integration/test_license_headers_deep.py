# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for 'license-headers --deep' (copyright years vs. git history)."""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

CURRENT_YEAR = datetime.now(UTC).year


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Typer CLI runner."""
    return CliRunner()


def _module(years: str) -> str:
    return (
        f"# SPDX-FileCopyrightText: {years} CESNET z.s.p.o.\n"
        "# SPDX-License-Identifier: MIT\n\n"
        '"""A module."""\n\n'
        "from __future__ import annotations\n"
    )


def _commit(root: Path, year: int, message: str) -> None:
    date = f"{year}-06-01T12:00:00+00:00"
    env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    for command in (
        ["git", "add", "-A"],
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "-m", message],
    ):
        subprocess.run(command, cwd=root, env=env, check=True, capture_output=True)  # noqa: S603 git is ok


def test_license_headers_deep_matching_years_exits_zero(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A header spanning first-commit..last-commit years passes."""
    monkeypatch.chdir(lint_project)
    module = lint_project / "src" / "cleanlib" / "__init__.py"
    module.write_text(_module("2020"))
    _commit(lint_project, 2020, "initial")
    module.write_text(_module("2020-2022") + "\nX = 1\n")
    _commit(lint_project, 2022, "modify")

    result = runner.invoke(app, ["library", "license-headers", "--deep", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert "LIC" not in result.output


def test_license_headers_deep_outdated_end_year_reports_issue(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A header not covering the latest modification year is reported with an editor location."""
    monkeypatch.chdir(lint_project)
    module = lint_project / "src" / "cleanlib" / "__init__.py"
    module.write_text(_module("2020"))
    _commit(lint_project, 2020, "initial")
    module.write_text(_module("2020") + "\nX = 1\n")
    _commit(lint_project, 2022, "modify")

    result = runner.invoke(app, ["library", "license-headers", "--deep", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 1
    assert f"LIC001 Wrong range, should be 2020-{CURRENT_YEAR}\n--> src/cleanlib/__init__.py:1:27" in result.output


def test_license_headers_deep_start_after_first_commit_reports_issue(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A header starting later than the file's first commit is reported."""
    monkeypatch.chdir(lint_project)
    module = lint_project / "src" / "cleanlib" / "__init__.py"
    module.write_text(_module("2020"))
    _commit(lint_project, 2020, "initial")
    module.write_text(_module("2022") + "\nX = 1\n")
    _commit(lint_project, 2022, "modify")

    result = runner.invoke(app, ["library", "license-headers", "--deep", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 1
    assert f"LIC001 Wrong range, should be 2020-{CURRENT_YEAR}" in result.output


def test_license_headers_deep_start_before_first_commit_is_accepted(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Code may predate the repository, so an earlier start year is not an error."""
    monkeypatch.chdir(lint_project)
    (lint_project / "src" / "cleanlib" / "__init__.py").write_text(_module("2018-2022"))
    _commit(lint_project, 2022, "initial")

    result = runner.invoke(app, ["library", "license-headers", "--deep", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0, result.output


def test_license_headers_deep_follows_renames(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """History from before a rename counts towards the renamed file."""
    monkeypatch.chdir(lint_project)
    old = lint_project / "src" / "cleanlib" / "old_name.py"
    old.write_text(_module("2020"))
    _commit(lint_project, 2020, "initial")
    old.rename(lint_project / "src" / "cleanlib" / "new_name.py")
    _commit(lint_project, 2022, "rename")

    result = runner.invoke(app, ["library", "license-headers", "--deep", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 1
    assert f"LIC001 Wrong range, should be 2020-{CURRENT_YEAR}\n--> src/cleanlib/new_name.py:1:27" in result.output


def test_license_headers_deep_uncommitted_changes_count_as_current_year(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Modified and untracked files must include the current year."""
    monkeypatch.chdir(lint_project)
    module = lint_project / "src" / "cleanlib" / "__init__.py"
    module.write_text(_module("2020"))
    _commit(lint_project, 2020, "initial")
    module.write_text(_module("2020") + "\nX = 1\n")
    (lint_project / "src" / "cleanlib" / "untracked.py").write_text(_module("2020"))

    result = runner.invoke(app, ["library", "license-headers", "--deep", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 1
    assert f"LIC001 Wrong range, should be 2020-{CURRENT_YEAR}\n--> src/cleanlib/__init__.py:1:27" in result.output
    assert f"LIC001 Wrong range, should be 2020-{CURRENT_YEAR}\n--> src/cleanlib/untracked.py:1:27" in result.output


def test_license_headers_deep_missing_year_reports_issue(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An SPDX header without a year is reported as LIC002."""
    monkeypatch.chdir(lint_project)
    (lint_project / "src" / "cleanlib" / "__init__.py").write_text(_module("").replace(": ", ":"))
    _commit(lint_project, 2020, "initial")

    result = runner.invoke(app, ["library", "license-headers", "--deep", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 1
    assert (
        f"LIC002 Missing copyright year, should be 2020-{CURRENT_YEAR}\n--> src/cleanlib/__init__.py:1:3"
        in result.output
    )


def test_repository_license_headers_deep_reports_issue(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """'repository license-headers --deep' runs the same check."""
    monkeypatch.chdir(lint_project)
    (lint_project / "src" / "cleanlib" / "__init__.py").write_text(_module("2020"))
    _commit(lint_project, 2022, "initial")

    result = runner.invoke(app, ["repository", "license-headers", "--deep", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 1
    assert f"LIC001 Wrong range, should be 2020-{CURRENT_YEAR}" in result.output


def test_license_headers_deep_header_only_changes_count_as_modifications(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Editing just the license header is a modification like any other."""
    monkeypatch.chdir(lint_project)
    module = lint_project / "src" / "cleanlib" / "__init__.py"
    module.write_text(_module("2019"))
    _commit(lint_project, 2020, "initial")
    module.write_text(_module("2018-2020"))
    _commit(lint_project, 2022, "edit header")

    result = runner.invoke(app, ["library", "license-headers", "--deep", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 1
    assert f"LIC001 Wrong range, should be 2018-{CURRENT_YEAR}" in result.output


def test_license_headers_fix_years_rewrites_single_holder(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--fix-years rewrites the range up to the current year; a following --deep run is clean."""
    monkeypatch.chdir(lint_project)
    module = lint_project / "src" / "cleanlib" / "__init__.py"
    module.write_text(_module("2020"))
    _commit(lint_project, 2020, "initial")
    module.write_text(_module("2020") + "\nX = 1\n")
    _commit(lint_project, 2022, "modify")

    result = runner.invoke(app, ["library", "license-headers", "--fix-years", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert module.read_text() == _module(f"2020-{CURRENT_YEAR}") + "\nX = 1\n"
    result = runner.invoke(app, ["library", "license-headers", "--deep", "--quiet"], catch_exceptions=False)
    assert result.exit_code == 0, result.output


def test_license_headers_fix_years_inserts_missing_year(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--fix-years adds the range to a header that has no year."""
    monkeypatch.chdir(lint_project)
    module = lint_project / "src" / "cleanlib" / "__init__.py"
    module.write_text(_module("").replace(":  ", ": "))
    _commit(lint_project, 2020, "initial")

    result = runner.invoke(app, ["repository", "license-headers", "--fix-years", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert module.read_text() == _module(f"2020-{CURRENT_YEAR}")


def test_license_headers_fix_years_skips_multiple_holders(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Files with several SPDX-FileCopyrightText lines are left untouched and still reported."""
    monkeypatch.chdir(lint_project)
    module = lint_project / "src" / "cleanlib" / "__init__.py"
    content = "# SPDX-FileCopyrightText: 2020 Someone Else\n" + _module("2020")
    module.write_text(content)
    _commit(lint_project, 2022, "initial")
    module.write_text(content + "\nX = 1\n")
    _commit(lint_project, 2023, "modify")

    result = runner.invoke(app, ["library", "license-headers", "--fix-years", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 1
    assert module.read_text() == content + "\nX = 1\n"
    assert (
        f"LIC001 Wrong range, should be 2020-{CURRENT_YEAR} (multiple copyright holders, fix manually)\n"
        "--> src/cleanlib/__init__.py:1:27"
    ) in result.output
