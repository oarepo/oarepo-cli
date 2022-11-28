from pathlib import Path

from utils import run_cmdline

from oarepo_cli.ui.radio import Radio
from oarepo_cli.ui.wizard import WizardStep


class InitDatabaseStep(WizardStep):
    step_name = "init-database"

    def __init__(self, **kwargs):
        super().__init__(
            Radio(
                "init_database_switch",
                options={"yes": "Yes", "no": "No"},
                default="yes",
            ),
            heading="""
If the database has not been initialized, I can do it now - 
this will delete all the previous data in the database.

Should I do it?
            """,
            **kwargs
        )

    def after_run(self, data):
        if data["init_database_switch"] == "yes":
            site_dir = str(Path(data["project_dir"]) / data["site_package"])
            run_cmdline(
                "pipenv",
                "run",
                "invenio",
                "db",
                "create",
                cwd=site_dir,
                environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
            )
