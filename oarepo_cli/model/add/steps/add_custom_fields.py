from oarepo_cli.model.gen.base import GeneratedFile
from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.package_versions import OAREPO_MODEL_BUILDER_CF_VERSION
from oarepo_cli.utils import unique_merger
from oarepo_cli.wizard import RadioStep


class AddCustomFieldsWizardStep(ModelWizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            RadioStep(
                "use_custom_fields",
                heading="Do you want your model to have configurable deployment custom fields?",
                options={
                    "yes": "Yes, I want that extensibility",
                    "no": "No, the metadata schema should be fixed",
                },
            ),
            **kwargs,
        )

    def after_run(self):
        if self.data["use_custom_fields"] != "yes":
            return

        yaml_file: GeneratedFile = self.root.files.get("model.yaml")
        yaml = yaml_file.yaml
        unique_merger.merge(
            yaml,
            {
                "record": {"use": ["./custom_fields.yaml"]},
                "plugins": {
                    "packages": [
                        f"oarepo-model-builder-cf{OAREPO_MODEL_BUILDER_CF_VERSION}"
                    ]
                },
            },
        )
        yaml_file.save()

        yaml_file: GeneratedFile = self.root.files.get("custom_fields.yaml")
        yaml = yaml_file.yaml

        cf = unique_merger.merge(yaml, {"custom-fields": []})
        if not yaml.ca.comment:
            yaml.yaml_set_comment_before_after_key(
                key="custom-fields",
                before="""
    TODO: add your expandable fields definitions for the base record here
    example:
    custom-fields:
    - element: custom_fields
      config: TEST_CUSTOM_FIELDS
    - config: INLINE_CUSTOM_FIELDS        
            """.strip(),
            )
        yaml_file.save()

    def should_run(self):
        return True
