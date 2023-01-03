import logging
from pathlib import Path

from oarepo_cli.config import Config
from oarepo_cli.ui.wizard import WizardStep

log = logging.getLogger("step_01_initialize_directory")


class DirectoryStep(WizardStep):
    def __init__(self, *args, **kwargs):
        super().__init__(heading="Creating the target directory ...")

    def after_run(self, data: Config):
        data["project_package"] = Path(data["project_dir"]).name.replace("-", "_")
        p = Path(data["project_dir"])
        if not p.exists():
            p.mkdir(parents=True)

    def should_run(self, data):
        return not Path(data["project_dir"]).exists()