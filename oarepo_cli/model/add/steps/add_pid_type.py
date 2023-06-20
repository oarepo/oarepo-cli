from oarepo_cli.model.gen.base import GeneratedFile
from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.utils import unique_merger
from oarepo_cli.wizard import InputStep


class AddPIDTypeWizardStep(ModelWizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            InputStep(
                "pid_type",
                prompt="Do you want to specify your own pid type (if empty, it will be autogenerated)?",
                required=False,
            ),
            **kwargs
        )

    def after_run(self):
        if not self.data.get("pid_type"):
            return

        yaml_file: GeneratedFile = self.root.files.get("model.yaml")
        yaml = yaml_file.yaml
        unique_merger.merge(
            yaml,
            {
                "record": {"pid": {"type": self.data["pid_type"]}},
            },
        )
        yaml_file.save()

    def should_run(self):
        return True