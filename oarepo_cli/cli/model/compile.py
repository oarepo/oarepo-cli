import os
import venv
from pathlib import Path

import click as click
from colorama import Fore, Style

from oarepo_cli.cli.model.utils import get_model_dir, load_model_repo
from oarepo_cli.ui.wizard import Wizard, WizardStep
from oarepo_cli.ui.wizard.steps import RadioWizardStep
from oarepo_cli.utils import run_cmdline


@click.command(name="compile", help="Compile model yaml file to invenio sources")
@click.option(
    "-p",
    "--project-dir",
    type=click.Path(exists=False, file_okay=False),
    default=lambda: os.getcwd(),
)
@click.argument("model-name", required=False)
def compile_model(project_dir, model_name, *args, **kwargs):
    cfg, project_dir = load_model_repo(model_name, project_dir)
    cfg.save_steps = False
    cfg["project_dir"] = project_dir
    optional_steps = []
    if (get_model_dir(cfg) / "setup.cfg").exists():
        optional_steps.append(
            RadioWizardStep(
                "merge_changes",
                options={
                    "merge": "Merge changes into the previously generated files",
                    "overwrite": "Remove previously generated files and start from scratch",
                },
                default="merge",
                heading=f"""
It seems that the model has been already generated. 

Should I try to {Fore.GREEN}merge{Fore.BLUE} the changes with the existing sources 
or {Fore.RED}remove{Fore.BLUE} the previously generated sources and generate from scratch?

{Fore.YELLOW}Please make sure that you have your existing sources safely committed into git repository
so that you might recover them if the compilation process fails.{Style.RESET_ALL}
""",
            )
        )
    wizard = Wizard(*optional_steps, CompileWizardStep())
    wizard.run(cfg)


class CompileWizardStep(WizardStep):
    def after_run(self, data):
        venv_dir = (
            Path(data.get("config.project_dir")) / ".venv" / "oarepo-model-builder"
        )
        venv_dir = venv_dir.absolute()
        if not venv_dir.exists():
            venv.main([str(venv_dir)])
            pip_binary = venv_dir / "bin" / "pip"

            run_cmdline(
                pip_binary, "install", "-U", "--no-input", "setuptools", "pip", "wheel"
            )
            run_cmdline(
                pip_binary,
                "install",
                "--no-input",
                "oarepo-model-builder>=1.0.0a4",
                "oarepo-model-builder-tests",
            )

        opts = []
        if data.get("merge_changes", None) == "overwrite":
            opts.append("--overwrite")

        run_cmdline(
            venv_dir / "bin" / "oarepo-compile-model",
            *opts,
            "-vvv",
            "model.yaml",
            cwd=get_model_dir(data),
        )
