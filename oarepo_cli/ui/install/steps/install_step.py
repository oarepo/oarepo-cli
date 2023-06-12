from oarepo_cli.site.install_site import update_and_install_site
from oarepo_cli.utils import SiteMixin, ProjectWizardMixin
from oarepo_cli.wizard import WizardStep


class InstallUIStep(SiteMixin, ProjectWizardMixin, WizardStep):
    def should_run(self):
        return True

    def after_run(self):
        sites = self.data["sites"]
        for site in sites:
            update_and_install_site(self.data, site)