import venv

import click as click
from colorama import Fore, Style

from oarepo_cli.cli.model.utils import ModelWizardStep
from oarepo_cli.cli.utils import with_config
from oarepo_cli.ui.wizard import Wizard, WizardStep
from oarepo_cli.ui.wizard.steps import RadioWizardStep
from oarepo_cli.utils import pip_install, run_cmdline


@click.command(
    name="compile",
    help="""
Compile model yaml file to invenio sources. Required arguments:
    <name>   ... name of the already existing model
""",
)
@click.argument("name", required=True)
@with_config(config_section=lambda name, **kwargs: ["models", name])
def compile_model(cfg=None, **kwargs):
    optional_steps = []
    model_dir = cfg.project_dir / "models" / cfg.section
    if (model_dir / "setup.cfg").exists():
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


class CompileWizardStep(ModelWizardStep, WizardStep):
    def after_run(self):
        venv_dir = self.data.project_dir / ".venv" / "oarepo-model-builder"
        venv_dir = venv_dir.absolute()
        if not venv_dir.exists():
            venv.main([str(venv_dir)])
            pip_install(venv_dir / "bin" / "pip", "OAREPO_MODEL_BUILDER_VERSION", "oarepo-model-builder==3.*", "https://github.com/oarepo/oarepo-model-builder")
            # "oarepo-model-builder-tests",

        # TODO: install plugins - but note, there might be error parsing the file as some includes might be handled by the plugin
        # TODO: support for tests
        # TODO: support for files
        # TODO: support for requests
        # TODO: support for relations
        # TODO: support for extended
        opts = []
        if self.data.get("merge_changes", None) == "overwrite":
            opts.append("--overwrite")

        run_cmdline(
            venv_dir / "bin" / "oarepo-compile-model",
            *opts,
            "-vvv",
            "model.yaml",
            cwd=self.model_dir,
        )

    def should_run(self):
        # always run as there is an optional step for merge/overwrite changes
        return True
