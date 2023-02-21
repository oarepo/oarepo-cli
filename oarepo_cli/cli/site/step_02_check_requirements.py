from __future__ import annotations

import os
from pathlib import Path

from oarepo_cli.cli.site.utils import SiteWizardStepMixin
from oarepo_cli.ui.wizard import WizardStep

from ...utils import run_cmdline


class CheckRequirementsStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
I will check the requirements for Invenio site installation.
            """,
            **kwargs,
        )

    def after_run(self):
        invenio_cli_dir = self._invenio_cli_dir

        run_cmdline(
            invenio_cli_dir / "bin" / "invenio-cli",
            "check-requirements",
            "--development",
            environ={
                "PIPENV_IGNORE_VIRTUALENVS": "1",
                "PATH": f"{self.data.project_dir}/.bin:{os.environ['PATH']}",
            },
            cwd=self.site_dir,
        )
        with open(invenio_cli_dir / ".check.ok", "w") as f:
            f.write("invenio check ok")

    def should_run(self):
        return not (self._invenio_cli_dir / ".check.ok").exists()

    @property
    def _invenio_cli_dir(self):
        return Path(self.data.project_dir) / ".venv" / "invenio-cli"
