from oarepo_cli.model.compile.steps.compile import CompileWizardStep
from oarepo_cli.model.compile.steps.remove_previous import RemovePreviousModelStep
from oarepo_cli.wizard import Wizard


class CompileModelWizard(Wizard):
    def __init__(self):
        super().__init__(RemovePreviousModelStep(), CompileWizardStep())
