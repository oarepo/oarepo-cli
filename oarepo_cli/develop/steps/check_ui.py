from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep


class CheckUIStep(SiteWizardStepMixin, WizardStep):
    def after_run(self):
        self.site_support.build_ui()

    def should_run(self):
        return not self.site_support.ui_ok()
