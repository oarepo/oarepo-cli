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
from oarepo_cli.utils import print_banner, to_python_name
from os.path import relpath


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
    if not (name.endswith("ui") or name.endswith("app")):
        name = name + "-ui"

    oarepo_yaml_file = project_dir / "oarepo.yaml"
    cfg = MonorepoConfig(oarepo_yaml_file, section=["ui", name])
    cfg.load()
    print_banner()

    add_ui_wizard(cfg).run(cfg)


class UIWizardMixin:
    def ui_name(self, data):
        return data.section

    def ui_dir(self, data):
        return data.project_dir / "ui" / self.ui_name(data)


def get_available_models(data):
    known_models = {
        # TODO: model description while adding models
        x: x
        for x in data.whole_data.get("models", {}).keys()
    }
    return known_models


def snail_to_title(v):
    return "".join(ele.title() for ele in v.split("_"))


class AddUIWizardStep(UIWizardMixin, ProjectWizardMixin, WizardStep):
    def after_run(self, data):
        ui_name = self.ui_name(data)

        ui_package = to_python_name(ui_name)
        ui_base = snail_to_title(ui_package)

        model_config = data.whole_data["models"][data["model_name"]]
        model_package = model_config["model_package"]

        model_path = data.project_dir / model_config["model_dir"]
        model_file = (
            (model_path / model_package / "models" / "model.json")
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
        cookiecutter_data = {
            "model_name": data["model_name"],
            "local_model_path": data.get(
                "cookiecutter_local_model_path", relpath(model_path, self.ui_dir(data))
            ),
            "model_package": data.get("cookiecutter_model_package", model_package),
            "app_name": data.get("cookiecutter_app_name", ui_name),
            "app_package": data.get("cookiecutter_app_package", ui_package),
            "ext_name": data.get("cookiecutter_ext_name", f"{ui_base}AppExtension"),
            "author": data.get(
                "cookiecutter_author", model_config.get("author_name", "")
            ),
            "author_email": data.get(
                "cookiecutter_author_email", model_config.get("author_email", "")
            ),
            "repository_url": data.get("cookiecutter_repository_url", ""),
            # TODO: take this dynamically from the running model's Ext so that
            # TODO: it does not have to be specified here
            "resource": data.get("cookiecutter_resource", f"{ui_base}Resource"),
            "resource_config": data.get(
                "cookiecutter_resource_config", f"{ui_base}ResourceConfig"
            ),
            "api_config": data.get("cookiecutter_api_config", model_resource_config),
            "api_service": data.get("cookiecutter_api_service", model_service),
            "url_prefix": data["url_prefix"],
        }

        cookiecutter(
            "https://github.com/oarepo/cookiecutter-app",
            checkout="v10.0",
            no_input=True,
            output_dir=data.project_dir / "ui",
            extra_context=cookiecutter_data,
        )

    def should_run(self, data):
        return not self.ui_dir(data).exists()


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
                    default=next(iter(get_available_models(data))),
                ),
                InputWizardStep(
                    "url_prefix",
                    prompt="On which url prefix will the UI reside? The prefix should like /something/: ",
                    default=lambda data: f"/{data.section}/",
                ),
            ]
        ),
    )
