import logging
import sys

from colorama import Fore, Style
from git import Repo

from oarepo_cli.utils import to_python_name
from oarepo_cli.wizard import WizardStep

log = logging.getLogger("step_01_initialize_directory")


class MonorepoDirectoryStep(WizardStep):
    def after_run(self):
        self.data["project_package"] = to_python_name(self.data.project_dir.name)
        p = self.data.project_dir
        if not p.exists():
            print(f"{Fore.BLUE}Creating {Style.RESET_ALL} {p}", file=sys.__stderr__)
            p.mkdir(parents=True)
        if not (p / ".git").exists():
            Repo.init(p)

    def should_run(self):
        return not self.data.project_dir.exists()
