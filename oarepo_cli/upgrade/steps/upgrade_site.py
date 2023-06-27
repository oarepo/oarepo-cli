from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.wizard import WizardStep


class UpgradeSiteStep(WizardStep):
    def should_run(self):
        return True

    def after_run(self):
        self.root.site_support.rebuild_site(clean=True, build_ui=True)
