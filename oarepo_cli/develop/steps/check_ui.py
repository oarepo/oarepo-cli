from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep


class CheckUIStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, production=False):
        super().__init__()
        self.production = production

    def after_run(self):
        self.site_support.build_ui(production=self.production)

    def should_run(self):
        # production always rebuilds the site
        return self.production or not self.site_support.ui_ok()
