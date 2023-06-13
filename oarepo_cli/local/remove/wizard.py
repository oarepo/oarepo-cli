from oarepo_cli.wizard import Wizard

from .steps.install import InstallToSiteStep
from .steps.remove_local import RemoveLocalWizardStep


class RemoveLocalWizard(Wizard):
    def __init__(self):
        super().__init__(
            RemoveLocalWizardStep(),
            InstallToSiteStep(),
        )
