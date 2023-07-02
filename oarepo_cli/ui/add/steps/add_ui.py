from os.path import relpath

from oarepo_cli.templates import get_cookiecutter_template
from oarepo_cli.ui.add.mixins import AssociatedModelMixin, UIWizardMixin
from oarepo_cli.utils import ProjectWizardMixin, snail_to_title, to_python_name
from oarepo_cli.wizard import InputStep, RadioStep, WizardStep


class AddUIWizardStep(
    AssociatedModelMixin, UIWizardMixin, ProjectWizardMixin, WizardStep
):
    def __init__(self):
        super().__init__(
            RadioStep(
                "model_name",
                heading="""
                For which model do you want to generate the ui?
                """,
                options=self.available_models,
                default=lambda data: next(iter(self.available_models())),
            ),
            InputStep(
                "url_prefix",
                prompt="On which url prefix will the UI reside? The prefix should like /something/: ",
                default=lambda data: f"/{data.section}/",
            ),
        )

    def available_models(self):
        known_models = {x: x for x in self.data.whole_data.get("models", {}).keys()}
        return known_models

    def available_sites(self):
        return list(self.data.whole_data.get("sites", {}).keys())

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

        if not self.data["url_prefix"].startswith("/"):
            self.data["url_prefix"] = "/" + self.data["url_prefix"]
        if not self.data["url_prefix"].endswith("/"):
            self.data["url_prefix"] += "/"

        model_service = model_description["model"]["service-config"]["service-id"]
        ui_serializer_class = model_description["model"]["json-serializer"]["class"]

        self.data.setdefault("sites", self.available_sites())

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

        self.run_cookiecutter(
            template=get_cookiecutter_template("ui"),
            config_file=f"ui-{ui_name}",
            output_dir=self.data.project_dir / "ui",
            extra_context=cookiecutter_data,
        )

        self.data["ui_dir"] = f"ui/{ui_name}"

    def should_run(self):
        return not self.ui_dir.exists()
