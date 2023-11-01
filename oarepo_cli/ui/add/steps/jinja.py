import json
from oarepo_cli.site.site_support import SiteSupport
from pathlib import Path
from typing import Any, List
import string

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
        existing_components = site.call_invenio(
            "oarepo",
            "ui",
            "components",
            grab_stdout=True,
        )

        template, component_definitions = self.generate_main(ui_definition, existing_components)
        if component_definitions:
            components = self.get_component_definitions(component_definitions)

        else:
            components = None

        # save template and components

        ui_dir = self.data.project_dir / self.data.config["ui_dir"]
        main_jinja_path = (
            ui_dir
            / self.data.config["cookiecutter_app_package"]
            / "templates"
            / "semantic-ui"
            / self.data.config["cookiecutter_app_package"]
            / "Main.jinja.html"
        )
        template = main_jinja_path.read_text() + "\n\n" + template
        main_jinja_path.write_text(template)
        for comp in components:
            file_name = "999-" + comp["name"] + ".jinja"
            component_jinja_path: Path = (
                ui_dir
                / self.data.config["cookiecutter_app_package"]
                / "templates"
                / "semantic-ui"
                / "oarepo_ui"
                / "components"
                / file_name
            )
            component_jinja_path.parent.mkdir(exist_ok=True, parents=True)
            component_jinja_path.write_text(comp["component"])

    def _select(self, fields, *keys):
        for k in keys:
            if k in fields:
                return k, fields.pop(k)
        return None, None

    def generate_main(self, ui, existing_components):
        component_definitions = []
        template = []
        fields = ui["children"]
        if "metadata" in fields:
            md = fields.pop("metadata")
            fields.update(
                {f"metadata.{k}": v for k, v in md.get("children", {}).items()}
            )
        title_key, title = self._select(fields, "title", "metadata.title")
        divider = False
        template.append("{#def metadata, ui, layout, record #}")
        if title_key:
            template.append(f'<h1>{{{{ {title_key} }}}}</h1>')
            divider = True
        creator_key, creator = self._select(fields, "creator", "metadata.creator")
        if creator_key:
            template.append(
                f'<div class="creator">{{{{ {creator_key} }}}}</div>'
            )
            divider = True
        if divider:
            template.append('<hr class="divider"/>')
        template.append('<dl class="detail-fields">')
        for fld_key, fld in sorted(fields.items()):
            if not fld_key.startswith('metadata'):
                data_name = 'record.' + fld_key
            else:
                data_name = fld_key
            matching_component = None
            for item in existing_components:
                if item['key'] == fld['detail']:
                    matching_component = item
                    break  # Exit the loop when a match is found

            if matching_component:
                field_definition = f'<Field label={{ _("{fld["label"]}") }}>'

                field_definition = field_definition + f'<{matching_component["component"]} data={{{data_name}}}></{matching_component["component"]}>'
                field_definition = field_definition + f'</Field>'

            elif not('child' in fld or 'children' in fld):
                field_definition = f'<Field label={{ _("{fld["label"]}") }}>{{{{ {data_name} }}}}</Field>'
            else:

                field_definition = f'<Field label={{ _("{fld["label"]}") }}>'
                component_name = self.create_component_name(fld_key)

                field_definition = field_definition + f'<{component_name} data={{{data_name}}}></{component_name}>'
                field_definition = field_definition + f'</Field>'

                component_definitions.append({"name": component_name, "definition": fld})
            template.append(field_definition)
        template.append("</dl>")

        return "\n".join(template), component_definitions

    def create_component_name(self, field_key):
        field_key = field_key.lstrip(string.punctuation)
        fields = field_key.split('.')
        component_name = "".join([field.capitalize() for field in fields])

        return component_name


    def get_component_definitions(
        self, component_definitions: List[Any]
    ):
        components = []
        for definition in component_definitions:

            if definition["definition"]["detail"] == "array":
                children_def, children = self._generate_macro_children(definition["definition"]["child"])
                components.append({"name": definition["name"], "component": f"\n\n{{#def data}}\n<dl class='detail-subfields'>\n{{% for field in data %}}\n{children_def}\n{{% endfor %}}\n</dl>\n"})

            else:
                children_def, children = self._generate_macro_children(definition["definition"])
                components.append({"name": definition["name"], "component": f"\n\n{{#def data}}\n<dl class='detail-subfields'>\n{children_def}\n</dl>\n"})


        return components

    def _generate_macro_children(self, definition):
        if "children" not in definition:
            return "", [{"definition": {}}]
        fields = []
        children = []
        for c_key, cdef in definition["children"].items():
            c_key = "data." + c_key
            fields.append(f'<Field label={{ _("{cdef["label"]}") }}>{{{{ {c_key} }}}}</Field>')

        return "\n".join(fields), children
