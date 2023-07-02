from oarepo_cli.model.gen.base import GeneratedFile
from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.package_versions import OAREPO_MODEL_BUILDER_VOCABULARIES_VERSION
from oarepo_cli.utils import unique_merger
from oarepo_cli.wizard import RadioStep


class AddVocabulariesWizardStep(ModelWizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            RadioStep(
                "use_vocabularies",
                heading="Do you want your model to use plain invenio vocabularies?",
                options={
                    "yes": "Yes, I want to use invenio vocabularies",
                    "no": "No, I will not have controlled vocabularies in the model",
                },
            ),
            **kwargs,
        )

    def after_run(self):
        if self.data["use_vocabularies"] != "yes":
            return
        self.data["use_relations"] = "yes"

        yaml_file: GeneratedFile = self.root.files.get("model.yaml")
        yaml = yaml_file.yaml
        unique_merger.merge(
            yaml,
            {
                "plugins": {
                    "packages": [
                        f"oarepo-model-builder-vocabularies{OAREPO_MODEL_BUILDER_VOCABULARIES_VERSION}"
                    ]
                },
            },
        )
        yaml_file.save()

    def should_run(self):
        return True
