from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.wizard import WizardStep, WizardBase


class CheckLibrariesStep(WizardStep):
    def __init__(
        self,
        *steps: "WizardBase",
        heading=None,
        pause=False,
        libraries=None,
        **kwargs,
    ):
        super().__init__(*steps, heading=heading, pause=pause, **kwargs)
        self.libraries = libraries or {}

    def should_run(self):
        return not not self.libraries

    def after_run(self):
        in_docker = self.data.running_in_docker
        site_support: SiteSupport = self.root.site_support

        for library_name, library in self.libraries.items():
            site_support.install_local_library(
                library_name, library if not in_docker else f"/mounts/{library_name}"
            )
