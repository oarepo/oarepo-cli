import json
from functools import cached_property

from dotenv import dotenv_values

from oarepo_cli.site.site_support import SiteSupport


class SiteWizardStepMixin:
    @cached_property
    def site_support(self):
        return SiteSupport(self.data)

    @property
    def site_dir(self):
        return self.site_support.site_dir

    def get_invenio_configuration(self, *keys):
        values = dotenv_values(self.site_dir / ".env")

        def convert(x):
            try:
                if x == "False":
                    return False
                if x == "True":
                    return True
                return json.loads(x)
            except:
                return x

        try:
            return [convert(values[x]) for x in keys]
        except KeyError as e:
            raise KeyError(
                f"Configuration key not found in defaults: {values.keys()}: {e}"
            )


def get_site_local_packages(data):
    models = [
        model_name
        for model_name, model_section in data.whole_data.get("models", {}).items()
        if data.section in model_section.get("sites")
    ]
    uis = [
        ui_name
        for ui_name, ui_section in data.whole_data.get("ui", {}).items()
        if data.section in ui_section.get("sites")
    ]
    local_packages = [
        local_name
        for local_name, local_section in data.whole_data.get("local", {}).items()
        if data.section in local_section.get("sites")
    ]
    return models, uis, local_packages
