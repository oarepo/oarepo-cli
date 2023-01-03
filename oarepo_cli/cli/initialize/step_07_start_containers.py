from pathlib import Path

from oarepo_cli.ui.wizard import WizardStep

from ...utils import run_cmdline


class StartContainersStep(WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
I'm going to start docker containers (database, opensearch, message queue, cache etc.).
If this step fails, please fix the problem and run the wizard again.            
            """,
            **kwargs
        )

    def after_run(self, data):
        site_dir = str(Path(data["project_dir"]) / data["site_package"])

        run_cmdline(
            data["invenio_cli"],
            "services",
            "start",
            cwd=site_dir,
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
        )
        self._check_containers_running(data, False)

    def _check_containers_running(self, data, check_only):
        site_dir = str(Path(data["project_dir"]) / data["site_package"])

        return not run_cmdline(
            data["invenio_cli"],
            "services",
            "status",
            cwd=site_dir,
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
            check_only=check_only,
        )

    def should_run(self, data):
        return not self._check_containers_running(data, True)
