import json
import os
import re
from pathlib import Path

import click as click
from cookiecutter.main import cookiecutter

from oarepo_cli.cli.model.utils import ProjectWizardMixin
from oarepo_cli.config import MonorepoConfig
from oarepo_cli.ui.wizard import StaticWizardStep, Wizard
from oarepo_cli.ui.wizard.steps import InputWizardStep, RadioWizardStep, WizardStep
from oarepo_cli.utils import print_banner


@click.command(
    name="add",
    help="Generate a new UI. Invoke this command with the name of the user interface",
)
@click.option(
    "-p",
    "--project-dir",
    type=click.Path(exists=False, file_okay=False),
    default=lambda: os.getcwd(),
    callback=lambda ctx, param, value: Path(value).absolute(),
)
@click.argument("name")
def add_ui(project_dir, name, *args, **kwargs):
    oarepo_yaml_file = project_dir / "oarepo.yaml"
    cfg = MonorepoConfig(oarepo_yaml_file, section=["uis", name])
    cfg.load()
    print_banner()
    if not (name.endswith("-ui") or name.endswith("-app")):
        name = name + "-ui"

    cfg["ui_name"] = name

    add_ui_wizard(cfg).run(cfg)


def get_available_models(data):
    known_models = {
        # TODO: model description while adding models
        x: x
        for x in data.whole_data.get("models", {}).keys()
    }
    return known_models


def snail_to_title(v):
    return "".join(ele.title() for ele in v.split("_"))


class AddUIWizardStep(ProjectWizardMixin, WizardStep):
    def model_defaults(self, data):
        ui_name = data["ui_name"]

        ui_package = ui_name.lower().replace("-", "_")
        ui_base = snail_to_title(ui_package)

        model_config = data.whole_data["models"][data["model_name"]]["config"]
        model_package = model_config["model_package"]

        data.setdefault("local_model_path", "../../models/" + data["model_name"])
        data.setdefault("model_package", model_package)
        model_file = (
            (
                self.project_dir(data)
                / "ui"
                / ui_name
                / data["local_model_path"]
                / model_package
                / "models"
                / "model.json"
            )
            .absolute()
            .resolve(strict=False)
        )
        with open(model_file) as f:
            model_description = json.load(f)

        model_resource_config = model_description["settings"]["python"][
            "record-resource-config-class"
        ]
        model_service = model_description["settings"]["python"][
            "proxies-current-service"
        ]

        data.setdefault("app_name", ui_name)
        data.setdefault("app_package", ui_package)
        data.setdefault("ext_name", f"{ui_base}AppExtension")
        data.setdefault("author", data.get("config.author_name", ""))
        data.setdefault("author_email", data.get("config.author_email", ""))
        data.setdefault("repository_url", "")
        # TODO: take this dynamically from the running model's Ext so that
        # TODO: it does not have to be specified here
        data.setdefault("resource", f"{ui_base}Resource")
        data.setdefault("resource_config", f"{ui_base}ResourceConfig")
        data.setdefault("api_config", model_resource_config)
        data.setdefault("api_service", model_service)

    def after_run(self, data):
        cookiecutter(
            "https://github.com/oarepo/cookiecutter-app",
            checkout="v10.0",
            no_input=True,
            output_dir=Path(data.get("config.project_dir")) / "ui",
            extra_context={
                **data,
            },
        )


def add_ui_wizard(data):
    return Wizard(
        StaticWizardStep(
            heading="""
A UI is a python package that displays the search, detail, edit, ... pages for a single
metadata model. At first you'll have to select the model for which the UI will be created
and then I'll ask you a couple of additional questions.
""",
        ),
        AddUIWizardStep(
            steps=[
                RadioWizardStep(
                    "model_name",
                    heading="""
    For which model do you want to generate the ui? 
    """,
                    options=get_available_models(data),
                ),
                "model_defaults",
            ]
        ),
        InputWizardStep(
            "url_prefix",
            prompt="On which url prefix will the UI reside? The prefix should like /something/: ",
            default=f"/{data['ui_name']}/",
        ),
    )
