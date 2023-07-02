from oarepo_cli.model.gen.base import GeneratedFile
from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.package_versions import NR_VOCABULARIES_VERSION
from oarepo_cli.utils import unique_merger
from oarepo_cli.wizard import RadioStep


class AddNRVocabulariesWizardStep(ModelWizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            RadioStep(
                "use_nr_vocabularies",
                heading="Do you want your model to use Czech NR vocabularies?",
                options={"yes": "Yes, I want to use Czech NR", "no": "No"},
            ),
            **kwargs
        )

    def after_run(self):
        if self.data["use_nr_vocabularies"] != "yes":
            return
        self.data["use_vocabularies"] = "yes"

        yaml_file: GeneratedFile = self.root.files.get("model.yaml")
        yaml = yaml_file.yaml
        unique_merger.merge(
            yaml,
            {
                "runtime-dependencies": {
                    "nr-vocabularies": NR_VOCABULARIES_VERSION,
                }
            },
        )
        yaml_file.save()

    def should_run(self):
        return True
