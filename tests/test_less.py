#
# Copyright (c) 2025 CESNET z.s.p.o.
#
# This file is a part of oarepo-cli (see https://github.com/oarepo/oarepo-cli).
#
# oarepo-cli is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
#

# tests/test_less_components_commands.py

import json
import re
from pathlib import Path

import pytest
from invenio_cli.helpers.process import ProcessResponse

from oarepo_cli.less import LessComponentsCommands


@pytest.fixture
def components_json(tmp_path):
    """Fixture that yields a JSON file with components list."""
    file = tmp_path / "components.json"
    data = {"components": ["componentA", "componentB", "componentC", "componentA"]}
    file.write_text(json.dumps(data))
    return file


@pytest.fixture
def mock_run_cmd(monkeypatch, components_json):
    """Mock run_cmd so it writes our prepared components.json content to the file path given."""

    def fake_run_cmd(cmd_args) -> ProcessResponse:
        # last argument is the temp JSON file created by _collect_less_components
        json_file_path = cmd_args[-1]
        # write the same content as our components_json fixture
        Path(json_file_path).write_text(components_json.read_text())
        return ProcessResponse()

    monkeypatch.setattr("oarepo_cli.less.run_cmd", fake_run_cmd)
    return fake_run_cmd


@pytest.fixture
def dummy_cli_config(tmp_path):
    """Minimal fake cli_config matching what LessComponentsCommands needs."""

    class DummyPkgManager:
        def run_command(self, *args: tuple) -> tuple:
            return args

    class DummyConfig:
        python_package_manager = DummyPkgManager()
        project_path = tmp_path

    return DummyConfig()


@pytest.fixture
def less_cmd(dummy_cli_config, mock_run_cmd):
    return LessComponentsCommands(dummy_cli_config)


def test_collect_less_components(less_cmd):
    resp = less_cmd._collect_less_components()  # noqa: SLF001
    assert isinstance(resp, ProcessResponse)
    assert sorted(less_cmd.components) == ["componentA", "componentB", "componentC"]  # deduplicated


def test_register_less_components_new_entries(tmp_path, less_cmd):
    theme_file = tmp_path / "theme.config"
    theme_file.write_text("/* --- autoregistration point, do not remove --- */\n")
    less_cmd.components = ["componentA", "componentB"]

    resp = less_cmd._register_less_components(theme_file)  # noqa: SLF001
    assert isinstance(resp, ProcessResponse)

    updated = theme_file.read_text()
    assert "@componentA:" in updated
    assert "@componentB:" in updated
    idx_marker = updated.index("/* --- autoregistration point, do not remove --- */")
    assert updated.index("@componentA:") < idx_marker
    assert updated.index("@componentB:") < idx_marker


def test_register_less_components_existing_entries(tmp_path, less_cmd):
    theme_file = tmp_path / "theme.config"
    theme_file.write_text("@componentA: 'default';\n/* --- autoregistration point, do not remove --- */\n")
    less_cmd.components = ["componentA"]

    resp = less_cmd._register_less_components(theme_file)  # noqa: SLF001
    assert isinstance(resp, ProcessResponse)

    updated = theme_file.read_text()
    # should not duplicate foo if already there
    assert len(re.findall(r"@componentA:", updated)) == 1


def test_register_less_components_file_not_found(tmp_path, less_cmd):
    missing = tmp_path / "nonexistent" / "theme.config"
    less_cmd.components = ["componentA"]
    with pytest.raises(FileNotFoundError):
        less_cmd._register_less_components(missing)  # noqa: SLF001


def test_register_less_components_default_path(tmp_path, less_cmd):
    default_theme = tmp_path / ".venv" / "var" / "instance" / "assets" / "less" / "theme.config"
    default_theme.parent.mkdir(parents=True, exist_ok=True)
    default_theme.write_text("/* --- autoregistration point, do not remove --- */\n")

    less_cmd.cli_config.project_path = tmp_path
    less_cmd.components = ["componentA"]

    resp = less_cmd._register_less_components(None)  # noqa: SLF001
    assert isinstance(resp, ProcessResponse)

    updated = default_theme.read_text()
    assert "@componentA:" in updated


def test_register_less_components_steps(less_cmd):
    from invenio_cli.commands.steps import FunctionStep

    steps = less_cmd.register_less_components(theme_config_file=Path("dummy"))
    assert len(steps) == 2
    assert isinstance(steps[0], FunctionStep)
    assert isinstance(steps[1], FunctionStep)
    assert steps[0].message == "Collecting LESS components..."
    assert steps[1].message == "Registering LESS components..."
