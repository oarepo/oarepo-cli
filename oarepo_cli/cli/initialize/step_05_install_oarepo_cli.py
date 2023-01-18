from __future__ import annotations

import shutil
import venv
from pathlib import Path

from oarepo_cli.ui.wizard import WizardStep

from ...utils import run_cmdline


class InstallIOARepoCliStep(WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
I will install oarepo command-line tools that make using the invenio easier.
To run them, invoke the "oarepo-cli" script from within the project directory.            
            """,
            **kwargs,
        )

    def after_run(self):
        print("Creating oarepo-cli virtualenv")
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
        # TODO: non-local path
        run_cmdline(pip_binary, "install", "--no-input", "oarepo-cli")
        # run_cmdline(
        #     pip_binary,
        #     "install",
        #     "--no-input",
        #     "-e",
        #     Path(__file__).parent.parent.parent.parent,
        # )
        with open(oarepo_cli_dir / ".check.ok", "w") as f:
            f.write("oarepo check ok")

    @property
    def _oarepo_cli_dir(self):
        return self.data.project_dir / ".venv" / "oarepo-cli"

    def should_run(self):
        return not (self._oarepo_cli_dir / ".check.ok").exists()
