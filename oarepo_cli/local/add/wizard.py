from oarepo_cli.wizard import Wizard

from ...site.site_support import SiteSupport
from ...wizard.docker import DockerRunner
from .steps.add_local import GitHubCloneWizardStep
from .steps.install import InstallToSiteStep


class AddLocalWizard(Wizard):
    def __init__(self, runner: DockerRunner, site_support: SiteSupport):
        self.site_support = site_support

        super().__init__(
            GitHubCloneWizardStep(),
            *runner.wrap_docker_steps(InstallToSiteStep()),
        )
