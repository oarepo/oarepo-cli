from __future__ import annotations

import shutil
import venv
from pathlib import Path

from oarepo_cli.ui.wizard import WizardStep

from ...utils import run_cmdline
import os


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

    def after_run(self, data):
        print("Creating invenio-cli virtualenv")
        invenio_cli_dir = self._invenio_cli_dir(data)
        data["invenio_cli"] = str(
            (invenio_cli_dir / "bin" / "invenio-cli").relative_to(data.project_dir)
        )
        if invenio_cli_dir.exists():
            shutil.rmtree(invenio_cli_dir)
        venv.main([str(invenio_cli_dir)])
        pip_binary = invenio_cli_dir / "bin" / "pip"

        run_cmdline(
            pip_binary, "install", "-U", "--no-input", "setuptools", "pip", "wheel"
        )
        run_cmdline(pip_binary, "install", "--no-input", "invenio-cli")
        run_cmdline(
            invenio_cli_dir / "bin" / "invenio-cli",
            "check-requirements",
            "--development",
            environ={
                "PIPENV_IGNORE_VIRTUALENVS": "1",
                "PATH": f"{data.project_dir}/.bin:{os.environ['PATH']}",
            },
        )
        with open(invenio_cli_dir / ".check.ok", "w") as f:
            f.write("invenio check ok")

    def _invenio_cli_dir(self, data):
        return Path(data.project_dir) / ".venv" / "invenio-cli"

    def should_run(self, data):
        return not (self._invenio_cli_dir(data) / ".check.ok").exists()
