from oarepo_cli.wizard import Wizard

from .steps.check_requirements import CheckRequirementsStep
from .steps.compile_gui import CompileGUIStep
from .steps.init_database import InitDatabaseStep
from .steps.init_files import InitFilesStep
from .steps.install_invenio import InstallInvenioStep
from .steps.install_site import InstallSiteStep
from .steps.link_env import LinkEnvStep
from .steps.next_steps import NextStepsStep
from .steps.resolve_dependencies import ResolveDependenciesStep
from .steps.start_containers import StartContainersStep


class AddSiteWizard(Wizard):
    def __init__(self):
        super().__init__(
            InstallSiteStep(),
            LinkEnvStep(),
            CheckRequirementsStep(),
            StartContainersStep(),
            ResolveDependenciesStep(),
            InstallInvenioStep(),
            CompileGUIStep(),
            InitDatabaseStep(),
            InitFilesStep(),
            NextStepsStep(),
        )
