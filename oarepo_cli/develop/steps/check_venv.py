import shutil

from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep


class CheckVirtualenvStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, clean=False, **kwargs):
        super().__init__(**kwargs)
        self.clean = clean

    def after_run(self):
        self.site_support.check_and_create_virtualenv(clean=self.clean)
        # venv was modified, so need to get rid of compiled stuff
        if self.site_support.invenio_instance_path.exists():
            shutil.rmtree(self.site_support.invenio_instance_path)

    def should_run(self):
        print("venv ok returning", self.site_support.venv_ok())
        return not self.site_support.venv_ok()
