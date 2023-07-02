import re
import subprocess

from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.wizard import RadioStep, WizardStep


class InitDatabaseStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            RadioStep(
                "init_database",
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

    def after_run(self):
        if self.data["init_database"] == "yes":
            self.site_support.call_invenio("db", "create")
        self.check_db_initialized(raise_error=True)

    def check_db_initialized(self, raise_error=False):
        try:
            output = self.site_support.call_invenio(
                "alembic",
                "current",
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

    def should_run(self):
        return not self.check_db_initialized(raise_error=False)
