from oarepo_cli.utils import run_this_command_in_docker
from oarepo_cli.wizard import WizardStep


class RunInContainerStep(WizardStep):
    def __init__(self, extra_arguments=None):
        self.extra_arguments = extra_arguments or []

    def should_run(self):
        return True

    def after_run(self):
        run_this_command_in_docker(*self.extra_arguments)
