from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep


class CheckDependenciesStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, clean=False, require_up_to_date=False):
        super().__init__()
        self.clean = clean
        self.require_up_to_date = require_up_to_date

    def after_run(self):
        if self.require_up_to_date:
            self.site_support.require_dependencies_up_to_date()
        else:
            self.site_support.build_dependencies()

    def should_run(self):
        return (
            self.require_up_to_date
            or self.clean
            or not (self.site_support.site_dir / "requirements.txt").exists()
        )
