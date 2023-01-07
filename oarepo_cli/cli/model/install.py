import json
import os
import shutil
import venv
from pathlib import Path

import click as click
import tomlkit
from colorama import Fore, Style

from oarepo_cli.cli.model.utils import ModelWizardStep, get_model_dir, load_model_repo
from oarepo_cli.ui.wizard import Wizard
from oarepo_cli.ui.wizard.steps import RadioWizardStep, WizardStep
from oarepo_cli.utils import add_to_pipfile_dependencies, run_cmdline


@click.command(name="install", help="Install the model into the current site")
@click.option(
    "-p",
    "--project-dir",
    type=click.Path(exists=False, file_okay=False),
    default=lambda: os.getcwd(),
)
@click.argument("model-name", required=False)
def install_model(project_dir, model_name, *args, **kwargs):
    cfg, project_dir = load_model_repo(model_name, project_dir)

    sites = cfg.whole_data.get("sites", {})
    if not sites:
        print(
            "Please install the site before running the command (oarepo-cli site add)"
        )
        return

    config_steps = [
        RadioWizardStep(
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
    ]

    if len(sites) == 1:
        cfg["installation_site"] = next(iter(sites))
    else:
        config_steps.append(
            RadioWizardStep(
                "installation_site",
                options={
                    x: f"{Fore.GREEN}{x}{Style.RESET_ALL}"
                    for x in cfg.whole_data["sites"]
                },
                default=next(iter(cfg.whole_data["sites"])),
                heading=f"""
        Select the site where you want to install the model to.
            """,
                force_run=True,
            )
        )

    wizard = Wizard(
        *config_steps,
        TestWizardStep(),
        InstallWizardStep(),
        AlembicWizardStep(),
        UpdateIndexWizardStep(),
    )
    wizard.run(cfg)


class TestWizardStep(WizardStep):
    def after_run(self, data):
        if data["run_tests"] == "skip":
            return
        model_dir = get_model_dir(data)
        venv_dir = model_dir / ".venv-test"
        if venv_dir.exists():
            shutil.rmtree(venv_dir)

        venv.main([str(venv_dir)])
        pip_binary = venv_dir / "bin" / "pip"
        pytest_binary = venv_dir / "bin" / "pytest"

        run_cmdline(
            pip_binary, "install", "-U", "--no-input", "setuptools", "pip", "wheel"
        )
        run_cmdline(
            pip_binary, "install", "--no-input", "-e", ".[tests]", cwd=model_dir
        )

        run_cmdline(
            pytest_binary,
            "tests",
            cwd=model_dir,
            environ={
                "OPENSEARCH_HOST": data.get("config.TEST_OPENSEARCH_HOST", "localhost"),
                "OPENSEARCH_PORT": data.get("config.TEST_OPENSEARCH_PORT", "9400"),
            },
        )

    def should_run(self, data):
        return True


class InstallWizardStep(ModelWizardStep):
    heading = f"""
    Now I will add the model to site's Pipfile (if it is not there yet)
    and will run pipenv lock & install.
        """
    pause = True

    def after_run(self, data):
        # add package to pipfile
        self.add_model_to_pipfile(data)
        self.install_pipfile(data)

    def add_model_to_pipfile(self, data):
        pipfile = self.site_dir(data) / "Pipfile"
        add_to_pipfile_dependencies(
            pipfile, self.model_name(data), f"../../models/{self.model_name(data)}"
        )

    def install_pipfile(self, data):
        self.pipenv_command(data, "lock")
        self.pipenv_command(data, "install")

    def should_run(self, data):
        return True


class AlembicWizardStep(ModelWizardStep):
    heading = f"""
    I will create/update the alembic migration steps so that you might later modify 
    the model and perform automatic database migrations. This command will write
    alembic steps (if the database layer has been modified) to the models' alembic directory.
                """
    pause = True

    def after_run(self, data):
        model_package = data["model_package"]
        model_package_dir = self.model_package_dir(data)
        alembic_path = model_package_dir / "alembic"
        filecount = len(list(alembic_path.iterdir()))

        if filecount < 2:
            # alembic has not been initialized yet ...
            self.invenio_command(data, "alembic", "upgrade", "heads")
            # create model branch
            self.invenio_command(
                data,
                "alembic",
                "revision",
                f"Create {model_package} branch.",
                "-b",
                model_package,
                "-p",
                "dbdbc1b19cf2",
                "--empty",
            )
            self.invenio_command(data, "alembic", "upgrade", "heads")
            self.invenio_command(
                data, "alembic", "revision", "Initial revision.", "-b", model_package
            )
            self.fix_sqlalchemy_utils(alembic_path)
            self.invenio_command(data, "alembic", "upgrade", "heads")
        else:
            # alembic has been initialized, update heads and generate
            self.invenio_command(data, "alembic", "upgrade", "heads")
            self.invenio_command(
                data,
                "alembic",
                "revision",
                "oarepo-cli install revision.",
                "-b",
                model_package,
            )
            self.fix_sqlalchemy_utils(alembic_path)
            self.invenio_command(data, "alembic", "upgrade", "heads")

    def fix_sqlalchemy_utils(self, alembic_path):
        for fn in alembic_path.iterdir():
            data = fn.read_text()

            empty_migration = '''
def upgrade():
    """Upgrade database."""
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###'''

            if empty_migration in data:
                print(
                    f"{Fore.YELLOW}Found empty migration in file {fn}, deleting it{Style.RESET_ALL}"
                )
                fn.unlink()
                continue

            modified = False
            if "import sqlalchemy_utils" not in data:
                data = "import sqlalchemy_utils\n" + data
                modified = True
            if "import sqlalchemy_utils.types" not in data:
                data = "import sqlalchemy_utils.types\n" + data
                modified = True
            if modified:
                fn.write_text(data)

    def should_run(self, data):
        return True


class UpdateIndexWizardStep(ModelWizardStep):

    steps = (
        RadioWizardStep(
            "update_opensearch",
            options={
                "run": f"{Fore.GREEN}Update opensearch index{Style.RESET_ALL}",
                "skip": f"{Fore.RED}Do not update opensearch index{Style.RESET_ALL}",
            },
            default="run",
            heading=f"""
Before the model can be used, I need to create index inside opensearch server.
This is not necessary if the model has not been changed. Should I create/update
the index? 
                            """,
            force_run=True,
        ),
    )

    def after_run(self, data):
        if data["update_opensearch"] == "run":
            self.invenio_command(data, self.model_name(data), "reindex", "--recreate")

    def should_run(self, data):
        return True
