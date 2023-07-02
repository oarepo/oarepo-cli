import json
import tempfile

from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep


class CheckSearchStep(SiteWizardStepMixin, WizardStep):
    def after_run(self):
        self.site_support.call_invenio("oarepo", "index", "init")
        # TODO: add option to reindex data to tooling

    def should_run(self):
        with tempfile.NamedTemporaryFile(suffix=".json") as f:
            self.site_support.call_invenio(
                "oarepo", "check", f.name, raise_exception=True, grab_stdout=True
            )
            f.seek(0)
            data = json.load(f)
            return data["opensearch"] != "ok"
