from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.site.install_site import update_and_install_site


class UnInstallUIStep(ModelWizardStep):
    def should_run(self):
        return True

    def after_run(self):
        sites = self.data.whole_data["sites"].keys()
        for site in sites:
            update_and_install_site(self.data, site, clean=True)
