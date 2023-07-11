import queue
import threading
import traceback
from queue import Queue

from oarepo_cli.develop.config import CONTROL_PIPE
from oarepo_cli.develop.controller import PipeController, TerminalController
from oarepo_cli.develop.runners.docker import DockerDevelopmentRunner
from oarepo_cli.develop.runners.local import LocalDevelopmentRunner
from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import run_nrp_in_docker_compose
from oarepo_cli.wizard import WizardStep


class DevelopStep(WizardStep):
    def should_run(self):
        return True

    def after_run(self):
        site_support: SiteSupport = self.root.site_support
        if not self.data.running_in_docker and self.data.use_docker:
            runner = DockerDevelopmentRunner(site_support)
        else:
            runner = LocalDevelopmentRunner(site_support)

        if not self.data.running_in_docker:
            controller = TerminalController()
        else:
            controller = PipeController(CONTROL_PIPE)

        control_queue = Queue()
        control_thread = threading.Thread(
            target=lambda: controller.run(control_queue), daemon=True
        )
        control_thread.start()
        self.control_loop(runner, control_queue)

    def control_loop(self, runner, control_queue: queue.Queue):
        runner.start()
        try:
            while True:
                try:
                    try:
                        command = control_queue.get(block=True, timeout=10)
                        print(f"Got {command=}")
                    except queue.Empty:
                        continue
                    if not command:
                        continue
                    if command == "stop":
                        runner.stop()
                        break
                    if command == "server":
                        runner.restart_python()
                        continue
                    if command == "ui":
                        runner.restart_ui()
                        continue
                    if command == "build":
                        runner.stop()
                        runner.start()
                except InterruptedError:
                    raise
                except Exception:
                    traceback.print_exc()
        except:
            runner.stop()
            return
