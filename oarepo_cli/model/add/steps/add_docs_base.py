from oarepo_cli.model.gen.base import GeneratedFile
from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.package_versions import (
    NR_METADATA_VERSION,
    NR_OAIPMH_HARVESTERS_VERSION,
    NR_VOCABULARIES_VERSION,
    OAREPO_MODEL_BUILDER_NR_VERSION,
)
from oarepo_cli.utils import unique_merger
from oarepo_cli.wizard import RadioStep


class AddDocsBaseWizardStep(ModelWizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            RadioStep(
                "use_docs",
                heading="Should I base the model on nr-docs?",
                options={"yes": "Yes", "no": "No"},
            ),
            **kwargs,
        )

    def after_run(self):
        if self.data["use_docs"] != "yes":
            return
        self.data["use_vocabularies"] = "yes"
        self.data["use_nr_vocabularies"] = "yes"
        self.data["use_metadata"] = "yes"
        yaml_file: GeneratedFile = self.root.files.get("model.yaml")
        yaml = yaml_file.yaml
        unique_merger.merge(
            yaml,
            {
                "record": {
                    "extend": "nr-documents#DocumentModel",
                },
                "plugins": {
                    "builder": {"disable": ["script_sample_data"]},
                    "packages": [
                        f"oarepo-model-builder-nr{OAREPO_MODEL_BUILDER_NR_VERSION}"
                    ],
                },
                "runtime-dependencies": {
                    "nr-metadata": NR_METADATA_VERSION,
                    "nr-oaipmh-harvesters": NR_OAIPMH_HARVESTERS_VERSION,
                    "nr-vocabularies": NR_VOCABULARIES_VERSION,
                },
                "settings": {
                    "i18n-languages": ["cs", "en"],
                    "supported-langs": {
                        "cs": {
                            "keyword": {"type": "keyword"},
                            "text": {"analyzer": "czech"},
                        },
                        "en": {"text": {}},
                    },
                },
            },
        )
        yaml_file.save()

    def should_run(self):
        return True
