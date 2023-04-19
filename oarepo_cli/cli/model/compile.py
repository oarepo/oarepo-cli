import venv

import click as click
from colorama import Fore, Style
import yaml

from oarepo_cli.cli.model.utils import ModelWizardStep
from oarepo_cli.cli.utils import with_config
from oarepo_cli.ui.wizard import Wizard, WizardStep
from oarepo_cli.ui.wizard.steps import RadioWizardStep
from oarepo_cli.utils import commit_git, pip_install, run_cmdline


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
    commit_git(
        cfg.project_dir,
        f"before-model-compile-{cfg.section}",
        f"Committed automatically before model {cfg.section} has been compiled",
    )
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
    commit_git(
        cfg.project_dir,
        f"after-model-compile-{cfg.section}",
        f"Committed automatically after model {cfg.section} has been compiled",
    )


class CompileWizardStep(ModelWizardStep, WizardStep):
    def after_run(self):
        venv_dir = self.data.project_dir / ".venv" / "oarepo-model-builder"
        venv_dir = venv_dir.absolute()
        if not venv_dir.exists():
            venv.main([str(venv_dir)])

        # TODO: install plugins - but note, there might be error parsing the file as some includes might be handled by the plugin
        pip_install(
            venv_dir / "bin" / "pip",
            "OAREPO_MODEL_BUILDER_VERSION",
            "oarepo-model-builder==3.*",
            "https://github.com/oarepo/oarepo-model-builder",
        )
        pip_install(
            venv_dir / "bin" / "pip",
            "OAREPO_MODEL_BUILDER_TESTS_VERSION",
            "oarepo-model-builder-tests==3.*",
            "https://github.com/oarepo/oarepo-model-builder-tests",
        )
        if self.data.get("use_requests", None) == "yes":
            pip_install(
                venv_dir / "bin" / "pip",
                "OAREPO_MODEL_BUILDER_REQUESTS_VERSION",
                "oarepo-model-builder-requests==3.*",
                "https://github.com/oarepo/oarepo-model-builder-requests",
            )
        if self.data.get("use_expandable_fields", None) == "yes":
            pip_install(
                venv_dir / "bin" / "pip",
                "OAREPO_MODEL_BUILDER_EXPANSIONS_VERSION",
                "oarepo-model-builder-expansions==3.*",
                "https://github.com/oarepo/oarepo-model-builder-expansions",
            )
        if self.data.get("use_files", None) == "yes":
            pip_install(
                venv_dir / "bin" / "pip",
                "OAREPO_MODEL_BUILDER_FILES_VERSION",
                "oarepo-model-builder-files==3.*",
                "https://github.com/oarepo/oarepo-model-builder-files",
            )

        if self.data.get("use_drafts", None) == "yes":
            pip_install(
                venv_dir / "bin" / "pip",
                "OAREPO_MODEL_BUILDER_DRAFTS_VERSION",
                "oarepo-model-builder-drafts==1.*",
                "https://github.com/oarepo/oarepo-model-builder-drafts",
            )

        if not self.data.get("use_drafts", None) == "yes":
            run_cmdline(
                venv_dir / "bin" / "pip",
                "uninstall",
                "-y",
                "oarepo-model-builder-drafts",
                cwd=self.model_dir,
            )

        if (
            self.data.get("use_relations", None) == "yes"
            or self.data.get("use_vocabularies", None) == "yes"
        ):
            pip_install(
                venv_dir / "bin" / "pip",
                "OAREPO_MODEL_BUILDER_RELATIONS_VERSION",
                "oarepo-model-builder-relations==1.*",
                "https://github.com/oarepo/oarepo-model-builder-relations",
            )
        if self.data.get("use_vocabularies", None) == "yes":
            pip_install(
                venv_dir / "bin" / "pip",
                "OAREPO_MODEL_BUILDER_VOCABULARIES_VERSION",
                "oarepo-model-builder-vocabularies==1.*",
                "https://github.com/oarepo/oarepo-model-builder-vocabularies",
            )
        if self.data.get("use_custom_fields", None) == "yes":
            pip_install(
                venv_dir / "bin" / "pip",
                "OAREPO_MODEL_BUILDER_FILES_VERSION",
                "oarepo-model-builder-cf==1.*",
                "https://github.com/oarepo/oarepo-model-builder-cf",
            )

        # TODO: install plugins - but note, there might be error parsing the file as some includes might be handled by the plugin
        with open(self.model_dir / "model.yaml") as f:
            model_data = yaml.safe_load(f)
        plugins = model_data.get("model", {}).get("plugins", {}).get("packages", [])
        for package in plugins:
            run_cmdline(
                venv_dir / "bin" / "pip",
                "install",
                package,
                cwd=self.model_dir,
            )

        opts = []

        if self.data.get("use_files", None) == "yes":
            opts.append("--profile")
            opts.append("model,files")

        if self.data.get("use_drafts", None) == "yes":
            opts.append("--profile")
            opts.append("model,drafts")

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
