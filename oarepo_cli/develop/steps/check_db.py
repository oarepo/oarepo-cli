import json
import tempfile

from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep


class CheckDBStep(SiteWizardStepMixin, WizardStep):
    def after_run(self):
        if self.db_status == "not_initialized":
            self.site_support.call_invenio("db", "create")
        elif self.db_status == "migration_pending":
            self.site_support.call_invenio("alembic", "upgrade", "heads")
        else:
            raise Exception(f'db error not handled: "{self.db_status}"')

    def should_run(self):
        with tempfile.NamedTemporaryFile(suffix=".json") as f:
            self.site_support.call_invenio(
                "oarepo", "check", f.name, raise_exception=True, grab_stdout=True
            )
            f.seek(0)
            data = json.load(f)
            self.db_status = data["db"]
            return self.db_status != "ok"
