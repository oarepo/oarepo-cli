from oarepo_cli.model.gen.base import GeneratedFile
from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.package_versions import OAREPO_MODEL_BUILDER_RELATIONS_VERSION
from oarepo_cli.utils import unique_merger
from oarepo_cli.wizard import RadioStep


class AddRelationsWizardStep(ModelWizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            RadioStep(
                "use_relations",
                heading="Do you want your model to use relations to other models (or within single model)?",
                options={"yes": "Yes, I want to use relations", "no": "No"},
            ),
            **kwargs,
        )

    def after_run(self):
        if self.data["use_relations"] != "yes":
            return

        yaml_file: GeneratedFile = self.root.files.get("model.yaml")
        yaml = yaml_file.yaml
        unique_merger.merge(
            yaml,
            {
                "plugins": {
                    "packages": [
                        f"oarepo-model-builder-relations{OAREPO_MODEL_BUILDER_RELATIONS_VERSION}"
                    ]
                },
            },
        )
        yaml_file.save()

    def should_run(self):
        return True
