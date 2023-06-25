from oarepo_cli.wizard import Wizard
from oarepo_cli.wizard.docker import DockerRunner

from .steps.uninstall import UnInstallUIStep


class UnInstallUIWizard(Wizard):
    def __init__(self, runner: DockerRunner, *, site_support):
        self.site_support = site_support

        super().__init__(
            *runner.wrap_docker_steps(
                UnInstallUIStep(),
            ),
        )
