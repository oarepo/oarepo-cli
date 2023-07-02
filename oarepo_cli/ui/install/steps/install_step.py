from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import ProjectWizardMixin, SiteMixin
from oarepo_cli.wizard import WizardStep


class InstallUIStep(SiteMixin, ProjectWizardMixin, WizardStep):
    def should_run(self):
        return True

    def after_run(self):
        sites = self.data["sites"]
        for site in sites:
            SiteSupport(self.data, site).rebuild_site(build_ui=True)
