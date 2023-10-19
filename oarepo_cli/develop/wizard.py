from oarepo_cli.wizard import Wizard
from oarepo_cli.wizard.docker import DockerRunner
from .steps.create_vite import CreateViteStep
from .steps.vite_develop import ViteDevelopStep

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
from .steps.check_libraries import CheckLibrariesStep


class WebpackDevelopWizard(Wizard):
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


class ViteDevelopWizard(Wizard):
    def __init__(self, runner: DockerRunner, *, site_support, fast, libraries):
        self.site_support = site_support
        steps = []
        docker_steps = []
        if not fast:
            steps.extend(
                (
                    LinkEnvStep(),
                    StartContainersStep(),
                )
            )
            docker_steps.extend(
                (
                    CheckVirtualenvStep(),
                    CheckDependenciesStep(),
                    CheckLibrariesStep(libraries=libraries),
                    CheckSiteStep(),
                    CheckUIStep(),
                    CheckDBStep(),
                    CheckSearchStep(),
                    CheckS3LocationStep(),
                    CreateViteStep(),
                )
            )
        super().__init__(
            *steps,
            *(
                runner.wrap_docker_steps(
                    *docker_steps,
                    #     EditorSupportStep(),
                    interactive=True,
                    extra_mounts=libraries,
                )
                if docker_steps
                else []
            ),
            *runner.wrap_docker_steps(
                CheckLibrariesStep(libraries=libraries),
                ViteDevelopStep(),
                interactive=True,
                extra_mounts=libraries,
            ),
        )
