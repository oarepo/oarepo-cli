from pathlib import Path
import subprocess

from oarepo_cli.ui.radio import Radio
from oarepo_cli.ui.wizard import WizardStep

from ...utils import run_cmdline
import re


class InitDatabaseStep(WizardStep):
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
            **kwargs,
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
        self.check_db_initialized(data, raise_error=True)

    def check_db_initialized(self, data, raise_error=False):
        site_dir = str(Path(data["project_dir"]) / data["site_package"])
        try:
            output = run_cmdline(
                "pipenv",
                "run",
                "invenio",
                "alembic",
                "current",
                cwd=site_dir,
                environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
                grab_stdout=True,
                raise_exception=True,
            )
        except subprocess.CalledProcessError:
            raise Exception(
                "Alembic initialization failed. This could mean that the database "
                "does not exist or that there is already an incompatible alembic "
                "(previous repository) present in the database. Please fix the problem "
                "and try again"
            )
        if re.search("[a-zA-Z0-9]{12,24}\s+->\s+[a-zA-Z0-9]{12,24}", output):
            return True
        if raise_error:
            raise Exception(
                f"DB initialization failed. Expected alembic heads, got\n{output}"
            )
        return False

    def should_run(self, data):
        return not self.check_db_initialized(data, raise_error=False)
