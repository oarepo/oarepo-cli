from oarepo_cli.wizard import StaticStep, Wizard

from ...wizard.docker import DockerRunner
from .steps.add_ui import AddUIWizardStep
from .steps.jinja import CreateJinjaStep


class AddUIWizard(Wizard):
    def __init__(self, runner: DockerRunner, *, site_support):
        self.site_support = site_support
        super().__init__(
            StaticStep(
                heading="""
        A UI is a python package that displays the search, detail, edit, ... pages for a single
        metadata model. At first you'll have to select the model for which the UI will be created
        and then I'll ask you a couple of additional questions.
        """,
            ),
            AddUIWizardStep(),
            *runner.wrap_docker_steps(
                CreateJinjaStep(),
            )
        )
