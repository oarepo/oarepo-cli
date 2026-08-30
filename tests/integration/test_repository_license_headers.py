# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for 'repository license-headers'.

Exercises the same services.license_headers.add_license_headers as
test_library_misc_commands.py's license-headers tests, but against a
multi-module uv_build project (see lint_project_multi_module), to confirm
headers are added across every module directory, not just the first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Typer CLI runner."""
    return CliRunner()


def test_repository_license_headers_help_displays(runner: CliRunner) -> None:
    """Test that 'repository license-headers --help' displays help text."""
    result = runner.invoke(app, ["repository", "license-headers", "--help"])

    assert result.exit_code == 0
    assert "license" in result.stdout.lower()


def test_repository_license_headers_adds_headers_across_modules(
    runner: CliRunner, lint_project_multi_module: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """'repository license-headers' adds SPDX headers in every module directory."""
    monkeypatch.chdir(lint_project_multi_module)

    common_module = lint_project_multi_module / "common" / "new_module.py"
    common_module.write_text(
        '"""A new module without a license header."""\n\n'
        "from __future__ import annotations\n\n\n"
        "def test() -> str:\n"
        '    """Return a test string."""\n'
        '    return "test"\n'
    )
    i18n_module = lint_project_multi_module / "i18n" / "new_module.py"
    i18n_module.write_text(
        '"""Another new module without a license header."""\n\n'
        "from __future__ import annotations\n\n\n"
        "def test() -> str:\n"
        '    """Return a test string."""\n'
        '    return "test"\n'
    )

    result = runner.invoke(app, ["repository", "license-headers", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0
    for module in (common_module, i18n_module):
        content = module.read_text()
        assert "spdx-filecopyrighttext" in content.lower()
        assert "spdx-license-identifier" in content.lower()


def test_repository_license_headers_uses_pyproject_organization(
    runner: CliRunner, lint_project_multi_module: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Organization defaults to [tool.oarepo-cli.license].organization from pyproject.toml.

    Confirms the CliConfig plumbing (already covered in isolation by
    tests/unit/test_config.py's pyproject-override tests) actually reaches
    add_license_headers, without needing --organization on the CLI.
    """
    monkeypatch.chdir(lint_project_multi_module)

    pyproject = lint_project_multi_module / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + '\n[tool.oarepo-cli.license]\norganization = "Acme Corp"\n')

    module = lint_project_multi_module / "common" / "new_module.py"
    module.write_text(
        '"""A new module without a license header."""\n\n'
        "from __future__ import annotations\n\n\n"
        "def test() -> str:\n"
        '    """Return a test string."""\n'
        '    return "test"\n'
    )

    result = runner.invoke(app, ["repository", "license-headers", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "Acme Corp" in module.read_text()


def test_repository_license_headers_requires_pyproject(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """'repository license-headers' fails cleanly when no pyproject.toml can be found."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["repository", "license-headers", "--quiet"])

    assert result.exit_code == 1
