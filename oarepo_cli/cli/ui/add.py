import json
from os.path import relpath
from pathlib import Path
import re
from typing import Any, List

import click as click

from oarepo_cli.cli.model.utils import ProjectWizardMixin
from oarepo_cli.cli.utils import with_config
from oarepo_cli.ui.wizard import StaticWizardStep, Wizard
from oarepo_cli.ui.wizard.steps import InputWizardStep, RadioWizardStep, WizardStep
from oarepo_cli.utils import get_cookiecutter_source, run_cmdline, to_python_name
from ...utils import commit_git


@click.command(
    name="add",
    help="""Generate a new UI. Required arguments:
    <name>   ... name of the ui. The recommended pattern for it is <modelname>-ui
    """,
)
@click.argument("name")
@with_config(config_section=lambda name, **kwargs: ["ui", name])
def add_ui(cfg=None, **kwargs):
    commit_git(
        cfg.project_dir,
        f"before-ui-add-{cfg.section}",
        f"Committed automatically before ui {cfg.section} has been added",
    )
    add_ui_wizard(cfg).run(cfg)
    commit_git(
        cfg.project_dir,
        f"after-ui-add-{cfg.section}",
        f"Committed automatically after ui {cfg.section} has been added",
    )


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


class ModelMixin:
    def get_model_definition(self):
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
        return model_description, model_path, model_package, model_config


class AddUIWizardStep(ModelMixin, UIWizardMixin, ProjectWizardMixin, WizardStep):
    def after_run(self):
        ui_name = self.ui_name

        ui_package = to_python_name(ui_name)
        ui_base = snail_to_title(ui_package)

        (
            model_description,
            model_path,
            model_package,
            model_config,
        ) = self.get_model_definition()

        model_service = model_description["model"]["service-id"]
        ui_serializer_class = model_description["model"]["record-ui-serializer-class"]

        self.data.setdefault(
            "cookiecutter_local_model_path", relpath(model_path, self.ui_dir)
        )
        self.data.setdefault("cookiecutter_model_package", model_package)
        self.data.setdefault("cookiecutter_app_name", ui_name)
        self.data.setdefault("cookiecutter_app_package", ui_package)
        self.data.setdefault("cookiecutter_ext_name", f"{ui_base}Extension")

        self.data.setdefault("cookiecutter_author", model_config.get("author_name", ""))
        self.data.setdefault(
            "cookiecutter_author_email", model_config.get("author_email", "")
        )
        self.data.setdefault("cookiecutter_repository_url", "")
        # TODO: take this dynamically from the running model's Ext so that
        # TODO: it does not have to be specified here
        self.data.setdefault("cookiecutter_resource", f"{ui_base}Resource")
        self.data.setdefault("cookiecutter_resource_config", f"{ui_base}ResourceConfig")
        self.data.setdefault("cookiecutter_api_service", model_service)
        self.data.setdefault(
            "cookiecutter_ui_record_serializer_class", ui_serializer_class
        )

        cookiecutter_data = {
            "model_name": self.data["model_name"],
            "local_model_path": self.data["cookiecutter_local_model_path"],
            "model_package": self.data["cookiecutter_model_package"],
            "app_name": self.data["cookiecutter_app_name"],
            "app_package": self.data["cookiecutter_app_package"],
            "ext_name": self.data["cookiecutter_ext_name"],
            "author": self.data["cookiecutter_author"],
            "author_email": self.data["cookiecutter_author_email"],
            "repository_url": self.data["cookiecutter_repository_url"],
            # TODO: take this dynamically from the running model's Ext so that
            # TODO: it does not have to be specified here
            "resource": self.data["cookiecutter_resource"],
            "resource_config": self.data["cookiecutter_resource_config"],
            "api_service": self.data["cookiecutter_api_service"],
            "ui_serializer_class": self.data["cookiecutter_ui_record_serializer_class"],
            "url_prefix": self.data["url_prefix"],
        }

        cookiecutter_path, cookiecutter_branch = get_cookiecutter_source(
            "OAREPO_UI_COOKIECUTTER_VERSION",
            "https://github.com/oarepo/cookiecutter-app",
            "v11.0",
            master_version="master",
        )

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
        CreateJinjaStep(),
    )


