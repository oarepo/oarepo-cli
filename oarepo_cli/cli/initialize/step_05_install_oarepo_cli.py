from __future__ import annotations

import shutil
import venv

from oarepo_cli.ui.wizard import WizardStep

from ...utils import commit_git, pip_install


class InstallIOARepoCliStep(WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
I will install oarepo command-line tools that make using the invenio easier.
To run them, invoke the "nrp-cli" script from within the project directory.            
            """,
            **kwargs,
        )

    def after_run(self):
        print("Creating nrp-cli virtualenv")
        oarepo_cli_dir = self._oarepo_cli_dir
        self.data["oarepo_cli"] = str(
            (oarepo_cli_dir / "bin" / "nrp-cli").relative_to(self.data.project_dir)
        )
        if oarepo_cli_dir.exists():
            shutil.rmtree(oarepo_cli_dir)
        venv.main([str(oarepo_cli_dir)])

        pip_install(
            oarepo_cli_dir / "bin" / "pip",
            "OAREPO_CLI_VERSION",
            "oarepo-cli>=11.0.8,<12",
            "https://github.com/oarepo/oarepo-cli",
        )

        with open(oarepo_cli_dir / ".check.ok", "w") as f:
            f.write("oarepo check ok")
        commit_git(
            self.data.project_dir,
            "after-install-oarepo-cli",
            "Committed automatically after oarepo-cli has been installed",
        )

    @property
    def _oarepo_cli_dir(self):
        return self.data.project_dir / ".venv" / "nrp-cli"

    def should_run(self):
        return not (self._oarepo_cli_dir / ".check.ok").exists()
