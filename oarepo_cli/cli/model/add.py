from pathlib import Path
import shutil
import click as click

from oarepo_cli.cli.model.utils import ModelWizardStep
from oarepo_cli.cli.utils import with_config
from oarepo_cli.ui.wizard import InputWizardStep, StaticWizardStep, Wizard, WizardStep
from oarepo_cli.ui.wizard.steps import RadioWizardStep
from oarepo_cli.utils import get_cookiecutter_source, to_python_name
import yaml
import os


@click.command(
    name="add",
    help="""
Generate a new model. Required arguments:
    <name>   ... name of the model, can contain [a-z] and dash (-)""",
)
@click.argument("name", required=True)
@with_config(config_section=lambda name, **kwargs: ["models", name])
def add_model(cfg=None, **kwargs):
    add_model_wizard.run(cfg)


class CreateModelWizardStep(ModelWizardStep, WizardStep):
    def after_run(self):
        model_dir = self.model_dir
        base_model_package = {
            "empty": "(none)",
            "common": "nr-common-metadata-model-builder",
            "documents": "nr-documents-records-model-builder",
            "data": "TODO",
        }.get(self.data["model_kind"])
        base_model_use = base_model_package.replace("-model-builder", "")

        cookiecutter_path, cookiecutter_branch = get_cookiecutter_source("OAREPO_MODEL_COOKIECUTTER_VERSION", 
                                                                         "https://github.com/oarepo/cookiecutter-model", "v11.0", 
                                                                         master_version="master")

        self.run_cookiecutter(
            template=cookiecutter_path,
            config_file=f"model-{model_dir.name}",
            checkout=cookiecutter_branch,
            output_dir=str(model_dir.parent),
            extra_context={
                **self.data,
                "model_name": model_dir.name,
                "base_model_package": base_model_package,
                "base_model_use": base_model_use,
            },
        )
        self.data["model_dir"] = str(model_dir.relative_to(self.data.project_dir))

    def should_run(self):
        return not self.model_dir.exists()


class InstallCustomModelWizardStep(ModelWizardStep, WizardStep):
    def should_run(self):
        custom_model = self.data.get("custom_model", None)
        return not not custom_model

    def after_run(self):
        custom_model_path: Path = self.data.project_dir.join(self.data["custom_model"])
        model_dir: Path = self.data.project_dir / self.data["model_dir"]
        shutil.copy(custom_model_path, model_dir / custom_model_path.name)
        # add to model
        metadata_file = model_dir / "metadata.yaml"
        model_data = yaml.safe_load(metadata_file.read_text())
        use_section = model_data.setdefault("oarepo:use", [])
        if custom_model_path.name not in use_section:
            use_section.append(custom_model_path.name)
            metadata_file.write_text(yaml.safe_dump(model_data))


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
        default=lambda data: to_python_name(data.section),
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
    InputWizardStep(
        "custom_model",
        default="",
        heading="""
If you already have a (custom) model file, please 
enter its path relative to the project directory.
The file will be copied into the model and used together 
with the base model selected in the previous step.
        """,
        required=False,
    ),
    StaticWizardStep(
        heading="""
Now tell me something about you. The defaults are taken from the monorepo, feel free to use them.
    """,
    ),
    InputWizardStep(
        "author_name",
        prompt="""Model author""",
        default=lambda data: get_site(data)["author_name"],
    ),
    InputWizardStep(
        "author_email",
        prompt="""Model author's email""",
        default=lambda data: get_site(data)["author_email"],
    ),
    StaticWizardStep(
        heading="Now I have all the information to generate your model. After pressing Enter, I will generate the sources",
        pause=True,
    ),
    CreateModelWizardStep(),
    InstallCustomModelWizardStep(),
    StaticWizardStep(
        heading=lambda data: f"""
The model has been generated in the {data.section} directory.
At first, edit the metadata.yaml and then run "nrp-cli model compile {data.section}"
and to install to the site run "nrp-cli model install {data.section}".
                     """,
        pause=True,
    ),
)


def get_site(data):
    primary_site_name = data.get("config.primary_site_name")
    return data.get(f"sites.{primary_site_name}")
