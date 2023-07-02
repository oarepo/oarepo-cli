from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.wizard import WizardStep


class UpgradeSiteStep(WizardStep):
    def __init__(self, site=None):
        super().__init__()
        self.site = site

    def should_run(self):
        return True

    def after_run(self):
        if not hasattr(self.root, "site_support"):
            site_support = SiteSupport(self.data, self.site)
        else:
            site_support = self.root.site_support
        site_support.rebuild_site(clean=True, build_ui=True)
