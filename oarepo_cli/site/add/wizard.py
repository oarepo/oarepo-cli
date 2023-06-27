from oarepo_cli.wizard import Wizard

from ...wizard.docker import DockerRunner
from ..site_support import SiteSupport
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
    def __init__(self, runner: DockerRunner, site_support: SiteSupport):
        self.site_support = site_support
        steps = []
        steps.extend(
            runner.wrap_docker_steps(
                InstallSiteStep(), in_compose=False, interactive=True
            )  # can run in plain docker
        )
        steps.append(LinkEnvStep())  # runs in userspace
        steps.extend(
            runner.wrap_docker_steps(
                CheckRequirementsStep(),  # can run in docker compose
            )
        )
        steps.append(StartContainersStep())  # runs in userspace
        steps.extend(
            runner.wrap_docker_steps(
                ResolveDependenciesStep(),  # can run in docker compose
                InstallInvenioStep(),  # can run in docker compose
                CompileGUIStep(),  # can run in docker compose
                InitDatabaseStep(),  # can run in docker compose
                InitFilesStep(),  # can run in docker compose
            )
        )
        steps.extend([NextStepsStep()])  # runs in userspace
        super().__init__(*steps)
