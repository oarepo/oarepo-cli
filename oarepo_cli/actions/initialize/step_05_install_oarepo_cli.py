from __future__ import annotations

import shutil
import venv
from pathlib import Path

from oarepo_cli.actions.utils import run_cmdline
from oarepo_cli.ui.wizard import WizardStep


class InstallIOARepoCliStep(WizardStep):
    step_name = "install-oarepo-cli"

    def __init__(self, **kwargs):
        super().__init__(
            heading="""
I will install oarepo command-line tools that make using the invenio easier.
To run them, invoke the "oarepo-cli" script from within the project directory.            
            """,
            **kwargs,
        )

    def after_run(self, data):
        print("Creating oarepo-cli virtualenv")
        oarepo_cli_dir = Path(data["project_dir"]) / ".venv" / "oarepo-cli"
        data["oarepo_cli"] = str(oarepo_cli_dir / "bin" / "oarepo-cli")
        if oarepo_cli_dir.exists():
            shutil.rmtree(oarepo_cli_dir)
        venv.main([str(oarepo_cli_dir)])
        pip_binary = oarepo_cli_dir / "bin" / "pip"

        run_cmdline(
            pip_binary, "install", "-U", "--no-input", "setuptools", "pip", "wheel"
        )
        # TODO: non-local path
        # run_cmdline(pip_binary, "install", "--no-input", "oarepo-cli")
        run_cmdline(pip_binary, "install", "--no-input", "-e", Path(__file__).parent.parent.parent.parent)
