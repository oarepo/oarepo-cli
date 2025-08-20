#
# Copyright (c) 2025 CESNET z.s.p.o.
#
# This file is a part of oarepo-cli (see https://github.com/oarepo/oarepo-cli).
#
# oarepo-cli is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
#
"""Commands for working with less components."""

import json
import re
import tempfile
from functools import partial
from pathlib import Path

from invenio_cli.commands import Commands
from invenio_cli.commands.steps import FunctionStep, Step
from invenio_cli.helpers.process import ProcessResponse, run_cmd


class LessComponentsCommands(Commands):
    """Commands for managing LESS components."""

    components: list[str]

    def register_less_components(self, theme_config_file: Path | None) -> list[Step]:
        """Return steps that register less components."""
        return [
            FunctionStep(
                self._collect_less_components, message="Collecting LESS components..."
            ),
            FunctionStep(
                partial(
                    self._register_less_components, theme_config_file=theme_config_file
                ),
                message="Registering LESS components...",
            ),
        ]

    def _collect_less_components(self) -> ProcessResponse:
        pkg_man = self.cli_config.python_package_manager
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as t:
            run_cmd(
                pkg_man.run_command("invenio", "oarepo", "less", "components", t.name)
            )
            self.components = list(set(json.load(t)["components"]))
        return ProcessResponse()

    def _register_less_components(
        self, theme_config_file: Path | None
    ) -> ProcessResponse:
        if theme_config_file is None:
            theme_config_file = (
                self.cli_config.project_path
                / "ui"
                / "branding"
                / "semantic-ui"
                / "less"
                / "theme.config"
            )
        if not theme_config_file.exists():
            raise FileNotFoundError(
                f"Theme configuration file {theme_config_file} does not exist."
            )
        theme_data = theme_config_file.read_text()
        for c in self.components:
            match = re.search("^@" + c, theme_data, re.MULTILINE)
            if not match:
                autoregistration_position = theme_data.index(
                    "/* --- autoregistration point, do not remove --- */"
                )
                theme_data = (
                    theme_data[:autoregistration_position]
                    + f"\n@{c}: 'default';\n"
                    + theme_data[autoregistration_position:]
                )
        theme_config_file.write_text(theme_data)
        return ProcessResponse()
