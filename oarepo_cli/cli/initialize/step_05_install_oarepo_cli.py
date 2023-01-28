from __future__ import annotations

import shutil
import venv
from pathlib import Path

from oarepo_cli.ui.wizard import WizardStep

from ...utils import run_cmdline

import os


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
            (oarepo_cli_dir / "bin" / "oarepo-cli").relative_to(self.data.project_dir)
        )
        if oarepo_cli_dir.exists():
            shutil.rmtree(oarepo_cli_dir)
        venv.main([str(oarepo_cli_dir)])
        pip_binary = oarepo_cli_dir / "bin" / "pip"

        run_cmdline(
            pip_binary, "install", "-U", "--no-input", "setuptools", "pip", "wheel"
        )
        installation_option = os.environ.get("OAREPO_INSTALL_VERSION", "release")
        if installation_option == "release":
            # TODO: non-local path
            run_cmdline(pip_binary, "install", "--no-input", "oarepo-cli")
        elif installation_option == "maintrunk":
            run_cmdline(
                pip_binary,
                "install",
                "--no-input",
                "git+https://github.com/oarepo/oarepo-cli",
            )
        elif installation_option == "local":
            run_cmdline(
                pip_binary,
                "install",
                "--no-input",
                "-e",
                Path(__file__).parent.parent.parent.parent,
            )
        else:
            raise ValueError(
                "Please set the OAREPO_INSTALL_VERSION to release(default), maintrunk or local (local development)"
            )
        with open(oarepo_cli_dir / ".check.ok", "w") as f:
            f.write("oarepo check ok")

    @property
    def _oarepo_cli_dir(self):
        return self.data.project_dir / ".venv" / "oarepo-cli"

    def should_run(self):
        return not (self._oarepo_cli_dir / ".check.ok").exists()
