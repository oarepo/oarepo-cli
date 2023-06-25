from oarepo_cli.initialize.steps.create_monorepo import CreateMonorepoStep
from oarepo_cli.initialize.steps.initialize_directory import MonorepoDirectoryStep
from oarepo_cli.initialize.steps.install_nrp_cli import InstallINRPCliStep
from oarepo_cli.wizard import StaticStep, Wizard


class InitializeWizard(Wizard):
    def __init__(self):
        super().__init__(
            StaticStep(
                """
            This command will initialize a new repository based on OARepo codebase (an extension of Invenio repository).
                    """,
                pause=True,
            ),
            MonorepoDirectoryStep(),
            CreateMonorepoStep(),
            InstallINRPCliStep(pause=True),
        )
