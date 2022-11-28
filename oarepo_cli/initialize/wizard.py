from initialize import (
    CreateMonorepoStep,
    CreatePipenvStep,
    DeploymentTypeStep,
    DirectoryStep,
    InitDatabaseStep,
    InstallInvenioCliStep,
    InstallInvenioStep,
    InstallIOARepoCliStep,
    InstallSiteStep,
    NextStepsStep,
    StartContainersStep,
)
from ui.wizard import StaticWizardStep, Wizard

initialize_wizard = Wizard(
    StaticWizardStep(
        "intro2",
        """
    This command will initialize a new repository based on OARepo codebase (an extension of Invenio repository).
            """,
        pause=True,
    ),
    DirectoryStep(),
    DeploymentTypeStep(),
    CreateMonorepoStep(pause=True),
    InstallInvenioCliStep(pause=True),
    InstallIOARepoCliStep(pause=True),
    InstallSiteStep(pause=True),
    StartContainersStep(pause=True),
    CreatePipenvStep(),
    InstallInvenioStep(pause=True),
    InitDatabaseStep(),
    NextStepsStep(pause=True),
)
