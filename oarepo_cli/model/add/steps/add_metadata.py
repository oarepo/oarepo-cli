from oarepo_cli.model.gen.base import GeneratedFile
from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.utils import unique_merger
from oarepo_cli.wizard import RadioStep


class AddMetadataWizardStep(ModelWizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            RadioStep(
                "use_metadata",
                default="yes",
                heading="Do you want to define your own metadata in a separated 'metadata' element and file ?",
                options={
                    "yes": "Yes, I want metadata separated in a new file",
                    "no": "No, I'll define metadata directly in the model file",
                },
            ),
            **kwargs
        )

    def after_run(self):
        if self.data["use_metadata"] != "yes":
            return

        yaml_file: GeneratedFile = self.root.files.get("model.yaml")
        yaml = yaml_file.yaml
        unique_merger.merge(
            yaml,
            {
                "record": {"properties": {"use": ["./metadata.yaml"]}},
            },
        )
        yaml_file.save()

        yaml_file: GeneratedFile = self.root.files.get("metadata.yaml")
        yaml = yaml_file.yaml
        unique_merger.merge(yaml, {"metadata": {"properties": {}}})
        yaml_file.save()

    def should_run(self):
        return True
