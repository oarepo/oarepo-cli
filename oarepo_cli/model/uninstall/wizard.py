from .steps.uninstall import UnInstallModelStep
from oarepo_cli.wizard import Wizard
from oarepo_cli.wizard.docker import DockerRunner


class UnInstallModelWizard(Wizard):
    def __init__(self, runner: DockerRunner):
        super().__init__(
            *runner.wrap_docker_steps(
                UnInstallModelStep(),
            ),
        )