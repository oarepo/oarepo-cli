from pathlib import Path

from oarepo_cli.ui.wizard import WizardStep

from ..utils import run_cmdline


class StartContainersStep(WizardStep):
    step_name = "start-containers"

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
        run_cmdline(
            data["invenio_cli"],
            "services",
            "status",
            cwd=site_dir,
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
        )
