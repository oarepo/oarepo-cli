import json
from pathlib import Path

from dotenv import dotenv_values

from oarepo_cli.utils import run_cmdline


class SiteWizardStepMixin:
    @property
    def site_dir(self):
        return Path(self.data.project_dir) / self.data["site_dir"]

    def call_pip(self, *args, **kwargs):
        return run_cmdline(['pdm', 'run', 'pip'], *args, **kwargs, cwd=self.site_dir)

    def call_invenio(self, *args, **kwargs):
        return run_cmdline(['pdm', 'run', 'invenio'], *args, **kwargs, cwd=self.site_dir)

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
