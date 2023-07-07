from oarepo_cli.wizard import Wizard
from oarepo_cli.wizard.docker import DockerRunner

from ..site.add.steps.link_env import LinkEnvStep
from ..site.add.steps.start_containers import StartContainersStep
from .steps.check_db import CheckDBStep
from .steps.check_dependencies import CheckDependenciesStep
from .steps.check_s3_location import CheckS3LocationStep
from .steps.check_search import CheckSearchStep
from .steps.check_site import CheckSiteStep
from .steps.check_ui import CheckUIStep
from .steps.check_venv import CheckVirtualenvStep
from .steps.develop_step import DevelopStep
from .steps.editor_support import EditorSupportStep


class DevelopWizard(Wizard):
    def __init__(self, runner: DockerRunner, *, site_support):
        self.site_support = site_support
        super().__init__(
            LinkEnvStep(),
            StartContainersStep(),
            *runner.wrap_docker_steps(
                CheckVirtualenvStep(),
                CheckDependenciesStep(),
                CheckSiteStep(),
                CheckUIStep(),
                CheckDBStep(),
                CheckSearchStep(),
                CheckS3LocationStep(),
                EditorSupportStep(),
            ),
            DevelopStep(),
        )
