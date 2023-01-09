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

    def after_run(self, data):

        run_cmdline(
            data.project_dir / data.get("config.invenio_cli"),
            "services",
            "start",
            cwd=self.site_dir(data),
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
        )
        self._check_containers_running(data, False)

    def _check_containers_running(self, data, check_only):

        try:
            stdout = run_cmdline(
                data.project_dir / data.get("config.invenio_cli"),
                "services",
                "status",
                cwd=self.site_dir(data),
                environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
                check_only=check_only,
                grab_stdout=True,
            )
            if "unable to connect" in stdout:
                return False
        except subprocess.CalledProcessError:
            return False
        return True

    def should_run(self, data):
        return not self._check_containers_running(data, True)
