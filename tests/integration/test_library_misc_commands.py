# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for library miscellaneous commands."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app
from oarepo_cli.core.config import CliConfig
from oarepo_cli.core.context import ProjectContext

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Typer CLI runner."""
    return CliRunner()


def test_translations_help_displays(runner: CliRunner) -> None:
    """Test that 'library translations --help' displays help text."""
    result = runner.invoke(app, ["library", "translations", "--help"])

    assert result.exit_code == 0
    assert "translations" in result.stdout.lower()


def test_license_headers_help_displays(runner: CliRunner) -> None:
    """Test that 'library license-headers --help' displays help text."""
    result = runner.invoke(app, ["library", "license-headers", "--help"])

    assert result.exit_code == 0
    assert "license" in result.stdout.lower()


def test_jslint_help_displays(runner: CliRunner) -> None:
    """Test that 'library jslint --help' displays help text."""
    result = runner.invoke(app, ["library", "jslint", "--help"])

    assert result.exit_code == 0
    assert "jslint" in result.stdout.lower()


def test_jstest_help_displays(runner: CliRunner) -> None:
    """Test that 'library jstest --help' displays help text."""
    result = runner.invoke(app, ["library", "jstest", "--help"])

    assert result.exit_code == 0
    assert "jstest" in result.stdout.lower()


def test_jslint_skips_without_package_json(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library jslint' skips gracefully when no package.json exists."""
    monkeypatch.chdir(lint_project)

    result = runner.invoke(app, ["library", "jslint", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0


def test_license_headers_adds_headers(runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that 'library license-headers' adds SPDX headers to files missing them."""
    monkeypatch.chdir(lint_project)

    # Create a file without a license header
    module = lint_project / "src" / "cleanlib" / "new_module.py"
    module.write_text(
        '"""A new module without a license header."""\n\n'
        "from __future__ import annotations\n\n\n"
        "def test() -> str:\n"
        '    """Return a test string."""\n'
        '    return "test"\n'
    )

    result = runner.invoke(app, ["library", "license-headers", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0
    # Check that the file now has SPDX headers
    content = module.read_text()
    assert "spdx-filecopyrighttext" in content.lower()
    assert "spdx-license-identifier" in content.lower()


def test_license_headers_replaces_old_style_headers(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library license-headers' replaces old-style copyright with SPDX."""
    monkeypatch.chdir(lint_project)

    # Create a file with old-style copyright header
    module = lint_project / "src" / "cleanlib" / "old_style.py"
    module.write_text(
        "#\n"
        "# Copyright (c) 2025 CESNET z.s.p.o.\n"
        "#\n"
        "# This file is a part of oarepo-ui (see https://github.com/oarepo/oarepo-ui).\n"
        "#\n"
        "# oarepo-ui is free software; you can redistribute it and/or modify it\n"
        "# under the terms of the MIT License; see LICENSE file for more details.\n"
        "#\n\n\n"
        '"""A module with old-style license header."""\n\n'
        "from __future__ import annotations\n\n\n"
        "def test() -> str:\n"
        '    """Return a test string."""\n'
        '    return "test"\n'
    )

    result = runner.invoke(app, ["library", "license-headers", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0
    content = module.read_text()
    # Check that it has SPDX headers
    assert "spdx-filecopyrighttext: 2025 cesnet z.s.p.o" in content.lower()
    assert "spdx-license-identifier: mit" in content.lower()
    # Check that old-style header is removed
    assert "this file is a part of" not in content.lower()
    assert "oarepo-ui is free software" not in content.lower()
    # Check that the docstring and code are preserved
    assert '"""A module with old-style license header."""' in content
    assert "def test()" in content


def test_license_headers_adds_to_javascript(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library license-headers' adds SPDX headers to JavaScript files."""
    monkeypatch.chdir(lint_project)

    # Create a JavaScript file without a license header
    js_file = lint_project / "src" / "cleanlib" / "test.js"
    js_file.write_text('"use strict";\n\nfunction test() {\n  return "hello";\n}\n')

    result = runner.invoke(app, ["library", "license-headers", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0
    content = js_file.read_text()
    # Check that it has SPDX headers with // style comments
    assert "// spdx-filecopyrighttext:" in content.lower()
    assert "// spdx-license-identifier: mit" in content.lower()
    # Check that the code is preserved
    assert '"use strict"' in content
    assert "function test()" in content


def test_license_headers_adds_to_jinja(runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that 'library license-headers' adds SPDX headers to Jinja templates."""
    monkeypatch.chdir(lint_project)

    # Create a Jinja template without a license header
    jinja_file = lint_project / "src" / "cleanlib" / "template.html"
    jinja_file.write_text(
        "<!DOCTYPE html>\n<html>\n<head><title>Test</title></head>\n<body>{{ content }}</body>\n</html>\n"
    )

    result = runner.invoke(app, ["library", "license-headers", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0
    content = jinja_file.read_text()

    # Check that it has SPDX headers in a Jinja comment block
    assert "spdx-filecopyrighttext:" in content.lower()
    assert "spdx-license-identifier: mit" in content.lower()
    assert "{#" in content
    assert "#}" in content
    # Check that DOCTYPE is preserved at the start
    assert content.startswith("<!DOCTYPE html>")
    # Check that the template content is preserved
    assert "{{ content }}" in content

    # Verify format: DOCTYPE, then multi-line {# comment #}, then content
    lines = content.split("\n")
    assert lines[0] == "<!DOCTYPE html>"
    assert lines[1] == "{#"  # Start of multi-line comment
    assert "SPDX-FileCopyrightText" in lines[2]
    assert "SPDX-License-Identifier" in lines[3]
    assert lines[4] == "#}"  # End of multi-line comment


@pytest.fixture
def mock_library_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Mock discover_context() and venv-existence checks for shell/invenio commands.

    Allows library shell/invenio to reach their os.execve call without needing a real venv.
    """
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path
    context.venv_path = tmp_path / ".venv"
    context.python_binary = tmp_path / ".venv" / "bin" / "python3.14"
    context.oarepo_version = 14
    context.config = CliConfig()
    monkeypatch.setattr("oarepo_cli.cli.library.discover_context", lambda: context)
    monkeypatch.setattr(
        "oarepo_cli.cli.library.VirtualEnvironmentManager.ensure_venv_exists",
        lambda self, requirements, quiet=False: context.venv_path,  # noqa: ARG005
    )
    monkeypatch.setattr("oarepo_cli.cli.library.ServicesLifecycleManager.load_service_env", lambda _self: {})
    return context


def test_library_shell_applies_same_env_defaults_as_blocking_calls(
    runner: CliRunner, mock_library_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Library shell's exec'd environment gets OAREPO_ENV_DEFAULTS/venv-stripping.

    The environment gets the same OAREPO_ENV_DEFAULTS/venv-stripping treatment any
    process.run() call gets, rather than being built from bare os.environ, which
    would silently miss both.
    """
    monkeypatch.setenv("VIRTUAL_ENV", "/oarepo-cli/own/venv")
    monkeypatch.delenv("INVENIO_APP_THEME", raising=False)
    execve_calls = []
    monkeypatch.setattr(
        "oarepo_cli.cli.library.os.execve",
        lambda *args: execve_calls.append(args),
    )

    result = runner.invoke(app, ["library", "shell", "--skip-services"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    _bash_path, _argv, env = execve_calls[0]
    assert env["VIRTUAL_ENV"] == str(mock_library_context.venv_path)
    assert env["INVENIO_APP_THEME"] == '["semantic-ui"]'


def test_library_invenio_applies_same_env_defaults_as_blocking_calls(
    runner: CliRunner, mock_library_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Library invenio's exec'd environment gets OAREPO_ENV_DEFAULTS/venv-stripping.

    The environment gets the same OAREPO_ENV_DEFAULTS/venv-stripping treatment any
    process.run() call gets, rather than being built from bare os.environ, which
    would silently miss both.
    """
    invenio_path = mock_library_context.venv_path / "bin" / "invenio"
    invenio_path.parent.mkdir(parents=True)
    invenio_path.touch()
    monkeypatch.setenv("VIRTUAL_ENV", "/oarepo-cli/own/venv")
    monkeypatch.delenv("INVENIO_APP_THEME", raising=False)
    execve_calls = []
    monkeypatch.setattr(
        "oarepo_cli.cli.library.os.execve",
        lambda *args: execve_calls.append(args),
    )

    result = runner.invoke(app, ["library", "invenio", "--skip-services", "db", "upgrade"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    _invenio_path, _argv, env = execve_calls[0]
    assert env["VIRTUAL_ENV"] == str(mock_library_context.venv_path)
    assert env["INVENIO_APP_THEME"] == '["semantic-ui"]'
