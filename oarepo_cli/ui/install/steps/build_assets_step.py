from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import ProjectWizardMixin, SiteMixin
from oarepo_cli.wizard import WizardStep


class BuildAssetsUIStep(SiteMixin, ProjectWizardMixin, WizardStep):
    def should_run(self):
        return True

    def after_run(self):
        sites = self.data["sites"]
        for site_name in sites:
            support = SiteSupport(self.data, site_name)
            support.build_ui()
