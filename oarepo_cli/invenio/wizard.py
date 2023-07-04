from oarepo_cli.invenio.steps.run_invenio import RunInvenioStep
from oarepo_cli.wizard import Wizard
from oarepo_cli.wizard.docker import DockerRunner


class InvenioWizard(Wizard):
    def __init__(self, runner: DockerRunner, *, site_support, invenio_args):
        self.site_support = site_support

        super().__init__(
            *runner.wrap_docker_steps(
                RunInvenioStep(invenio_args),
            ),
        )
