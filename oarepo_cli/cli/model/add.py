import os
from pathlib import Path

import click as click
from cookiecutter.main import cookiecutter

from oarepo_cli.config import MonorepoConfig
from oarepo_cli.ui.wizard import InputWizardStep, StaticWizardStep, Wizard, WizardStep
from oarepo_cli.ui.wizard.steps import RadioWizardStep
from oarepo_cli.utils import print_banner


@click.command(name="add", help="Generate a new model")
@click.option(
    "-p",
    "--project-dir",
    type=click.Path(exists=False, file_okay=False),
    default=lambda: os.getcwd(),
    callback=lambda ctx, param, value: Path(value).absolute(),
)
@click.argument("name")
def add_model(project_dir, name, *args, **kwargs):
    oarepo_yaml_file = project_dir / "oarepo.yaml"
    cfg = MonorepoConfig(oarepo_yaml_file, section=["models", name])
    cfg.load()
    print_banner()
    cfg["model_name"] = name

    add_model_wizard.run(cfg)


class CreateModelWizardStep(WizardStep):

    def after_run(self, data):
        base_model_package = {
            "empty": "(none)",
            "common": "nr-common-metadata-model-builder",
            "documents": "nr-documents-records-model-builder",
            "data": "TODO",
        }.get(data["model_kind"])
        base_model_use = base_model_package.replace("-model-builder", "")
        cookiecutter(
            "https://github.com/oarepo/cookiecutter-model",
            checkout="v10.0",
            no_input=True,
            output_dir=Path(data.get("config.project_dir")) / "models",
            extra_context={
                **data,
                "base_model_package": base_model_package,
                "base_model_use": base_model_use,
            },
        )


add_model_wizard = Wizard(
    StaticWizardStep(
        heading="""
Before creating the datamodel, I'll ask you a few questions.
If unsure, use the default value.
    """,
    ),
    InputWizardStep(
        "model_package",
        prompt="Enter the model package",
        default=lambda data: data["model_name"].replace("-", "_"),
    ),
    RadioWizardStep(
        "model_kind",
        heading="""
Now choose if you want to start from a completely empty model or if you
want to base your model on an already existing one. You have the following
options:

* common       - a common set of metadata created by the National library of Technology, Prague
                 compatible with Dublin Core
                 See https://github.com/Narodni-repozitar/nr-common-metadata for details
* documents    - extension of common, can be used to capture metadata of documents (articles etc.)
                 See https://github.com/Narodni-repozitar/nr-documents-records for details
* data         - extension of common for capturing generic metadata about datasets
                 See TODO for details
* custom_model - use any custom model as a base model. If you select this option, answer the next two questions
                 (base_model_package, base_model_use) as well
* empty_model  - just what it says, not recommended as you have no compatibility with
                 the Czech National Repository

When asked about the base_model_package: leave as is unless you have chosen a custom base model.
In that case enter the package name of the model builder extension on pypi which contains the custom model.

When asked about the base_model_use: leave as is unless you have chosen a custom base model.
In that case enter the string that should be put to 'oarepo:use. Normally that is the name
of the extension without 'model-builder-'. See the documentation of your custom model for details.
    """,
        options={
            "common": "Common set of metadata, DC compatible",
            "documents": "Based on Czech National Repository documents metadata",
            "data": "Based on Czech National Repository datasets metadata",
            "empty": "Just use empty model, I'll add the metadata myself",
        },
        default="common",
    ),
    StaticWizardStep(
        heading="""
Now tell me something about you. The defaults are taken from the monorepo, feel free to use them.
    """,
    ),
    InputWizardStep(
        "author_name",
        prompt="""Model author""",
        default=lambda data: data.get("config.author_name"),
    ),
    InputWizardStep(
        "author_email",
        prompt="""Model author's email""",
        default=lambda data: data.get("config.author_email"),
    ),
    StaticWizardStep(
        heading="Now I have all the information to generate your model. After pressing Enter, I will generate the sources",
        pause=True,
    ),
    CreateModelWizardStep(),
    StaticWizardStep(
        heading=lambda data: f"""
The model has been generated in the {Path(data.get('config.project_dir')) / 'models' / data['model_name']} directory.
At first, edit the metadata.yaml and then run "oarepo-cli model compile {data['model_name']}"
and to install to the site run "oarepo-cli model install {data['model_name']}".
                     """,
        pause=True,
    ),
)
