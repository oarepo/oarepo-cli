from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.wizard import WizardStep


class RunInvenioStep(WizardStep):
    def __init__(self, invenio_args):
        super().__init__()
        self.invenio_args = invenio_args

    def should_run(self):
        return True

    def after_run(self):
        site_support: SiteSupport = self.root.site_support
        site_support.call_invenio(*self.invenio_args, cwd=site_support.site_dir)
