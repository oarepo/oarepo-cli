import os
import shutil
import venv
from pathlib import Path

import click as click
import tomlkit
from colorama import Fore, Style

from oarepo_cli.cli.model.utils import get_model_dir, load_model_repo
from oarepo_cli.ui.wizard import Wizard
from oarepo_cli.ui.wizard.steps import RadioWizardStep, WizardStep
from oarepo_cli.utils import run_cmdline


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
    cfg.save_steps = False
    cfg["project_dir"] = project_dir

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
        ),
        TestWizardStep(),
        InstallWizardStep(
            heading=f"""
Now I will add the model to site's Pipfile (if it is not there yet)
and will run pipenv lock & install.
    """,
            pause=True,
        ),
    )
    wizard.run(cfg)


class TestWizardStep(WizardStep):
    step_name = "test-step"

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

        run_cmdline(pytest_binary, "tests", cwd=model_dir)


class InstallWizardStep(WizardStep):
    step_name = "install-step"

    def after_run(self, data):
        # add package to pipfile
        self.add_model_to_pipfile(data)
        self.install_pipfile(data)

    @staticmethod
    def add_model_to_pipfile(data):
        model_name = data["model_name"]
        pipfile = (
            Path(data.get("config.project_dir"))
            / data.get("config.site_dir")
            / "Pipfile"
        )
        with open(pipfile, "r") as f:
            pipfile_data = tomlkit.load(f)
        for pkg in pipfile_data["packages"]:
            if pkg == model_name:
                break
        else:
            t = tomlkit.inline_table()
            t.comment("Added by oarepo-cli")
            t.update({"editable": True, "path": f"../models/{model_name}"})
            pipfile_data["packages"].add(tomlkit.nl())
            pipfile_data["packages"][model_name] = t
            pipfile_data["packages"].add(tomlkit.nl())

            with open(pipfile, "w") as f:
                tomlkit.dump(pipfile_data, f)

    @staticmethod
    def install_pipfile(data):
        site_dir = str(
            Path(data.get("config.project_dir")) / data.get("config.site_package")
        )
        run_cmdline(
            "pipenv", "lock", cwd=site_dir, environ={"PIPENV_IGNORE_VIRTUALENVS": "1"}
        )
        run_cmdline(
            "pipenv",
            "install",
            cwd=site_dir,
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
        )
