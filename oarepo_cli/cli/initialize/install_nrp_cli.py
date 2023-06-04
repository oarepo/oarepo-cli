from __future__ import annotations

import shutil
import venv

from oarepo_cli.wizard import WizardStep
from ...package_versions import NRP_CLI_VERSION

from ...utils import commit_git, pip_install


class InstallINRPCliStep(WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
I will install nrp command-line tools that make using the invenio easier.
To run them, invoke the "nrp-cli" script from within the project directory.            
            """,
            **kwargs,
        )

    def after_run(self):
        print("Creating nrp-cli virtualenv")
        self.data["oarepo_cli"] = str(
            (self.nrp_cli_dir / "bin" / "nrp-cli").relative_to(self.data.project_dir)
        )
        if self.nrp_cli_dir.exists():
            shutil.rmtree(self.nrp_cli_dir)
        venv.main([str(self.nrp_cli_dir)])

        pip_install(
            self.nrp_cli_dir / "bin" / "pip",
            "NRP_CLI_VERSION", NRP_CLI_VERSION,
            "https://github.com/oarepo/oarepo-cli",
        )

        with open(self.nrp_cli_dir / ".check.ok", "w") as f:
            f.write("oarepo check ok")
        commit_git(
            self.data.project_dir,
            "after-install-oarepo-cli",
            "Committed automatically after oarepo-cli has been installed",
        )

    @property
    def nrp_cli_dir(self):
        return self.data.project_dir / ".venv" / "nrp-cli"

    def should_run(self):
        return not (self.nrp_cli_dir / ".check.ok").exists()
