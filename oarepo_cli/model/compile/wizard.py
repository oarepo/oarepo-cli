from oarepo_cli.model.compile.steps.compile import CompileWizardStep
from oarepo_cli.model.compile.steps.remove_previous import RemovePreviousModelStep
from oarepo_cli.wizard import Wizard
from oarepo_cli.wizard.docker import DockerRunner


class CompileModelWizard(Wizard):
    def __init__(self, runner: DockerRunner):
        super().__init__(
            RemovePreviousModelStep(),
            *runner.wrap_docker_steps(CompileWizardStep(), in_compose=False)
        )
