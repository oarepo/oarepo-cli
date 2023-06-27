import json
import re
from pathlib import Path
from typing import Any, List

from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import ProjectWizardMixin, SiteMixin
from oarepo_cli.wizard import WizardStep

from ..mixins import AssociatedModelMixin


def replace_non_variable_signs(x):
    return f"__{ord(x.group())}__"


class CreateJinjaStep(SiteMixin, AssociatedModelMixin, ProjectWizardMixin, WizardStep):
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

        site = SiteSupport(self.data)
        renderers_json = site.call_invenio(
            "oarepo",
            "ui",
            "renderers",
            "--json",
            grab_stdout=True,
        )
        renderers = [x["renderer"] for x in json.loads(renderers_json)]

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
            fields.update(
                {f"metadata.{k}": v for k, v in md.get("children", {}).items()}
            )
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
