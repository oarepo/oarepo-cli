from pathlib import Path

from oarepo_cli.wizard import WizardStep


class BaseFormatStep(WizardStep):
    def should_run(self):
        return True

    def after_run(self):
        pd = self.data.project_dir
        model_paths = [
            pd / "models" / model_name / model["model_package"]
            for model_name, model in self.data.whole_data.get("models", {}).items()
            if (pd / "models" / model_name / model["model_package"]).exists()
        ]
        ui_paths = [
            pd
            / "ui"
            / ui_name
            / ui["cookiecutter_app_package"]  # TODO: better name here?
            for ui_name, ui in self.data.whole_data.get("ui", {}).items()
            if (pd / "ui" / ui_name / ui["cookiecutter_app_package"]).exists()
        ]
        local_paths = [
            pd / "local" / local_name
            for local_name in self.data.whole_data.get("local", {})
            if (pd / "local" / local_name).exists()
        ]
        site_paths = [
            pd / "sites" / site_name
            for site_name in self.data.whole_data.get("sites", {})
            if (pd / "sites" / site_name).exists()
        ]
        self.format_paths(model_paths, ui_paths, local_paths, site_paths)

    def format_paths(self, model_paths, ui_paths, local_paths, site_paths):
        pass

    def find_files_with_extensions(self, dirs, *extensions):
        for d in dirs:
            for f in Path(d).glob("**/*"):
                if f.suffix[1:] in extensions:
                    yield f
