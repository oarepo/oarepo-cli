import shutil

from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep


class CheckSiteStep(SiteWizardStepMixin, WizardStep):
    def after_run(self):
        # site will be newly installed, so need to get rid of compiled stuff
        # doing it before site installation as it will place 'invenio.cfg'
        # there
        if self.site_support.invenio_instance_path.exists():
            shutil.rmtree(self.site_support.invenio_instance_path)

        self.site_support.install_site()

    def should_run(self):
        return not self.site_support.site_ok()
