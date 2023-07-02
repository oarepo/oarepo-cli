from oarepo_cli.wizard import Wizard

from ...wizard.docker import DockerRunner
from .steps.uninstall import UnInstallLocalStep


class RemoveLocalWizard(Wizard):
    def __init__(self, runner: DockerRunner, *, site_support):
        self.site_support = site_support
        super().__init__(*runner.wrap_docker_steps(UnInstallLocalStep()))
