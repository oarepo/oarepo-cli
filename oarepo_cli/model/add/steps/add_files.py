from oarepo_cli.model.gen.base import GeneratedFile
from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.package_versions import OAREPO_MODEL_BUILDER_FILES_VERSION
from oarepo_cli.utils import unique_merger
from oarepo_cli.wizard import RadioStep


class AddFilesWizardStep(ModelWizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            RadioStep(
                "use_files",
                heading="Do you want to store digital objects along with metadata?",
                options={
                    "yes": "Yes, I need files",
                    "no": "No, this is metadata-only repository",
                },
            ),
            **kwargs,
        )

    def after_run(self):
        if self.data["use_files"] != "yes":
            return

        yaml_file: GeneratedFile = self.root.files.get("model.yaml")
        yaml = yaml_file.yaml
        unique_merger.merge(
            yaml,
            {
                "record": {"use": ["./files.yaml"]},
                "plugins": {
                    "packages": [
                        f"oarepo-model-builder-files{OAREPO_MODEL_BUILDER_FILES_VERSION}"
                    ]
                },
                "profiles": ["files"],
            },
        )
        yaml_file.save()

        yaml_file: GeneratedFile = self.root.files.get("files.yaml")
        yaml = yaml_file.yaml
        unique_merger.merge(
            yaml,
            {
                "files": {
                    "use": ["invenio_files"],
                    "module": {
                        "qualified": self.data["model_package"],
                    },
                    "properties": {},
                }
            },
        )
        yaml_file.save()

    def should_run(self):
        return True
