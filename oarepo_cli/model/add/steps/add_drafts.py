from oarepo_cli.model.gen.base import GeneratedFile
from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.package_versions import (
    OAREPO_MODEL_BUILDER_DRAFTS_FILES_VERSION,
    OAREPO_MODEL_BUILDER_DRAFTS_VERSION,
)
from oarepo_cli.utils import unique_merger
from oarepo_cli.wizard import RadioStep


class AddDraftsWizardStep(ModelWizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            RadioStep(
                "use_drafts",
                heading="Should records be first uploaded as editable drafts before they are published?",
                options={
                    "yes": "yes",
                    "no": "no",
                },
                default="yes",
            ),
            **kwargs,
        )

    def after_run(self):
        if self.data["use_drafts"] != "yes":
            return

        yaml_file: GeneratedFile = self.root.files.get("model.yaml")
        yaml = yaml_file.yaml
        unique_merger.merge(
            yaml,
            {
                "record": {"draft": {}},
                "profiles": ["draft"],
                "plugins": {
                    "packages": [
                        f"oarepo-model-builder-drafts{OAREPO_MODEL_BUILDER_DRAFTS_VERSION}"
                    ]
                },
            },
        )

        if self.data["use_files"] == "yes":
            unique_merger.merge(
                yaml,
                {
                    "record": {"draft-files": {}},
                    "profiles": ["draft_files"],
                    "plugins": {
                        "packages": [
                            f"oarepo-model-builder-drafts-files{OAREPO_MODEL_BUILDER_DRAFTS_FILES_VERSION}"
                        ]
                    },
                },
            )

        yaml_file.save()

    def should_run(self):
        return True
