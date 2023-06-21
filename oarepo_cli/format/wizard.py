from oarepo_cli.wizard import Wizard

from oarepo_cli.wizard.docker import DockerRunner
from .steps.format_python import FormatPythonStep


class FormatWizard(Wizard):
    def __init__(self, runner: DockerRunner):

        steps = []
        steps.extend(
            runner.wrap_docker_steps(FormatPythonStep(), in_compose=False)         # can run in plain docker
        )
        super().__init__(
            *steps
        )
