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
from .steps.run_in_container import RunInContainerStep
from .steps.start_containers import StartContainersStep


class AddSiteWizard(Wizard):
    def __init__(self, running_in_container, use_container):
        steps = []
        if not use_container:
            steps.extend([
                InstallSiteStep(),  # runs in userspace
            ])
        else:
            steps.extend([
                steps.append(RunInContainerStep('--step', 'InstallSiteStep'))
            ])
        if not running_in_container:
            steps.extend([
                LinkEnvStep(),              # runs in userspace
            ])
        if running_in_container or not use_container:
            steps.extend([
                CheckRequirementsStep(),    # runs in docker
                StartContainersStep(),      # runs in userspace
                ResolveDependenciesStep(),  # runs in docker
                InstallInvenioStep(),       # runs in docker
                CompileGUIStep(),           # runs in docker
                InitDatabaseStep(),         # runs in docker
                InitFilesStep(),            # runs in docker
                NextStepsStep(),            # in docker or in userspace
            ])
        if use_container and not running_in_container:
            steps.append(RunInContainerStep())
        super().__init__(
            *steps
        )
