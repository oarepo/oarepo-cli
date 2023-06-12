from oarepo_cli.ui.install.steps.build_assets_step import BuildAssetsUIStep
from oarepo_cli.ui.install.steps.install_step import InstallUIStep
from oarepo_cli.utils import ProjectWizardMixin
from oarepo_cli.wizard import Wizard


class InstallWizard(ProjectWizardMixin, Wizard):
    def __init__(self):
        super().__init__(
            InstallUIStep(),
            BuildAssetsUIStep()
        )
