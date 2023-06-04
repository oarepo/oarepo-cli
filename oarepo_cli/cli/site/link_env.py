from __future__ import annotations

import datetime
import os
import re

from oarepo_cli.cli.site.utils import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep, InputStep, RadioStep, StaticStep
from ..utils import ProjectWizardMixin
from ...package_versions import SITE_COOKIECUTTER_REPO, SITE_COOKIECUTTER_VERSION

from ...utils import commit_git, get_cookiecutter_source


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
