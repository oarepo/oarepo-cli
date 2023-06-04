from oarepo_cli.model.gen.base import GeneratedFile
from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.package_versions import OAREPO_MODEL_BUILDER_TESTS_VERSION
from oarepo_cli.utils import unique_merger
from oarepo_cli.wizard import RadioStep


class AddTestsWizardStep(ModelWizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            RadioStep(
                "use_tests",
                heading="Do you want to pre-generate some tests?",
                options={"yes": "Yes, I want to use tests", "no": "No"},
            ),
            **kwargs,
        )

    def after_run(self):
        if self.data["use_tests"] != "yes":
            return

        yaml_file: GeneratedFile = self.root.files.get("model.yaml")
        yaml = yaml_file.yaml
        unique_merger.merge(
            yaml,
            {
                "plugins": {
                    "packages": [
                        f"oarepo-model-builder-tests{OAREPO_MODEL_BUILDER_TESTS_VERSION}"
                    ]
                },
            },
        )
        yaml_file.save()

    def should_run(self):
        return True
