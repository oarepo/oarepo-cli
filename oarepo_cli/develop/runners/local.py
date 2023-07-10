import os
import subprocess
import sys
import time
from pathlib import Path

from oarepo_cli.kill import kill
from oarepo_cli.site.site_support import SiteSupport


class LocalDevelopmentRunner:
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
                "--use-docker"
                if self.site_support.config.use_docker
                else "--outside-docker",
            ],
            env={
                "INVENIO_TEMPLATES_AUTO_RELOAD": "1",
                "INVENIO_DEVELOPMENT_MODE": "1",
                "FLASK_DEBUG": "1",
                **os.environ,
            },
            stdin=subprocess.DEVNULL,
            cwd=self.site_support.config.project_dir,
        )

    def stop_server(self):
        print("Stopping server")
        self.stop_handle(self.server_handle)
        self.server_handle = None

    def start_ui(self):
        print("Starting file watcher")
        self.ui_handle = subprocess.Popen(
            [
                self.nrp_cli,
                "ui-watch",
                "--site",
                self.site_support.site_name,
                "--use-docker"
                if self.site_support.config.use_docker
                else "--outside-docker",
                "--run-ui",
            ],
            stdin=subprocess.DEVNULL,
            cwd=self.site_support.config.project_dir,
        )
        time.sleep(5)

    def stop_ui(self):
        print("Stopping file watcher")
        self.stop_handle(self.ui_handle)
        self.ui_handle = None

    @staticmethod
    def stop_handle(handle):
        if handle and handle.returncode is None:
            kill(handle.pid)
