import os
import subprocess
import sys
import time
from pathlib import Path

from oarepo_cli.kill import kill
from oarepo_cli.site.site_support import SiteSupport


class ViteDevelopmentRunner:
    def __init__(self, site_support: SiteSupport):
        self.site_support: SiteSupport = site_support
        self.server_handle = None
        self.ui_handle = None

    def start(self):
        self.start_server()
        self.start_ui()

    def stop(self):
        self.stop_server()
        self.stop_ui()

    def restart_python(self):
        self.stop_server()
        self.start_server()

    def restart_ui(self):
        self.stop_ui()
        self.start_ui()

    @property
    def nrp_cli(self):
        return Path(sys.argv[0]).resolve()

    def start_server(self):
        print("Starting server")
        self.server_handle = subprocess.Popen(
            [
                self.nrp_cli,
                "run",
                "--site",
                self.site_support.site_name,
                "--outside-docker",
            ],
            env={
                "INVENIO_TEMPLATES_AUTO_RELOAD": "1",
                "OAREPO_UI_BUILD_FRAMEWORK": "vite",
                "OAREPO_UI_DEVELOPMENT_MODE": "1",
                "FLASK_DEBUG": "1",
                **os.environ,
            },
            stdin=subprocess.DEVNULL,
            cwd=self.site_support.config.project_dir,
        )

    def stop_server(self):
        print("Stopping server")
        self._stop_handle(self.server_handle)
        self.server_handle = None

    def start_ui(self):
        print("Starting ui")
        self.ui_handle = subprocess.Popen(
            ["bun", "vite"],
            stdin=subprocess.DEVNULL,
            cwd=self.site_support.config.project_dir,
        )
        time.sleep(5)

    def stop_ui(self):
        print("Stopping ui")
        self._stop_handle(self.ui_handle)
        self.ui_handle = None

    @staticmethod
    def _stop_handle(handle):
        if handle and handle.returncode is None:
            kill(handle.pid)
