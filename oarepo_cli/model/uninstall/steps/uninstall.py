from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.site.site_support import SiteSupport


class UnInstallModelStep(ModelWizardStep):
    def should_run(self):
        return True

    def after_run(self):
        sites = self.data.whole_data["sites"].keys()
        for site in sites:
            SiteSupport(self.data, site).rebuild_site(clean=True, build_ui=True)
