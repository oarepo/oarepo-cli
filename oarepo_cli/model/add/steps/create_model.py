from oarepo_cli.model.gen.base import GeneratedFile
from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.utils import to_python_name, unique_merger
from oarepo_cli.wizard import InputStep


class EmptyModelWizardStep(ModelWizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            InputStep(
                "model_package",
                prompt="Enter the model package",
                default=lambda data: to_python_name(data.section),
            ),
            **kwargs
        )

    def after_run(self):
        yaml_file: GeneratedFile = self.root.files.get("model.yaml")
        yaml = yaml_file.yaml
        unique_merger.merge(
            yaml,
            {
                "record": {
                    "use": ["invenio"],
                    "module": {
                        "qualified": self.data["model_package"],
                    },
                    "properties": {},
                },
                "settings": {"i18n-languages": ["en"]},
                "profiles": ["record"],
            },
        )
        yaml_file.save()

    def should_run(self):
        return True
