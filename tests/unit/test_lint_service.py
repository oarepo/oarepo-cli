# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Unit tests for oarepo_cli.services.lint.LintRunner.

Mocks process.run so these run fast against a fake ruff/ty, unlike
tests/integration/test_library_lint_format.py's real-tool coverage.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services import process
from oarepo_cli.services.lint import LintRunner


@pytest.fixture
def mock_context(tmp_path: Path) -> Mock:
    """A mock ProjectContext with real, empty code directories (so the
    license-header/future-annotations checks -- which glob real files --
    find nothing and don't block reaching the ty check step)."""
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path
    context.venv_path = tmp_path / ".venv"
    return context


def _fake_process_result(**overrides: object) -> process.ProcessResult:
    defaults: dict[str, object] = {
        "return_code": 0,
        "stdout": "",
        "stderr": "",
        "command": [],
        "cwd": Path(),
        "duration_ms": 0,
    }
    defaults.update(overrides)
    return process.ProcessResult(**defaults)  # type: ignore[arg-type]


def test_run_lint_ty_check_covers_every_module_directory(
    tmp_path: Path, mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ty check is invoked with every non-tests code directory, not just the first --
    regression test for a multi-module repository (Step 4.15): the old code only ever
    passed code_directories[0], which for a library (always a single source dir) is
    harmless, but for a repository's several module directories would silently skip
    all but the first."""
    common = tmp_path / "common"
    i18n = tmp_path / "i18n"
    ui = tmp_path / "ui"
    tests_dir = tmp_path / "tests"
    for directory in (common, i18n, ui, tests_dir):
        directory.mkdir()
    mock_context.code_directories = [common, i18n, ui, tests_dir]

    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> process.ProcessResult:
        calls.append(list(command))
        return _fake_process_result()

    monkeypatch.setattr("oarepo_cli.services.lint.process.run", fake_run)

    runner = LintRunner(context=mock_context, quiet=True)
    runner.run_lint()

    ty_call = next(call for call in calls if call[0].endswith("ty"))
    assert str(common) in ty_call
    assert str(i18n) in ty_call
    assert str(ui) in ty_call
    assert str(tests_dir) not in ty_call


def test_run_lint_ty_check_single_directory_matches_library_layout(
    tmp_path: Path, mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A library's usual single-source-dir-plus-tests layout still passes exactly
    that one source directory to ty, unchanged from before Step 4.15."""
    src = tmp_path / "src"
    tests_dir = tmp_path / "tests"
    src.mkdir()
    tests_dir.mkdir()
    mock_context.code_directories = [src, tests_dir]

    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> process.ProcessResult:
        calls.append(list(command))
        return _fake_process_result()

    monkeypatch.setattr("oarepo_cli.services.lint.process.run", fake_run)

    runner = LintRunner(context=mock_context, quiet=True)
    runner.run_lint()

    ty_call = next(call for call in calls if call[0].endswith("ty"))
    assert str(src) in ty_call
    assert str(tests_dir) not in ty_call
