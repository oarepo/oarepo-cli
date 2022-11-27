import logging

from oarepo_cli.ui.wizard import StaticWizardStep, Wizard
from .step_01_initialize_directory import DirectoryStep
from .step_02_deployment_type import DeploymentTypeStep
from .step_03_create_monorepo import CreateMonorepoStep
from .step_04_install_invenio_cli import InstallInvenioCliStep
from .step_05_install_oarepo_cli import InstallIOARepoCliStep
from .step_06_install_site import InstallSiteStep
from .step_07_start_containers import StartContainersStep
from .step_08_create_pipenv import CreatePipenvStep
from .step_10_init_database import InitDatabaseStep
from .step_09_install_invenio import InstallInvenioStep
from .step_11_next_steps import NextStepsStep

log = logging.getLogger("initialize")

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
    CreatePipenvStep(pause=True),
    InstallInvenioStep(pause=True),
    InitDatabaseStep(),
    NextStepsStep(pause=True)
)
