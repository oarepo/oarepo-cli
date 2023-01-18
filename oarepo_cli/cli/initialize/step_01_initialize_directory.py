import logging

from oarepo_cli.config import Config
from oarepo_cli.ui.wizard import WizardStep
from oarepo_cli.utils import to_python_name

log = logging.getLogger("step_01_initialize_directory")


class DirectoryStep(WizardStep):
    def __init__(self, *args, **kwargs):
        super().__init__(heading="Creating the target directory ...")

    def after_run(self):
        self.data["project_package"] = to_python_name(self.data.project_dir.name)
        p = self.data.project_dir
        if not p.exists():
            p.mkdir(parents=True)

    def should_run(self):
        return True
