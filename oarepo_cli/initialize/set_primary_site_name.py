from __future__ import annotations

from oarepo_cli.utils import commit_git
from oarepo_cli.wizard import WizardStep
from oarepo_cli.wizard.steps import InputStep


class PrimarySiteNameStep(WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            InputStep(
                "primary_site_name",
                prompt="""Directory name of your site (keep the default if unsure)""",
                default=lambda data: data["project_package"].replace("_", "-")
                + "-site",
            ),
            **kwargs,
        )

    def after_run(self):
        super().after_run()
        commit_git(
            self.data.project_dir,
            "after-primary-site-name",
            "Committed automatically after primary site name has been selected",
        )

    def should_run(self):
        return "primary_site_name" not in self.data