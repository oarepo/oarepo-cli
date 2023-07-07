from __future__ import annotations

import os

from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.utils import ProjectWizardMixin
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
        try:
            # try to unlink stale symlink - it also does not "exist" from pathlib point of view
            os.unlink(str(self.site_dir / ".env"))
        except:
            pass
        os.symlink("variables", str(self.site_dir / ".env"))

    def should_run(self):
        return not (self.site_dir / ".env").exists()
