# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration test for ProjectContext.code_directories against the real, checked-in
tests/testrepo fixture -- a real repository project built with the uv_build backend's
multi-module [tool.uv.build-backend] layout, rather than a library's single
src/-or-package-dir layout.

Only reads testrepo_project's real pyproject.toml/directories -- no install, no
services, so it's safe to run alongside a real, separately-running repository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from oarepo_cli.core.context import ContextBuilder

if TYPE_CHECKING:
    from pathlib import Path


def test_code_directories_resolves_real_testrepo_uv_build_modules(
    testrepo_project: Path,
) -> None:
    """code_directories resolves testrepo's real [tool.uv.build-backend].module-name
    (["common", "i18n", "ui"]) rather than raising or guessing a single package dir."""
    context = ContextBuilder().from_directory(testrepo_project).validate()

    assert context.code_directories == [
        testrepo_project / "common",
        testrepo_project / "i18n",
        testrepo_project / "ui",
    ]
