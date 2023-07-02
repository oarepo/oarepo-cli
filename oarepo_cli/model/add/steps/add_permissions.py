from oarepo_cli.model.gen.base import GeneratedFile
from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.utils import unique_merger
from oarepo_cli.wizard import InputStep


class AddPermissionsWizardStep(ModelWizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            InputStep(
                "permissions_preset",
                prompt="""
Which permission presets do you want to use? Pre-defined values are
"'read_only' and 'everyone' but note that you may define your own presets.
Enter 'none' to not define permission preset at all (and use vanilla invenio 
permission classes).
""",
                default="read_only",
            ),
            **kwargs
        )

    def after_run(self):
        if self.data["permissions_preset"] == "none":
            return

        yaml_file: GeneratedFile = self.root.files.get("model.yaml")
        yaml = yaml_file.yaml
        unique_merger.merge(
            yaml,
            {
                "record": {
                    "permissions": {
                        "presets": [
                            x.strip()
                            for x in self.data["permissions_preset"].split(",")
                            if x.strip()
                        ]
                    }
                }
            },
        )
        yaml_file.save()

    def should_run(self):
        return True
