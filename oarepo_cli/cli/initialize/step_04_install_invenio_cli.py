from __future__ import annotations

import shutil
import venv
from pathlib import Path

from oarepo_cli.ui.wizard import WizardStep

from ...utils import commit_git, pip_install


class InstallInvenioCliStep(WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""I will install invenio command-line client. I will use the client to check that
you have all the tools installed (python, docker, ...). If this step fails, please fix the problem
and run this wizard again.

Before the installation, you may have a look at the requirements at
https://inveniordm.docs.cern.ch/install/requirements/ .
            """,
            **kwargs,
        )

    def after_run(self):
        print("Creating invenio-cli virtualenv")
        invenio_cli_dir = self._invenio_cli_dir
        self.data["invenio_cli"] = str(
            (invenio_cli_dir / "bin" / "invenio-cli").relative_to(self.data.project_dir)
        )
        if invenio_cli_dir.exists():
            shutil.rmtree(invenio_cli_dir)
        venv.main([str(invenio_cli_dir)])

        pip_install(
            invenio_cli_dir / "bin" / "pip",
            "INVENIO_CLI_VERSION",
            "invenio-cli==1.0.16",
            "https://github.com/inveniosoftware/invenio-cli",
        )

        with open(invenio_cli_dir / ".install.ok", "w") as f:
            f.write("invenio installation ok")
        commit_git(
            self.data.project_dir,
            "after-install-invenio-cli",
            "Committed automatically after invenio-cli has been installed",
        )

    @property
    def _invenio_cli_dir(self):
        return Path(self.data.project_dir) / ".venv" / "invenio-cli"

    def should_run(self):
        return not (self._invenio_cli_dir / ".install.ok").exists()
