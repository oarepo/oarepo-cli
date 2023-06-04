from __future__ import annotations

from oarepo_cli.old_cli.utils import ProjectWizardMixin
from oarepo_cli.site.utils import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep


class LinkEnvStep(SiteWizardStepMixin, ProjectWizardMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
I link the "variables" file in the site directory to the .env file. 
If you'd like to make local changes to the variables, remove the link,
"cp variables .env" and edit the file.""",
            **kwargs,
        )

    def after_run(self):
        (self.site_dir / ".env").symlink_to(self.site_dir / "variables")

    def should_run(self):
        return not (self.site_dir / ".env").exists()
