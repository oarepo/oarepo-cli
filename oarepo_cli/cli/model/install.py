import os
import shutil
import venv
import re

import click as click
from colorama import Fore, Style
from setuptools.config import read_configuration

from oarepo_cli.cli.model.utils import ModelWizardStep
from oarepo_cli.cli.utils import PipenvInstallWizardStep, with_config
from oarepo_cli.ui.wizard import Wizard
from oarepo_cli.ui.wizard.steps import RadioWizardStep, WizardStep
from oarepo_cli.utils import commit_git, run_cmdline


@click.command(
    name="install",
    help="""
Install the model into the current site. Required arguments:
    <name>   ... name of the already existing model""",
)
@click.argument("name", required=True)
@with_config(config_section=lambda name, **kwargs: ["models", name])
def install_model(cfg=None, **kwargs):
    commit_git(
        cfg.project_dir,
        f"before-model-install-{cfg.section}",
        f"Committed automatically before model {cfg.section} has been installed",
    )
    wizard = Wizard(
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
        TestWizardStep(),
        InstallWizardStep(),
        AlembicWizardStep(),
        UpdateIndexWizardStep(),
    )
    wizard.run(cfg)
    commit_git(
        cfg.project_dir,
        f"after-model-install-{cfg.section}",
        f"Committed automatically after model {cfg.section} has been installed",
    )


class TestWizardStep(ModelWizardStep, WizardStep):
    def after_run(self):
        if self.data["run_tests"] == "skip":
            return
        model_dir = self.model_dir
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
                "OPENSEARCH_HOST": self.data.get(
                    "config.TEST_OPENSEARCH_HOST", "localhost"
                ),
                "OPENSEARCH_PORT": self.data.get("config.TEST_OPENSEARCH_PORT", "9400"),
            },
        )

    def should_run(self):
        return True


class InstallWizardStep(PipenvInstallWizardStep):
    folder = "models"


class AlembicWizardStep(ModelWizardStep):
    heading = f"""
    I will create/update the alembic migration steps so that you might later modify 
    the model and perform automatic database migrations. This command will write
    alembic steps (if the database layer has been modified) to the models' alembic directory.
                """
    pause = True

    def after_run(self):
        setup_cfg = read_configuration(self.model_dir / "setup.cfg")
        for alembic_config in setup_cfg["options"]["entry_points"]["invenio_db.models"]:
            branch, model_dir = [
                x.strip() for x in alembic_config.split("=", maxsplit=1)
            ]

            model_dir = model_dir.replace(".", os.sep)
            model_dir = self.model_dir / model_dir
            alembic_path = self.get_alembic_path(model_dir)
            if not alembic_path:
                print(
                    f"{Fore.RED}Alembic path not found for model in {model_dir}, "
                    f"so can not set up alembic. You will have to do it manually{Style.RESET_ALL}"
                )
            else:
                self.setup_alembic(branch, alembic_path)

    def get_alembic_path(self, model_dir):
        md = model_dir
        while md != self.model_dir:
            ap = md / "alembic"
            if ap.exists():
                return ap
            md = md.parent

    def setup_alembic(self, branch, alembic_path):
        filecount = len(list(alembic_path.iterdir()))
        revision_id_prefix = self.data['model_package']

        def rewrite_revision_file(file_suffix, new_id_number):
            files = list(alembic_path.iterdir())
            target_file = str([file_name for file_name in files if file_suffix in str(file_name)][0])
            id_start_index = target_file.rfind("/") + 1
            id_end_index = target_file.find(file_suffix)
            old_id = target_file[id_start_index:id_end_index]
            new_id = f"{revision_id_prefix}_{new_id_number}"
            with open(target_file, 'r') as f:
                file_text = f.read()
                file_text = file_text.replace(f"revision = '{old_id}'", f"revision = '{new_id}'")
            with open(target_file.replace(old_id, new_id), 'w') as f:
                f.write(file_text)
            os.remove(target_file)

        if filecount < 2:
            # alembic has not been initialized yet ...
            self.invenio_command("alembic", "upgrade", "heads")
            # create model branch
            self.invenio_command(
                "alembic",
                "revision",
                f"Create {branch} branch for {self.data['model_package']}.",
                "-b",
                branch,
                "-p",
                "dbdbc1b19cf2",
                "--empty",
            )


            rewrite_revision_file("_create_", "1")

            self.fix_sqlalchemy_utils(alembic_path)
            self.invenio_command("alembic", "upgrade", "heads")
            self.invenio_command(
                "alembic", "revision", "Initial revision.", "-b", branch
            )

            rewrite_revision_file("_initial_revision", "2") # the link to down-revision is created correctly after alembic upgrade heads on the corrected file, explicit rewrite of down-revision is not needed

            self.fix_sqlalchemy_utils(alembic_path)
            self.invenio_command("alembic", "upgrade", "heads")
        else:
            # alembic has been initialized, update heads and generate
            files = [file_path.name for file_path in alembic_path.iterdir()]

            file_numbers = []
            for file in files:
                file_number_regex = re.findall(f"(?<={revision_id_prefix}_)\d+", file)
                if file_number_regex:
                    file_numbers.append(int(file_number_regex[0]))
            new_file_number = max(file_numbers) + 1
            
            self.invenio_command("alembic", "upgrade", "heads")
            self.invenio_command(
                "alembic",
                "revision",
                "nrp-cli install revision.",
                "-b",
                branch,
            )

            rewrite_revision_file("_nrp_cli_install", new_file_number)

            self.fix_sqlalchemy_utils(alembic_path)
            self.invenio_command("alembic", "upgrade", "heads")

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

    def should_run(self):
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

    def after_run(self):
        setup_cfg = read_configuration(self.model_dir / "setup.cfg")
        for cmd_def in setup_cfg["options"]["entry_points"]["flask.commands"]:
            cmd_name, _ = [x.strip() for x in cmd_def.split("=", maxsplit=1)]
            break

        if self.data["update_opensearch"] == "run":
            self.invenio_command(cmd_name, "reindex", "--recreate")

    def should_run(self):
        return True
