import json
from os.path import relpath

import click as click

from oarepo_cli.cli.model.utils import ProjectWizardMixin
from oarepo_cli.cli.utils import with_config
from oarepo_cli.ui.wizard import StaticWizardStep, Wizard
from oarepo_cli.ui.wizard.steps import InputWizardStep, RadioWizardStep, WizardStep
from oarepo_cli.utils import get_cookiecutter_source, to_python_name
import os


@click.command(
    name="add",
    help="""Generate a new UI. Required arguments:
    <name>   ... name of the ui. The recommended pattern for it is <modelname>-ui
    """,
)
@click.argument("name")
@with_config(config_section=lambda name, **kwargs: ["ui", name])
def add_ui(cfg=None, **kwargs):
    add_ui_wizard(cfg).run(cfg)


class UIWizardMixin:
    @property
    def ui_name(self):
        return self.data.section

    @property
    def ui_dir(self):
        return self.data.project_dir / "ui" / self.ui_name


def available_models(data):
    known_models = {
        # TODO: model description while adding models
        x: x
        for x in data.whole_data.get("models", {}).keys()
    }
    return known_models


def snail_to_title(v):
    return "".join(ele.title() for ele in v.split("_"))


class AddUIWizardStep(UIWizardMixin, ProjectWizardMixin, WizardStep):
    def after_run(self):
        ui_name = self.ui_name

        ui_package = to_python_name(ui_name)
        ui_base = snail_to_title(ui_package)

        model_config = self.data.whole_data["models"][self.data["model_name"]]
        model_package = model_config["model_package"]

        model_path = self.data.project_dir / model_config["model_dir"]
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
            "model_name": self.data["model_name"],
            "local_model_path": self.data.get(
                "cookiecutter_local_model_path", relpath(model_path, self.ui_dir)
            ),
            "model_package": self.data.get("cookiecutter_model_package", model_package),
            "app_name": self.data.get("cookiecutter_app_name", ui_name),
            "app_package": self.data.get("cookiecutter_app_package", ui_package),
            "ext_name": self.data.get(
                "cookiecutter_ext_name", f"{ui_base}AppExtension"
            ),
            "author": self.data.get(
                "cookiecutter_author", model_config.get("author_name", "")
            ),
            "author_email": self.data.get(
                "cookiecutter_author_email", model_config.get("author_email", "")
            ),
            "repository_url": self.data.get("cookiecutter_repository_url", ""),
            # TODO: take this dynamically from the running model's Ext so that
            # TODO: it does not have to be specified here
            "resource": self.data.get("cookiecutter_resource", f"{ui_base}Resource"),
            "resource_config": self.data.get(
                "cookiecutter_resource_config", f"{ui_base}ResourceConfig"
            ),
            "api_config": self.data.get(
                "cookiecutter_api_config", model_resource_config
            ),
            "api_service": self.data.get("cookiecutter_api_service", model_service),
            "url_prefix": self.data["url_prefix"],
        }

        cookiecutter_path, cookiecutter_branch = get_cookiecutter_source("OAREPO_UI_COOKIECUTTER_VERSION", 
                                                                         "https://github.com/oarepo/cookiecutter-app", "v11.0", 
                                                                         master_version="master")

        self.run_cookiecutter(
            template=cookiecutter_path,
            config_file=f"ui-{ui_name}",
            checkout=cookiecutter_branch,
            output_dir=self.data.project_dir / "ui",
            extra_context=cookiecutter_data,
        )
        self.data["ui_dir"] = f"ui/{ui_name}"

    def should_run(self):
        return not self.ui_dir.exists()


def add_ui_wizard(data):
    available = available_models(data)
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
                    options=available,
                    default=next(iter(available)),
                ),
                InputWizardStep(
                    "url_prefix",
                    prompt="On which url prefix will the UI reside? The prefix should like /something/: ",
                    default=lambda data: f"/{data.section}/",
                ),
            ]
        ),
    )
