import queue
import threading
import traceback
from queue import Queue

from oarepo_cli.develop.config import CONTROL_PIPE
from oarepo_cli.develop.controller import PipeController, TerminalController
from oarepo_cli.develop.runners.docker import DockerDevelopmentRunner
from oarepo_cli.develop.runners.local import LocalDevelopmentRunner
from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.wizard import WizardStep


class ViteDevelopStep(WizardStep):
    def should_run(self):
        return True

    def after_run(self):
        pass
