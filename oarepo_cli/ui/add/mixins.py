import json


class UIWizardMixin:
    @property
    def ui_name(self):
        return self.data.section

    @property
    def ui_dir(self):
        return self.data.project_dir / "ui" / self.ui_name


class AssociatedModelMixin:
    def get_model_definition(self):
        model_config = self.data.whole_data["models"][self.data["model_name"]]
        model_package = model_config["model_package"]

        model_path = self.data.project_dir / model_config["model_dir"]
        model_file = (
            (model_path / model_package / "models" / "records.json")
            .absolute()
            .resolve(strict=False)
        )
        with open(model_file) as f:
            model_description = json.load(f)
        return model_description, model_path, model_package, model_config
