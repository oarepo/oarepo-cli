from oarepo_cli.develop.steps.check_dependencies import CheckDependenciesStep
from oarepo_cli.develop.steps.check_site import CheckSiteStep
from oarepo_cli.develop.steps.check_ui import CheckUIStep
from oarepo_cli.develop.steps.check_venv import CheckVirtualenvStep
from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.wizard import Wizard
from oarepo_cli.wizard.docker import DockerRunner


class BuildWizard(Wizard):
    def __init__(
        self, runner: DockerRunner, site_support: SiteSupport, production: bool
    ):
        self.site_support = site_support
        super().__init__(
            *runner.wrap_docker_steps(
                CheckVirtualenvStep(clean=True),
                CheckDependenciesStep(clean=False, require_up_to_date=production),
                CheckSiteStep(clean=True),
                CheckUIStep(production=production),
            ),
        )
