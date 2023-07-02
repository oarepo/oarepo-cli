from oarepo_cli.wizard import Wizard
from oarepo_cli.wizard.docker import DockerRunner

from .steps.uninstall import UnInstallModelStep


class UnInstallModelWizard(Wizard):
    def __init__(self, runner: DockerRunner, *, model_support, site_support):
        self.model_support = model_support
        self.site_support = site_support

        super().__init__(
            *runner.wrap_docker_steps(
                UnInstallModelStep(),
            ),
        )
