from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep


class ResolveDependenciesStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
I am going to resolve python dependencies.
            """,
            **kwargs,
        )

    def after_run(self):
        self.site_support.build_dependencies()

    def should_run(self):
        return True
