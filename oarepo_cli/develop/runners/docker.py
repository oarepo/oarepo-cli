import threading

from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import exec_nrp_in_docker, run_nrp_in_docker_compose


class DockerDevelopmentRunner:
    def __init__(self, site_support: SiteSupport):
        self.site_support: SiteSupport = site_support

    def start(self):
        self.development_server_thread = threading.Thread(
            target=lambda: self.run_docker_develop(), daemon=True
        )
        self.development_server_thread.start()

    @property
    def develop_container_name(self):
        return self.site_support.site_name + "-repo-develop"

    def run_docker_develop(self):
        run_nrp_in_docker_compose(
            self.site_support.site_dir,
            "develop",
            "--site",
            self.site_support.site_name,
            "--step",
            "DevelopStep",
            interactive=False,
            no_input=True,
            name=self.develop_container_name,
        )

    def stop(self):
        self.send_command("stop")

    def restart_python(self):
        self.send_command("server")

    def restart_ui(self):
        self.send_command("ui")

    def send_command(self, command):
        exec_nrp_in_docker(
            self.site_support.site_dir,
            self.develop_container_name,
            "develop",
            "--command",
            command,
            "--site",
            self.site_support.site_name,
            interactive=False,
        )
