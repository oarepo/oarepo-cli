from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep


class CheckDependenciesStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, clean=False):
        super().__init__()
        self.clean = clean

    def after_run(self):
        self.site_support.build_dependencies()

    def should_run(self):
        return (
            self.clean or not (self.site_support.site_dir / "requirements.txt").exists()
        )
