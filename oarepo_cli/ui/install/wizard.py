from oarepo_cli.ui.install.steps.build_assets_step import BuildAssetsUIStep
from oarepo_cli.ui.install.steps.install_step import InstallUIStep
from oarepo_cli.utils import ProjectWizardMixin
from oarepo_cli.wizard import Wizard
from oarepo_cli.wizard.docker import DockerRunner


class InstallWizard(ProjectWizardMixin, Wizard):
    def __init__(self, runner: DockerRunner, *, site_support):
        self.site_support = site_support
        super().__init__(
            *runner.wrap_docker_steps(InstallUIStep(), BuildAssetsUIStep())
        )
