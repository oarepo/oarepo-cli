import os

from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.wizard import WizardStep


class RunServerStep(WizardStep):
    def should_run(self):
        return True

    def after_run(self):
        site_support: SiteSupport = self.root.site_support
        site_support.call_invenio(
            "run",
            "--cert",
            "docker/nginx/test.crt",
            "--key",
            "docker/nginx/test.key",
            "-h",
            os.environ.get("INVENIO_UI_HOST", "127.0.0.1"),
        )