class CreateJinjaStep(ModelMixin, WizardStep):
    def should_run(self):
        return True

    def after_run(self):
        (
            model_description,
            model_path,
            model_package,
            model_config,
        ) = self.get_model_definition()
        # get the UI definition
        ui_definition_path = model_path / model_package / "models" / "ui.json"
        ui_definition = json.loads(ui_definition_path.read_text())

        # get the first site (TODO: how to do this better?) and load registered renderers
        sites = self.data.whole_data.get("sites", [])
        if sites:
            first_site = next(iter(sites.values()))
            renderers_json = run_cmdline(
                "pipenv",
                "run",
                "invenio",
                "oarepo",
                "ui",
                "renderers",
                "--json",
                cwd=self.data.project_dir / first_site["site_dir"],
                environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
                grab_stdout=True,
            )
            renderers = [x["renderer"] for x in json.loads(renderers_json)]
        else:
            # pre-defined renderers
            renderers = [
                "array",
                "date",
                "datetime",
                "double",
                "field",
                "float",
                "fulltext",
                "fulltext__43__keyword",
                "int",
                "keyword",
                "time",
                "value",
            ]

        template, macro_definitions = self.generate_main(ui_definition)
        if macro_definitions:
            macros = "\n".join(
                self.generate_macro_definitions(macro_definitions, set(renderers))
            )
        else:
            macros = None

        # save template and macros
        ui_dir = self.data.project_dir / self.data.config["ui_dir"]
        main_jinja_path = (
            ui_dir
            / self.data.config["cookiecutter_app_package"]
            / "templates"
            / "semantic-ui"
            / self.data.config["cookiecutter_app_package"]
            / "main.html"
        )
        template = main_jinja_path.read_text() + "\n\n" + template
        main_jinja_path.write_text(template)

        macros_jinja_path: Path = (
            ui_dir
            / self.data.config["cookiecutter_app_package"]
            / "templates"
            / "semantic-ui"
            / "oarepo_ui"
            / "components"
            / "100-macros.html"
        )
        macros_jinja_path.parent.mkdir(exist_ok=True, parents=True)
        macros_jinja_path.write_text(macros or "")

    def _select(self, fields, *keys):
        for k in keys:
            if k in fields:
                return k, fields.pop(k)
        return None, None

    def generate_main(self, ui):
        macro_definitions = []
        template = []
        fields = ui["children"]
        if "metadata" in fields:
            md = fields.pop("metadata")
            fields.update({f"metadata.{k}": v for k, v in md["children"].items()})
        title_key, title = self._select(fields, "title", "metadata.title")
        divider = False
        if title_key:
            template.append(f'<h1>{{%- value "{title_key}" -%}}</h1>')
            macro_definitions.append(title)
            divider = True
        creator_key, creator = self._select(fields, "creator", "metadata.creator")
        if creator_key:
            template.append(
                f'<div class="creator">{{%- value "{creator_key}" -%}}</div>'
            )
            macro_definitions.append(creator)
            divider = True
        if divider:
            template.append('<hr class="divider"/>')
        template.append('<dl class="detail-fields">')
        for fld_key, fld in sorted(fields.items()):
            template.append(f'{{%- field "{fld_key}" -%}}')
            macro_definitions.append(fld)
        template.append("</dl>")

        return "\n".join(template), macro_definitions

    def generate_macro_definitions(
        self, macro_definitions: List[Any], processed_components
    ):
        for definition in macro_definitions:
            if not definition.get("detail"):
                continue
            component = re.sub(r"\W", replace_non_variable_signs, definition["detail"])

            if component in processed_components:
                _, children = self._generate_macro_children(definition)
            else:
                processed_components.add(component)

                children_def, children = self._generate_macro_children(definition)
                if children_def:
                    yield f"\n\n{{%- macro render_{component}(arg) -%}}\n<dl class='detail-subfields'>\n{children_def}\n</dl>\n{{%- endmacro -%}}"
                else:
                    yield f"\n\n{{%- macro render_{component}(arg) -%}}{'{{'}arg{'}}'}{{%- endmacro -%}}"

            yield from self.generate_macro_definitions(children, processed_components)

    def _generate_macro_children(self, definition):
        # for array members, do not return fields as array macro is built-in
        if "child" in definition:
            return "", [definition["child"]]
        if "children" not in definition:
            return "", []
        fields = []
        children = []
        for c_key, cdef in definition["children"].items():
            fields.append(f'{{%- field "{c_key}" -%}}')
            children.append(cdef)
        return "\n".join(fields), children


def replace_non_variable_signs(x):
    return f"__{ord(x.group())}__"
