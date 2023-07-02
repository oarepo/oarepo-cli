from colorama import Fore, Style

from oarepo_cli.model.install.steps.alembic import CreateAlembicModelStep
from oarepo_cli.model.install.steps.install import InstallModelStep
from oarepo_cli.model.install.steps.test_model import RunTestsModelStep
from oarepo_cli.model.install.steps.update_index import UpdateSearchIndexModelStep
from oarepo_cli.wizard import RadioStep, Wizard
from oarepo_cli.wizard.docker import DockerRunner


class InstallModelWizard(Wizard):
    def __init__(self, runner: DockerRunner, *, model_support, site_support):
        self.model_support = model_support
        self.site_support = site_support

        super().__init__(
            RadioStep(
                "run_tests",
                options={
                    "run": f"{Fore.GREEN}Run tests{Style.RESET_ALL}",
                    "skip": f"{Fore.RED}Skip tests{Style.RESET_ALL}",
                },
                default="run",
                heading=f"""
            Before installing the model, it is wise to run the test to check that the model is ok.
            If the tests fail, please fix the errors and run this command again.
                """,
                force_run=True,
            ),
            *runner.wrap_docker_steps(
                RunTestsModelStep(),
                InstallModelStep(),
                CreateAlembicModelStep(),
                UpdateSearchIndexModelStep(),
            ),
        )
