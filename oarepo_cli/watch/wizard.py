from oarepo_cli.watch.steps.watcher_step import WatcherStep
from oarepo_cli.wizard import Wizard
from oarepo_cli.wizard.docker import DockerRunner


class WatcherWizard(Wizard):
    def __init__(self, runner: DockerRunner, site_support, run_ui):
        self.site_support = site_support
        super().__init__(*runner.wrap_docker_steps(WatcherStep(run_ui)))
