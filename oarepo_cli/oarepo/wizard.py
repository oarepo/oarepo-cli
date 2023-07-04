from oarepo_cli.oarepo.steps.run_oarepo import RunOARepoStep
from oarepo_cli.wizard import Wizard
from oarepo_cli.wizard.docker import DockerRunner


class OARepoWizard(Wizard):
    def __init__(self, runner: DockerRunner, *, site_support, oarepo_args):
        self.site_support = site_support

        super().__init__(
            *runner.wrap_docker_steps(
                RunOARepoStep(oarepo_args),
            ),
        )
