import subprocess

from oarepo_cli.cli.site.utils import SiteWizardStepMixin
from oarepo_cli.ui.wizard import WizardStep

from ...utils import run_cmdline


class StartContainersStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
I'm going to start docker containers (database, opensearch, message queue, cache etc.).
If this step fails, please fix the problem and run the wizard again.            
            """,
            **kwargs
        )

    def after_run(self):
        run_cmdline(
            self.data.project_dir / self.data.get("config.invenio_cli"),
            "services",
            "start",
            cwd=self.site_dir,
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
        )
        self._check_containers_running(False)

    def _check_containers_running(self, check_only):
        try:
            stdout = run_cmdline(
                self.data.project_dir / self.data.get("config.invenio_cli"),
                "services",
                "status",
                cwd=self.site_dir,
                environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
                check_only=check_only,
                grab_stdout=True,
            )
            if not isinstance(stdout, str):
                return False
            if "unable to connect" in stdout:
                return False
        except subprocess.CalledProcessError:
            return False
        return True

    def should_run(self):
        return not self._check_containers_running(True)
