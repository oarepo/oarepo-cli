from oarepo_cli.ui.radio import Radio
from oarepo_cli.ui.wizard import WizardStep
from oarepo_cli.ui.wizard.validation import required


class DeploymentTypeStep(WizardStep):
    def __init__(self):
        super().__init__(
            Radio(
                name="packaging",
                options={
                    "single": "Build a single package out of all sources",
                    "multiple": "Build a separate package for each part of repository",
                },
                default="single",
            ),
            heading="""
Build a single python package from sources ("deployment" monorepo) or multiple packages?
Single package is the preferred choice unless you plan to share parts of repository
(such as metadata models, ui, ...) with other projects.            
            """,
            validate=[required("packaging")],
        )

    def should_run(self):
        return self.data.get("packaging") not in ("single", "multiple")
