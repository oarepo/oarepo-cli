from pathlib import Path

from cookiecutter.main import cookiecutter

from oarepo_cli.templates import get_cookiecutter_template
from oarepo_cli.ui.wizard import Wizard, StaticWizardStep, InputWizardStep, WizardStep
from oarepo_cli.ui.wizard.steps import RadioWizardStep


class CreateModelWizardStep(WizardStep):
    def after_run(self, data):
        """
        "base_model_package": "{%- if cookiecutter.model_kind == 'empty model' -%} (none) {%- elif cookiecutter.model_kind == 'common' -%} nr-common-metadata-model-builder {%- elif cookiecutter.model_kind == 'documents' -%} nr-documents-records-model-builder {%- elif cookiecutter.model_kind == 'data' -%} TODO {%- elif cookiecutter.model_kind == 'common' -%} {%- endif -%}",
"base_model_use": "{{ cookiecutter.base_model_package|strip_model_builder }}",
"_extensions": [
    "local_extensions.strip_model_builder"
]
        """
        base_model_package = {
            'empty': '(none)',
            'common': 'nr-common-metadata-model-builder',
            'documents': 'nr-documents-records-model-builder',
            'data': 'TODO',
        }.get('model_kind')
        base_model_use = base_model_package.replace('-model-builder', '')
        cookiecutter(
            get_cookiecutter_template("model"),
            no_input=True,
            output_dir=Path(data['project_dir']) / 'models',
            extra_context={
                **data,
                "base_model_package": base_model_package,
                "base_model_use": base_model_use
            },
        )


add_model_wizard = Wizard(
    StaticWizardStep('intro', heading="""
Before creating the datamodel, I'll ask you a few questions.
If unsure, use the default value.
    """),
    InputWizardStep("model_package", heading="Enter the model package",
                    default=lambda data: data['model_name'].replace('-', '_')),
    RadioWizardStep("model_kind", heading="""
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
                        'common': 'Common set of metadata, DC compatible',
                        'documents': 'Based on Czech National Repository documents metadata',
                        'data': 'Based on Czech National Repository datasets metadata',
                        'empty': "Just use empty model, I'll add the metadata myself"
                    },
                    default='common'),
    StaticWizardStep('intro2', heading="""
Now tell me something about you. The defaults are taken from the monorepo, feel free to use them.
    """),
    InputWizardStep("author_name", heading="""Model author""", default=lambda data: data.get('config.author_name')),
    InputWizardStep("author_email", heading="""Model author's email""",
                    default=lambda data: data.get('.config.author_email')),
    StaticWizardStep('outro1', heading="Now I have all the information to generate your model. After pressing Enter, I will generate the sources", pause=True),
    CreateModelWizardStep('create_model_step'),
    StaticWizardStep('outro2',
                     heading=lambda data: f"""
The model has been generated in the {Path(data['project_dir']) / 'models' / data['model_name']} directory.
At first, edit the model-metadata.yaml and them run "oarepo-configure model compile {data['model_name']}"
and "oarepo-configure model install {data['model_name']}".
                     """,
                     pause=True),
)
