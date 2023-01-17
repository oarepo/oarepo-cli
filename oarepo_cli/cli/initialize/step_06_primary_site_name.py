from __future__ import annotations

from oarepo_cli.ui.wizard import WizardStep
from oarepo_cli.ui.wizard.steps import InputWizardStep


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

    def should_run(self):
        return "primary_site_name" not in self.data
