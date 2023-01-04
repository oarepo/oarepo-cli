from __future__ import annotations

import shutil
import venv
from pathlib import Path

from oarepo_cli.ui.wizard import WizardStep
from oarepo_cli.ui.wizard.steps import InputWizardStep

from ...utils import run_cmdline, to_python_name


class PrimarySiteNameStep(WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            steps=[
                InputWizardStep(
                    "primary_site_name",
                    prompt="""Directory name of your site (keep the default if unsure)""",
                    default=lambda data: data["project_package"].replace("_", "-")
                    + "-site",
                )
            ],
            **kwargs,
        )

    def should_run(self, data):
        return super().should_run(data)
