from oarepo_cli.wizard import Wizard
from oarepo_cli.wizard.docker import DockerRunner

from .steps.run_server import RunServerStep
from ..site.add.steps.link_env import LinkEnvStep


class RunSiteWizard(Wizard):
    def __init__(self, runner: DockerRunner, *, site_support):
        self.site_support = site_support
        super().__init__(
            LinkEnvStep(),
            *runner.wrap_docker_steps(
                RunServerStep(),
            ),
        )
