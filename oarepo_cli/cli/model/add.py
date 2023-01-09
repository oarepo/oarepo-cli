import click as click
from cookiecutter.main import cookiecutter

from oarepo_cli.cli.model.utils import ModelWizardStep
from oarepo_cli.cli.utils import with_config
from oarepo_cli.ui.wizard import InputWizardStep, StaticWizardStep, Wizard, WizardStep
from oarepo_cli.ui.wizard.steps import RadioWizardStep
from oarepo_cli.utils import to_python_name


@click.command(
    name="add",
    help="""
Generate a new model. Required arguments:
    <name>   ... name of the model, can contain [a-z] and dash (-)""",
)
@click.argument("name")
@with_config(config_section=lambda name, **kwargs: ["models", name])
def add_model(cfg, **kwargs):
    add_model_wizard.run(cfg)


class CreateModelWizardStep(ModelWizardStep, WizardStep):
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
            output_dir=str(self.model_dir(data).parent),
            extra_context={
                **data,
                "model_name": self.model_dir(data).name,
                "base_model_package": base_model_package,
                "base_model_use": base_model_use,
            },
        )
        data["model_dir"] = str(self.model_dir(data).relative_to(data.project_dir))

    def should_run(self, data):
        return not self.model_dir(data).exists()


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
    StaticWizardStep(
        heading=lambda data: f"""
The model has been generated in the {data.section} directory.
At first, edit the metadata.yaml and then run "oarepo-cli model compile {data.section}"
and to install to the site run "oarepo-cli model install {data.section}".
                     """,
        pause=True,
    ),
)


def get_site(data):
    primary_site_name = data.get("config.primary_site_name")
    return data.get(f"sites.{primary_site_name}")
