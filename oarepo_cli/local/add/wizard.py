from oarepo_cli.wizard import Wizard

from .steps.add_local import GitHubCloneWizardStep
from .steps.install import InstallToSiteStep


class AddLocalWizard(Wizard):
    def __init__(self):
        super().__init__(
            GitHubCloneWizardStep(),
            InstallToSiteStep(),
        )
