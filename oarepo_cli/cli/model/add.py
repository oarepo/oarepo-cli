import subprocess
import venv
from pathlib import Path

import click as click

from oarepo_cli.cli.model.utils import ModelWizardStep
from oarepo_cli.cli.utils import with_config
from oarepo_cli.ui.wizard import InputWizardStep, StaticWizardStep, Wizard, WizardStep
from oarepo_cli.ui.wizard.steps import RadioWizardStep
from oarepo_cli.utils import get_cookiecutter_source, pip_install, to_python_name

from ...utils import commit_git


@click.command(
    name="add",
    help="""
Generate a new model. Required arguments:
    <name>   ... name of the model, can contain [a-z] and dash (-)""",
)
@click.argument("name", required=True)
@click.option(
    "--merge",
    multiple=True,
    help="""
Use this option to merge your code into the generated model.

--merge my_dir              will merge my_dir with the generated sources

--merge my_dir=gen_subdir   will merge my_dir into the subdir(relative path to models/<model>)

--merge my_file=<rel_path_to_file>   will merge single file

Normally, user file is merged at the end of the generated file - that is, the content of generated file goes first (includes, classes, arrays).

Use '-' before the dir/file to reverse the order - the content of your file will be prepended to an existing file
Use '!' before the dir/file to copy the file to destination without merging it
""",
)
@with_config(config_section=lambda name, **kwargs: ["models", name])
def add_model(cfg=None, merge=None, **kwargs):
    commit_git(
        cfg.project_dir,
        f"before-model-add-{cfg.section}",
        f"Committed automatically before model {cfg.section} has been added",
    )
    if merge:
        venv_dir: Path = cfg.project_dir / ".venv" / "oarepo-model-builder"
        venv_dir = venv_dir.absolute()
        if not venv_dir.exists():
            venv_dir.parent.mkdir(parents=True, exist_ok=True)
            venv.main([str(venv_dir)])

            pip_install(
                venv_dir / "bin" / "pip",
                "OAREPO_MODEL_BUILDER_VERSION",
                "oarepo-model-builder==3.*",
                "https://github.com/oarepo/oarepo-model-builder",
            )

    add_model_wizard.run(cfg)

    if merge:
        for merge_def in merge:
            opts = []
            merge_def = merge_def.split("=", maxsplit=1)

            merge_source: Path = merge_def[0]
            if merge_source[0] == "-":
                merge_source = merge_source[1:]
                opts.append("--destination-first")
            if merge_source[0] == "!":
                merge_source = merge_source[1:]
                opts.append("--overwrite")

            merge_target: Path = cfg.project_dir
            for p in cfg.section_path:
                merge_target = merge_target / p
            if len(merge_def) == 2:
                merge_target = merge_target.joinpath(merge_def[1])

            subprocess.call(
                [
                    venv_dir / "bin" / "oarepo-merge",
                    Path(merge_source).absolute(),
                    Path(merge_target).absolute(),
                    *opts,
                ]
            )
    commit_git(
        cfg.project_dir,
        f"after-model-add-{cfg.section}",
        f"Committed automatically after model {cfg.section} has been added",
    )


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

        cookiecutter_path, cookiecutter_branch = get_cookiecutter_source(
            "OAREPO_MODEL_COOKIECUTTER_VERSION",
            "https://github.com/oarepo/cookiecutter-model",
            "v11.0",
            master_version="master",
        )

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
        default=lambda data: (get_site(data) or {}).get("author_name"),
    ),
    InputWizardStep(
        "author_email",
        prompt="""Model author's email""",
        default=lambda data: (get_site(data) or {}).get("author_email"),
    ),
    RadioWizardStep(
        "permissions_presets",
        heading="Would you like to set up permissions",
        options={
            "no": "no",
            "read_only": "read only access to records, no one can create or edit them",
            "everyone": "every user (both authenticated or anonymous) can create, edit and delete any record",
        },
        default="yes",
    ),
    InputWizardStep(
        "pid_type",
        prompt="""Specify the name of the type of the pid of the model. If nothing is provided,
         it will be autogenerated.""",
        default="",
        required=False,
    ),
    RadioWizardStep(
        "use_drafts",
        heading="Should records be first uploaded as editable drafts before they are published?",
        options={
            "yes": "yes",
            "no": "no",
        },
        default="yes",
    ),
    StaticWizardStep(
        heading="Now you can choose which plugins you need in the repo.", pause=True
    ),
    RadioWizardStep(
        "use_files",
        heading="Will you upload files to the records in this model? If the repository is not metadata only, answer yes.",
        options={
            "yes": "yes",
            "no": "no",
        },
        default="yes",
    ),
    RadioWizardStep(
        "use_requests",
        heading="Do you need approval process for the records in this model? We recommend to use it, otherwise your changes would be immediately visible.",
        options={
            "yes": "yes",
            "no": "no",
        },
        default="yes",
    ),
    RadioWizardStep(
        "use_expandable_fields",
        heading="Will you use expandable fields? If in doubt, choose no.",
        options={
            "yes": "yes",
            "no": "no",
        },
        default="no",
    ),
    RadioWizardStep(
        "use_relations",
        heading="Will you use relations to different records? For example, if this model represents a Dataset, relation to Article model.",
        options={
            "yes": "yes",
            "no": "no",
        },
        default="yes",
    ),
    RadioWizardStep(
        "use_custom_fields",
        heading="Would you like to make your model extensible during deployment via custom fields?",
        options={
            "yes": "yes",
            "no": "no",
        },
        default="yes",
    ),
    RadioWizardStep(
        "use_vocabularies",
        heading="Will you use vocabularies in your model?",
        options={
            "yes": "yes",
            "no": "no",
        },
        default="yes",
    ),
    StaticWizardStep(
        heading="Now I have all the information to generate your model. After pressing Enter, I will generate the sources",
        pause=True,
    ),
    CreateModelWizardStep(),
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
