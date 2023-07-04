from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.wizard import WizardStep


class RunOARepoStep(WizardStep):
    def __init__(self, oarepo_args):
        super().__init__()
        self.oarepo_args = oarepo_args

    def should_run(self):
        return True

    def after_run(self):
        site_support: SiteSupport = self.root.site_support
        site_support.call_invenio(
            "oarepo", *self.oarepo_args, cwd=site_support.site_dir
        )
